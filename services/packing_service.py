from __future__ import annotations

import db


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
        '''SELECT box_no, length_cm, width_cm, height_cm, weight_kg, updated_at
           FROM boxes WHERE case_id=? ORDER BY box_no''',
        (case_id,),
    )


def clear_box(case_id: int, box_no: int) -> None:
    db.execute(
        'UPDATE shipment_items SET box_no=NULL WHERE case_id=? AND box_no=?',
        (case_id, box_no),
    )
    db.execute('DELETE FROM boxes WHERE case_id=? AND box_no=?', (case_id, box_no))
