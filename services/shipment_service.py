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
