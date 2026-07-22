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
    db.execute(
        "UPDATE export_cases SET stage='패킹',updated_at=? WHERE id=?",
        (now, case_id),
    )


def unassign_items(case_id: int, item_ids: list[int]) -> None:
    now = now_text()
    for item_id in item_ids:
        db.execute(
            'UPDATE shipment_items SET box_no=NULL,updated_at=? WHERE id=? AND case_id=?',
            (now, item_id, case_id),
        )


def update_box(box_id: int, length: float, width: float, height: float, weight: float) -> None:
    db.execute(
        'UPDATE boxes SET length_cm=?,width_cm=?,height_cm=?,weight_kg=?,updated_at=? WHERE id=?',
        (length, width, height, weight, now_text(), box_id),
    )


def clear_box(case_id: int, box_no: int) -> None:
    db.execute(
        'UPDATE shipment_items SET box_no=NULL,updated_at=? WHERE case_id=? AND box_no=?',
        (now_text(), case_id, box_no),
    )
    db.execute('DELETE FROM boxes WHERE case_id=? AND box_no=?', (case_id, box_no))
