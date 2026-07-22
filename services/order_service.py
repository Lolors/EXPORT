from __future__ import annotations

import db
from utils.dates import now_text


def list_editable_cases():
    return db.rows(
        '''SELECT c.id, c.export_no, c.buyer, c.country, c.transport_mode, c.stage,
                  c.status, c.note, c.actual_ship_date, c.case_type, c.created_at,
                  COALESCE(GROUP_CONCAT(o.product_name, ' '), '') AS product_names
           FROM export_cases c
           LEFT JOIN order_items o ON o.case_id=c.id
           WHERE c.stage<>'취소'
           GROUP BY c.id, c.export_no, c.buyer, c.country, c.transport_mode, c.stage,
                    c.status, c.note, c.actual_ship_date, c.case_type, c.created_at
           ORDER BY COALESCE(NULLIF(c.actual_ship_date,''), c.created_at) DESC'''
    )


def list_for_case(case_id: int):
    return db.rows(
        '''SELECT id, product_name, quantity, unit, created_at
           FROM order_items
           WHERE case_id=?
           ORDER BY id''',
        (case_id,),
    )


def get_order_items_dataframe(case_id: int):
    import pandas as pd

    rows = db.rows(
        '''SELECT o.id AS _id, o.product_name AS 제품명, o.quantity AS 수량, o.unit AS 단위
           FROM order_items o
           WHERE o.case_id=?
           ORDER BY o.id''',
        (case_id,),
    )
    return pd.DataFrame([dict(row) for row in rows])


def create_order_items(case_id: int, items: list[tuple[str, float, str]], *, historical: bool = False) -> None:
    now = now_text()
    for product_name, quantity, unit in items:
        order_id = db.execute(
            'INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',
            (case_id, product_name, quantity, unit, now),
        )
        if historical:
            db.execute(
                '''INSERT INTO shipment_items(
                       case_id,order_item_id,business_unit,location,product_name,
                       lot_no,expiry_date,requested_qty,box_no,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (case_id, order_id, '', '', product_name, '', '', quantity, None, now, now),
            )


def sync_historical_shipments(case_id: int) -> None:
    case = db.row('SELECT case_type FROM export_cases WHERE id=?', (case_id,))
    if not case or case['case_type'] != 'historical':
        return

    now = now_text()
    orders = db.rows(
        'SELECT id, product_name, quantity FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    order_ids = {int(row['id']) for row in orders}

    for order in orders:
        shipment = db.row(
            'SELECT id FROM shipment_items WHERE case_id=? AND order_item_id=? ORDER BY id LIMIT 1',
            (case_id, order['id']),
        )
        if shipment:
            db.execute(
                'UPDATE shipment_items SET product_name=?,requested_qty=?,updated_at=? WHERE id=?',
                (order['product_name'], order['quantity'], now, shipment['id']),
            )
            db.execute(
                'DELETE FROM shipment_items WHERE case_id=? AND order_item_id=? AND id<>?',
                (case_id, order['id'], shipment['id']),
            )
        else:
            db.execute(
                '''INSERT INTO shipment_items(
                       case_id,order_item_id,business_unit,location,product_name,
                       lot_no,expiry_date,requested_qty,box_no,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (case_id, order['id'], '', '', order['product_name'], '', '', order['quantity'], None, now, now),
            )

    linked = db.rows(
        'SELECT id, order_item_id FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
        (case_id,),
    )
    for shipment in linked:
        if int(shipment['order_item_id']) not in order_ids:
            db.execute('DELETE FROM shipment_items WHERE id=?', (shipment['id'],))


def save_order_items(case_id: int, edited) -> None:
    existing_rows = db.rows(
        '''SELECT o.id, o.product_name, o.quantity, o.unit,
                  COUNT(s.id) AS linked_count
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=?
           GROUP BY o.id, o.product_name, o.quantity, o.unit
           ORDER BY o.id''',
        (case_id,),
    )
    existing = {int(row['id']): row for row in existing_rows}
    seen_ids: set[int] = set()
    now = now_text()
    case = db.row('SELECT case_type FROM export_cases WHERE id=?', (case_id,))
    historical = bool(case and case['case_type'] == 'historical')

    for _, row in edited.iterrows():
        raw_id = row.get('_id')
        order_id = int(raw_id) if raw_id not in (None, '', 0) else None
        product_name = str(row.get('제품명', '') or '').strip()
        quantity = float(row.get('수량', 0) or 0)
        unit = str(row.get('단위', 'EA') or 'EA').strip() or 'EA'

        if not product_name:
            continue

        if order_id and order_id in existing:
            seen_ids.add(order_id)
            db.execute(
                'UPDATE order_items SET product_name=?,quantity=?,unit=? WHERE id=? AND case_id=?',
                (product_name, quantity, unit, order_id, case_id),
            )
        else:
            db.execute(
                'INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',
                (case_id, product_name, quantity, unit, now),
            )

    for order_id, row in existing.items():
        if order_id in seen_ids:
            continue
        if not historical and int(row['linked_count'] or 0) > 0:
            raise ValueError(
                f"실출고가 연결된 주문품목 '{row['product_name']}'은 삭제할 수 없습니다. 수량·제품명 수정은 가능합니다."
            )
        db.execute('DELETE FROM shipment_items WHERE case_id=? AND order_item_id=?', (case_id, order_id))
        db.execute('DELETE FROM order_items WHERE id=? AND case_id=?', (order_id, case_id))

    sync_historical_shipments(case_id)
