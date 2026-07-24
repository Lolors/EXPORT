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


def cleanup_invalid_links(case_id: int) -> int:
    invalid_rows = db.rows(
        '''SELECT s.id
           FROM shipment_items s
           LEFT JOIN order_items o
             ON o.id=s.order_item_id
            AND o.case_id=s.case_id
           WHERE s.case_id=?
             AND s.order_item_id IS NOT NULL
             AND o.id IS NULL''',
        (case_id,),
    )
    if not invalid_rows:
        return 0
    ids = [int(row['id']) for row in invalid_rows]
    db.executemany('DELETE FROM shipment_items WHERE id=?', [(shipment_id,) for shipment_id in ids])
    db.execute(
        '''DELETE FROM boxes
           WHERE case_id=?
             AND NOT EXISTS(
                 SELECT 1 FROM shipment_items s
                 WHERE s.case_id=boxes.case_id AND s.box_no=boxes.box_no
             )''',
        (case_id,),
    )
    return len(ids)


def list_actual(case_id: int):
    cleanup_invalid_links(case_id)
    return db.rows(
        '''SELECT s.business_unit, s.product_name, s.lot_no, s.expiry_date, s.requested_qty
           FROM shipment_items s
           JOIN order_items o
             ON o.id=s.order_item_id
            AND o.case_id=s.case_id
           WHERE s.case_id=?
           ORDER BY s.id''',
        (case_id,),
    )


def get_lot_expiry_dataframe(case_id: int):
    import pandas as pd

    cleanup_invalid_links(case_id)
    rows = db.rows(
        '''SELECT s.id AS _id, s.product_name AS 제품명, s.requested_qty AS 출고수량,
                  s.box_no AS CTN번호, s.lot_no AS 제조번호, s.expiry_date AS 유통기한
           FROM shipment_items s
           JOIN order_items o
             ON o.id=s.order_item_id
            AND o.case_id=s.case_id
           WHERE s.case_id=?
           ORDER BY CASE WHEN s.box_no IS NULL THEN 1 ELSE 0 END, s.box_no, s.id''',
        (case_id,),
    )
    return pd.DataFrame([dict(row) for row in rows])


def update_lot_expiry(case_id: int, edited) -> int:
    now = now_text()
    updated = 0
    valid_ids = {
        int(row['id'])
        for row in db.rows(
            '''SELECT s.id
               FROM shipment_items s
               JOIN order_items o
                 ON o.id=s.order_item_id
                AND o.case_id=s.case_id
               WHERE s.case_id=?''',
            (case_id,),
        )
    }
    for _, row in edited.iterrows():
        raw_id = row.get('_id')
        if raw_id in (None, '', 0):
            continue
        shipment_id = int(raw_id)
        if shipment_id not in valid_ids:
            continue
        db.execute(
            '''UPDATE shipment_items
               SET lot_no=?, expiry_date=?, updated_at=?
               WHERE id=? AND case_id=?''',
            (
                str(row.get('제조번호', '') or '').strip(),
                str(row.get('유통기한', '') or '').strip(),
                now,
                shipment_id,
                case_id,
            ),
        )
        updated += 1
    if updated:
        db.execute('UPDATE export_cases SET updated_at=? WHERE id=?', (now, case_id))
    return updated


def list_linked(case_id: int, order_item_id: int):
    cleanup_invalid_links(case_id)
    return db.rows(
        '''SELECT s.id, s.business_unit, s.product_name, s.lot_no, s.expiry_date,
                  s.requested_qty, s.box_no
           FROM shipment_items s
           JOIN order_items o
             ON o.id=s.order_item_id
            AND o.case_id=s.case_id
           WHERE s.case_id=? AND s.order_item_id=?
           ORDER BY s.id''',
        (case_id, order_item_id),
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
    order = db.row('SELECT id FROM order_items WHERE id=? AND case_id=?', (order_item_id, case_id))
    if order is None:
        raise ValueError('현재 수출 건의 주문품목을 찾을 수 없습니다.')

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
    cleanup_invalid_links(case_id)
    result = db.row(
        '''SELECT COALESCE(SUM(s.requested_qty),0) AS quantity
           FROM shipment_items s
           JOIN order_items o
             ON o.id=s.order_item_id
            AND o.case_id=s.case_id
           WHERE s.case_id=?''',
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
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                (case_id, order['id'], '', '', order['product_name'], '', '',
                 order['quantity'], None, now, now),
            )
    for shipment in db.rows(
        'SELECT id, order_item_id FROM shipment_items WHERE case_id=? AND order_item_id IS NOT NULL',
        (case_id,),
    ):
        if int(shipment['order_item_id']) not in order_ids:
            db.execute('DELETE FROM shipment_items WHERE id=?', (shipment['id'],))
