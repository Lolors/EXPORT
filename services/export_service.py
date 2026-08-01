from __future__ import annotations

from typing import Any

import streamlit as st

import db
from utils.dates import now_text


@st.cache_data(show_spinner=False, persist='disk', max_entries=128)
def _cached_case(case_id: int, cache_token: tuple[int, int, int, int]):
    result = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
    return dict(result) if result else None


def get_case(case_id: int):
    return _cached_case(int(case_id), db.read_cache_token())


@st.cache_data(show_spinner=False, persist='disk', max_entries=64)
def _cached_case_list(
    include_cancelled: bool,
    cache_token: tuple[int, int, int, int],
) -> list[dict]:
    sql = 'SELECT * FROM export_cases'
    if not include_cancelled:
        sql += " WHERE status<>'취소' AND stage<>'취소'"
    rows = db.rows(sql + " ORDER BY COALESCE(NULLIF(actual_ship_date,''),created_at) DESC")
    return [dict(row) for row in rows]


def list_cases(include_cancelled: bool = False):
    return _cached_case_list(bool(include_cancelled), db.read_cache_token())


@st.cache_data(show_spinner=False, persist='disk', max_entries=64)
def _cached_active_cases(
    country: str,
    cache_token: tuple[int, int, int, int],
) -> list[dict]:
    sql = "SELECT * FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소')"
    params: tuple[Any, ...] = ()
    if country:
        sql += ' AND country=?'
        params = (country,)
    return [dict(row) for row in db.rows(sql + ' ORDER BY created_at', params)]


def active_cases(country: str | None = None):
    return _cached_active_cases(str(country or ''), db.read_cache_token())


@st.cache_data(show_spinner=False, persist='disk', max_entries=32)
def _cached_intake_editable_cases(
    cache_token: tuple[int, int, int, int],
) -> list[dict]:
    rows = db.rows(
        '''SELECT *
           FROM export_cases
           WHERE case_type<>'historical'
             AND status<>'취소'
             AND stage IN (
                 '주문 접수','출고 대기','입고 진행',
                 '패킹 대기','패킹 진행','패킹 완료','국내배송'
             )
           ORDER BY COALESCE(NULLIF(actual_ship_date,''),created_at) DESC'''
    )
    return [dict(row) for row in rows]


def intake_editable_cases():
    """Current export cases whose intake may still need correction."""
    return _cached_intake_editable_cases(db.read_cache_token())


@st.cache_data(show_spinner=False, persist='disk', max_entries=128)
def _cached_order_items(
    case_id: int,
    cache_token: tuple[int, int, int, int],
) -> list[dict]:
    rows = db.rows(
        'SELECT id, product_name, quantity, unit, created_at FROM order_items WHERE case_id=? ORDER BY id',
        (case_id,),
    )
    return [dict(row) for row in rows]


def get_order_items(case_id: int):
    return _cached_order_items(int(case_id), db.read_cache_token())


@st.cache_data(show_spinner=False, persist='disk', max_entries=64)
def _cached_order_items_for_cases(
    case_ids: tuple[int, ...],
    cache_token: tuple[int, int, int, int],
) -> list[dict]:
    if not case_ids:
        return []
    placeholders = ','.join('?' for _ in case_ids)
    rows = db.rows(
        f'''SELECT case_id, id, product_name, quantity, unit
            FROM order_items
            WHERE case_id IN ({placeholders})
            ORDER BY case_id, id''',
        case_ids,
    )
    return [dict(row) for row in rows]


def get_order_items_for_cases(case_ids) -> list[dict]:
    normalized = tuple(sorted({int(case_id) for case_id in case_ids}))
    return _cached_order_items_for_cases(normalized, db.read_cache_token())


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


def update_basic(
    case_id: int,
    country: str,
    buyer: str,
    transport: str,
    note: str,
    *,
    actual_ship_date: str | None = None,
) -> None:
    if actual_ship_date is None:
        db.execute(
            '''UPDATE export_cases
               SET country=?,buyer=?,transport_mode=?,note=?,updated_at=?
               WHERE id=?''',
            (country.strip(), buyer.strip(), transport, note.strip(), now_text(), case_id),
        )
        return

    db.execute(
        '''UPDATE export_cases
           SET country=?,buyer=?,transport_mode=?,note=?,actual_ship_date=?,updated_at=?
           WHERE id=?''',
        (
            country.strip(),
            buyer.strip(),
            transport,
            note.strip(),
            actual_ship_date.strip(),
            now_text(),
            case_id,
        ),
    )


def cancel_case(case_id: int) -> None:
    db.execute(
        '''UPDATE export_cases
           SET stage='취소', status='취소', updated_at=?
           WHERE id=?''',
        (now_text(), case_id),
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