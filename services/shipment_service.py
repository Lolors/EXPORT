from __future__ import annotations

import db
from utils.dates import now_text


def list_for_case(case_id: int):
    return db.rows(
        '''SELECT id, case_id, order_item_id, business_unit, product_name,
                  lot_no, expiry_date, requested_qty, box_no, created_at, updated_at
           FROM shipment_items WHERE case_id=? ORDER BY id''',
        (case_id,),
    )


def list_actual(case_id: int):
    return db.rows(
        '''SELECT business_unit, product_name, lot_no, expiry_date, requested_qty
           FROM shipment_items
           WHERE case_id=? AND order_item_id IS NOT NULL
           ORDER BY id''',
        (case_id,),
    )


def list_linked(order_item_id: int):
    return db.rows(
        '''SELECT id, business_unit, product_name, lot_no, expiry_date,
                  requested_qty, box_no
           FROM shipment_items
           WHERE order_item_id=?
           ORDER BY id''',
        (order_item_id,),
    )


def count_unlinked(case_id: int) -> int:
    result = db.row(
        'SELECT COUNT(*) AS count FROM shipment_items WHERE case_id=? AND order_item_id IS NULL',
        (case_id,),
    )
    return int(result['count'] or 0) if result else 0


def list_unlinked(case_id: int):
    return db.rows(
        '''SELECT id, business_unit, product_name, lot_no, expiry_date,
                  requested_qty, box_no
           FROM shipment_items
           WHERE case_id=? AND order_item_id IS NULL
           ORDER BY id''',
        (case_id,),
    )


def delete_unlinked(case_id: int) -> None:
    db.execute('DELETE FROM shipment_items WHERE case_id=? AND order_item_id IS NULL', (case_id,))
    db.execute(
        '''DELETE FROM boxes
           WHERE case_id=?
             AND NOT EXISTS(
                 SELECT 1 FROM shipment_items s
                 WHERE s.case_id=boxes.case_id AND s.box_no=boxes.box_no
             )''',
        (case_id,),
    )


def save_for_order(case_id: int, order_item_id: int, rows: list[dict]) -> float:
    values = []
    now = now_text()
    total = 0.0
    for item in rows:
        product_name = str(item.get('product_name', '') or '').strip()
        quantity = float(item.get('requested_qty', 0) or 0)
        if not product_name:
            raise ValueError('입력된 행에는 실제 제품명이 필요합니다.')
        total += quantity
        values.append((
            case_id,
            order_item_id,
            str(item.get('business_unit', '') or '').strip(),
            '',
            product_name,
            str(item.get('lot_no', '') or '').strip(),
            str(item.get('expiry_date', '') or '').strip(),
            quantity,
            None,
            now,
            now,
        ))

    db.execute('DELETE FROM shipment_items WHERE case_id=? AND order_item_id=?', (case_id, order_item_id))
    if values:
        db.executemany(
            '''INSERT INTO shipment_items(
                   case_id, order_item_id, business_unit, location, product_name,
                   lot_no, expiry_date, requested_qty, box_no, created_at, updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            values,
        )
    db.execute("UPDATE export_cases SET stage='출고 대기', updated_at=? WHERE id=?", (now, case_id))
    return total


def total_linked_quantity(case_id: int) -> float:
    result = db.row(
        'SELECT COALESCE(SUM(requested_qty),0) AS quantity FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
        (case_id,),
    )
    return float(result['quantity'] or 0) if result else 0.0


def sync_historical(case_id: int) -> None:
    case = db.row('SELECT case_type FROM export_cases WHERE id=?', (case_id,))
    if not case or case['case_type'] != 'historical':
        return
    now = now_text()
    orders = db.rows(
        'SELECT id, product_name, quantity FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    order_ids = {int(order['id']) for order in orders}
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
                (case_id, order['id'], '', '', order['product_name'], '', '',
                 order['quantity'], None, now, now),
            )
    for shipment in db.rows(
        'SELECT id, order_item_id FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
        (case_id,),
    ):
        if int(shipment['order_item_id']) not in order_ids:
            db.execute('DELETE FROM shipment_items WHERE id=?', (shipment['id'],))
