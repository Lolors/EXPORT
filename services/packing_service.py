from __future__ import annotations

import db
from utils.dates import now_text


def list_items(case_id: int):
    return db.rows(
        '''SELECT id, business_unit, product_name, lot_no, expiry_date,
                  requested_qty, box_no
           FROM shipment_items
           WHERE case_id=?
           ORDER BY CASE WHEN box_no IS NULL THEN 0 ELSE 1 END, box_no, id''',
        (case_id,),
    )


def list_packed_rows(case_id: int):
    return db.rows(
        '''SELECT s.id, s.box_no, s.business_unit, s.product_name, s.lot_no,
                  s.expiry_date, s.requested_qty, b.weight_kg, b.length_cm,
                  b.width_cm, b.height_cm
           FROM shipment_items s
           LEFT JOIN boxes b ON b.case_id=s.case_id AND b.box_no=s.box_no
           WHERE s.case_id=? AND s.box_no IS NOT NULL
           ORDER BY s.box_no, s.id''',
        (case_id,),
    )


def list_boxes(case_id: int):
    return db.rows(
        '''SELECT id, box_no, length_cm, width_cm, height_cm, weight_kg, updated_at
           FROM boxes WHERE case_id=? ORDER BY box_no''',
        (case_id,),
    )


def list_box_items(case_id: int, box_no: int):
    return db.rows(
        '''SELECT business_unit, product_name, lot_no, expiry_date, requested_qty
           FROM shipment_items
           WHERE case_id=? AND box_no=?
           ORDER BY id''',
        (case_id, box_no),
    )


def next_box_no(case_id: int) -> int:
    result = db.row('SELECT COALESCE(MAX(box_no),0)+1 AS n FROM boxes WHERE case_id=?', (case_id,))
    return int(result['n'] or 1)


def _sync_packing_stage(case_id: int, now: str | None = None) -> None:
    timestamp = now or now_text()
    result = db.row(
        '''SELECT COALESCE(SUM(CASE WHEN box_no IS NULL THEN requested_qty ELSE 0 END), 0) AS remaining_qty
           FROM shipment_items
           WHERE case_id=?''',
        (case_id,),
    )
    remaining_qty = float(result['remaining_qty'] or 0) if result else 0.0
    stage = '패킹 완료' if remaining_qty <= 0 else '패킹 진행'
    db.execute(
        'UPDATE export_cases SET stage=?, updated_at=? WHERE id=?',
        (stage, timestamp, case_id),
    )


def assign_items(case_id: int, item_ids: list[int], box_no: int) -> None:
    now = now_text()
    for item_id in item_ids:
        db.execute(
            'UPDATE shipment_items SET box_no=?,updated_at=? WHERE id=? AND case_id=?',
            (box_no, now, item_id, case_id),
        )
    db.execute(
        'INSERT OR IGNORE INTO boxes(case_id,box_no,updated_at) VALUES (?,?,?)',
        (case_id, box_no, now),
    )
    _sync_packing_stage(case_id, now)


def assign_partial_item(case_id: int, item_id: int, box_no: int, quantity: float) -> None:
    item = db.row(
        '''SELECT id, case_id, order_item_id, business_unit, location, product_name,
                  lot_no, expiry_date, requested_qty, box_no, created_at
           FROM shipment_items
           WHERE id=? AND case_id=?''',
        (item_id, case_id),
    )
    if item is None:
        raise ValueError('선택한 실제 출고제품을 찾을 수 없습니다.')

    current_qty = float(item['requested_qty'] or 0)
    if item['box_no'] is not None:
        raise ValueError('이미 박스에 배정된 제품은 일부 배정할 수 없습니다.')
    if quantity <= 0:
        raise ValueError('배정 수량은 0보다 커야 합니다.')
    if quantity > current_qty:
        raise ValueError('배정 수량은 남은 출고수량보다 클 수 없습니다.')

    if quantity == current_qty:
        assign_items(case_id, [item_id], box_no)
        return

    now = now_text()
    remaining_qty = current_qty - quantity
    db.execute(
        '''UPDATE shipment_items
           SET requested_qty=?, box_no=?, updated_at=?
           WHERE id=? AND case_id=?''',
        (quantity, box_no, now, item_id, case_id),
    )
    db.execute(
        '''INSERT INTO shipment_items(
               case_id, order_item_id, business_unit, location, product_name,
               lot_no, expiry_date, requested_qty, box_no, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,NULL,?,?)''',
        (
            case_id,
            item['order_item_id'],
            item['business_unit'],
            item['location'],
            item['product_name'],
            item['lot_no'],
            item['expiry_date'],
            remaining_qty,
            item['created_at'] or now,
            now,
        ),
    )
    db.execute(
        'INSERT OR IGNORE INTO boxes(case_id,box_no,updated_at) VALUES (?,?,?)',
        (case_id, box_no, now),
    )
    _sync_packing_stage(case_id, now)


def unassign_items(case_id: int, item_ids: list[int]) -> None:
    now = now_text()
    for item_id in item_ids:
        db.execute(
            'UPDATE shipment_items SET box_no=NULL,updated_at=? WHERE id=? AND case_id=?',
            (now, item_id, case_id),
        )
    _sync_packing_stage(case_id, now)


def update_box(box_id: int, length: float, width: float, height: float, weight: float) -> None:
    db.execute(
        'UPDATE boxes SET length_cm=?,width_cm=?,height_cm=?,weight_kg=?,updated_at=? WHERE id=?',
        (length, width, height, weight, now_text(), box_id),
    )


def clear_box(case_id: int, box_no: int) -> None:
    now = now_text()
    db.execute(
        'UPDATE shipment_items SET box_no=NULL,updated_at=? WHERE case_id=? AND box_no=?',
        (now, case_id, box_no),
    )
    db.execute('DELETE FROM boxes WHERE case_id=? AND box_no=?', (case_id, box_no))
    _sync_packing_stage(case_id, now)
