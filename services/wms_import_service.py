from __future__ import annotations

import sqlite3
from pathlib import Path

import db
from services import product_name_match_service, shipment_service
from utils.dates import now_text


_SETTING_KEY = "wms_db_path"


def configured_db_path() -> str:
    return db.get_setting(_SETTING_KEY).strip()


def save_db_path(path_text: str) -> str:
    path = Path(str(path_text or "").strip()).expanduser()
    if not path.is_file():
        raise ValueError("WMS 데이터베이스 파일을 찾을 수 없습니다.")
    with sqlite3.connect(path) as con:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"export_waiting_orders", "export_waiting_items"}.issubset(tables):
            raise ValueError("선택한 파일은 NOHTUS WMS 데이터베이스가 아닙니다.")
    resolved = str(path.resolve())
    db.set_setting(_SETTING_KEY, resolved)
    return resolved


def _wms_rows(export_no: str) -> list[dict]:
    path_text = configured_db_path()
    if not path_text or not Path(path_text).is_file():
        raise ValueError("WMS DB 경로를 먼저 설정하세요.")
    with sqlite3.connect(f"file:{Path(path_text).resolve()}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """SELECT i.id AS wms_item_id,i.company,i.product_name,i.lot,i.exp_date,i.qty,
                      o.id AS wms_order_id,o.status,o.updated_at
               FROM export_waiting_orders o
               JOIN export_waiting_items i ON i.order_id=o.id
               WHERE TRIM(o.export_no)=TRIM(?) AND COALESCE(o.status,'')<>'cancelled'
               ORDER BY o.id,i.id""",
            (export_no,),
        ).fetchall()
        return [dict(row) for row in rows]


def preview(case_id: int) -> dict:
    case = db.row("SELECT export_no FROM export_cases WHERE id=?", (int(case_id),))
    if not case:
        raise ValueError("수출 건을 찾을 수 없습니다.")
    orders = db.rows(
        "SELECT id,product_name,quantity,unit FROM order_items WHERE case_id=? ORDER BY id",
        (int(case_id),),
    )
    normalized_orders: dict[str, list] = {}
    for order in orders:
        key = product_name_match_service.normalize_for_match(str(order["product_name"] or ""))
        normalized_orders.setdefault(key, []).append(order)

    rows = []
    matched_by_order: dict[int, list[dict]] = {}
    for item in _wms_rows(str(case["export_no"] or "")):
        key = product_name_match_service.normalize_for_match(str(item["product_name"] or ""))
        candidates = normalized_orders.get(key, [])
        if len(candidates) == 1:
            order = candidates[0]
            status = "일치"
            order_item_id = int(order["id"])
            order_name = str(order["product_name"] or "")
            matched_by_order.setdefault(order_item_id, []).append({
                "business_unit": item["company"] or "",
                "product_name": item["product_name"] or "",
                "lot_no": item["lot"] or "",
                "expiry_date": item["exp_date"] or "",
                "requested_qty": float(item["qty"] or 0),
            })
        elif len(candidates) > 1:
            status, order_item_id, order_name = "주문 중복", None, ""
        else:
            status, order_item_id, order_name = "주문에 없음", None, ""
        rows.append({
            "매칭상태": status,
            "주문제품": order_name,
            "WMS 표준제품명": item["product_name"] or "",
            "사업장": item["company"] or "",
            "제조번호": item["lot"] or "",
            "유통기한": item["exp_date"] or "",
            "수량": float(item["qty"] or 0),
            "_order_item_id": order_item_id,
        })

    order_totals = {int(order["id"]): float(order["quantity"] or 0) for order in orders}
    differences = []
    for order in orders:
        order_id = int(order["id"])
        imported = sum(float(row["requested_qty"]) for row in matched_by_order.get(order_id, []))
        ordered = order_totals[order_id]
        if abs(imported - ordered) > 0.000001:
            differences.append({
                "주문제품": order["product_name"],
                "주문수량": ordered,
                "WMS 수출대기": imported,
                "차이": imported - ordered,
            })
    return {"rows": rows, "matched_by_order": matched_by_order, "differences": differences}


@db.backup_batch
def apply(case_id: int) -> dict:
    result = preview(case_id)
    unmatched = [row for row in result["rows"] if row["매칭상태"] != "일치"]
    if unmatched:
        raise ValueError("주문과 자동 매칭되지 않은 WMS 품목이 있어 불러올 수 없습니다.")
    for order_item_id, rows in result["matched_by_order"].items():
        shipment_service.save_for_order(int(case_id), int(order_item_id), rows)
    db.execute("UPDATE export_cases SET updated_at=? WHERE id=?", (now_text(), int(case_id)))
    return {
        "row_count": len(result["rows"]),
        "order_count": len(result["matched_by_order"]),
        "difference_count": len(result["differences"]),
    }
