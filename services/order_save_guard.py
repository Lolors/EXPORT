from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from services import order_service


_original_save_order_items = order_service.save_order_items


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


def _safe_number(value: object, default: float = 0.0) -> float:
    if value is None or pd.isna(value) or value == '':
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_duplicate_rows(cleaned: pd.DataFrame) -> list[dict[str, object]]:
    """Return every editor row whose normalized product name appears more than once."""
    normalized_names: dict[str, list[tuple[int, str]]] = {}

    for position, (_, row) in enumerate(cleaned.iterrows(), start=1):
        name = _clean_text(row.get('제품명'))
        if not name:
            continue

        key = order_service.normalize_product_name(name)
        if not key:
            key = name.casefold()
        normalized_names.setdefault(key, []).append((position, name))

    return [
        {'행': position, '제품명': name}
        for items in normalized_names.values()
        if len(items) > 1
        for position, name in items
    ]


def render_duplicate_notice(rows: list[dict[str, object]]) -> None:
    """Show compact duplicate feedback directly beneath the order editor."""
    if not rows:
        return

    grouped: dict[str, list[int]] = {}
    for row in rows:
        name = _clean_text(row.get('제품명'))
        position = int(row.get('행', 0))
        grouped.setdefault(name, []).append(position)

    chips = ''.join(
        (
            '<span style="display:inline-flex;align-items:center;gap:0.35rem;'
            'padding:0.28rem 0.55rem;margin:0.18rem 0.22rem 0 0;'
            'border:1px solid #f3a8c5;border-radius:999px;'
            'background:#ffd6e7;color:#7a173f;font-weight:650;">'
            f'{escape(name)} · {", ".join(f"{position}행" for position in positions)}'
            '</span>'
        )
        for name, positions in grouped.items()
    )

    st.markdown(
        (
            '<div style="margin:0.35rem 0 0.65rem;padding:0.72rem 0.82rem;'
            'border:1px solid #f3a8c5;border-radius:0.65rem;background:#fff0f6;">'
            '<div style="color:#7a173f;font-weight:750;margin-bottom:0.28rem;">'
            '같은 제품명이 주문 목록에 중복되어 있습니다.'
            '</div>'
            '<div style="color:#8f3157;font-size:0.9rem;margin-bottom:0.25rem;">'
            '아래 제품명 셀의 행을 합치거나 제품명을 구분한 뒤 저장하세요.'
            '</div>'
            f'<div>{chips}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def save_order_items(case_id: int, edited) -> None:
    """Validate and normalize the order editor before using the existing save logic."""
    cleaned = edited.copy()

    if '매입가' not in cleaned.columns:
        cleaned['매입가'] = 0.0
    cleaned['매입가'] = cleaned['매입가'].map(lambda value: _safe_number(value, 0.0))

    if '수량' in cleaned.columns:
        cleaned['수량'] = cleaned['수량'].map(lambda value: _safe_number(value, 0.0))

    duplicate_rows = find_duplicate_rows(cleaned)
    if duplicate_rows:
        render_duplicate_notice(duplicate_rows)
        st.stop()

    _original_save_order_items(case_id, cleaned)


def install() -> None:
    order_service.save_order_items = save_order_items
