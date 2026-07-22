from __future__ import annotations

from typing import Any

import db
from utils.dates import now_text


def get_case(case_id: int):
    return db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))


def list_cases(include_cancelled: bool = False):
    sql = 'SELECT * FROM export_cases'
    if not include_cancelled:
        sql += " WHERE status<>'취소' AND stage<>'취소'"
    return db.rows(sql + ' ORDER BY COALESCE(NULLIF(actual_ship_date,\'\'),created_at) DESC')


def active_cases(country: str | None = None):
    sql = "SELECT * FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소')"
    params: tuple[Any, ...] = ()
    if country:
        sql += ' AND country=?'
        params = (country,)
    return db.rows(sql + ' ORDER BY created_at', params)


def get_order_items(case_id: int):
    return db.rows(
        'SELECT id, product_name, quantity, unit, created_at FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )


def get_order_items_with_actual(case_id: int):
    return db.rows(
        '''SELECT o.id, o.product_name, o.quantity, o.unit,
                  COALESCE(SUM(s.requested_qty),0) AS actual_qty
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=?
           GROUP BY o.id, o.product_name, o.quantity, o.unit
           ORDER BY o.id''',
        (case_id,),
    )


def update_basic(case_id: int, country: str, buyer: str, transport: str, note: str) -> None:
    db.execute(
        '''UPDATE export_cases
           SET country=?,buyer=?,transport_mode=?,note=?,updated_at=?
           WHERE id=?''',
        (country.strip(), buyer.strip(), transport, note.strip(), now_text(), case_id),
    )


def create_case(*, export_no: str, buyer: str, country: str, transport: str,
                note: str, actual_ship_date: str = '', case_type: str = 'current',
                stage: str = '주문 접수', status: str = '진행중') -> int:
    now = now_text()
    return db.execute(
        '''INSERT INTO export_cases(
               export_no,buyer,country,transport_mode,stage,status,note,
               actual_ship_date,case_type,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (export_no, buyer.strip(), country.strip(), transport, stage, status,
         note.strip(), actual_ship_date, case_type, now, now),
    )
