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


def _safe_row_number(value: object, fallback: int) -> int:
    if value is None or pd.isna(value) or value == '':
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def with_row_numbers(frame: pd.DataFrame) -> pd.DataFrame:
    numbered = frame.copy().reset_index(drop=True)
    numbered['행번호'] = range(1, len(numbered) + 1)
    columns = ['행번호'] + [column for column in numbered.columns if column != '행번호']
    return numbered[columns]


def _normalized_name(value: object) -> str:
    name = _clean_text(value)
    if not name:
        return ''
    return order_service.normalize_product_name(name) or name.casefold()


def duplicate_groups(cleaned: pd.DataFrame) -> list[list[int]]:
    grouped: dict[str, list[int]] = {}
    for position, (_, row) in enumerate(cleaned.iterrows()):
        key = _normalized_name(row.get('제품명'))
        if key:
            grouped.setdefault(key, []).append(position)
    return [positions for positions in grouped.values() if len(positions) > 1]


def find_duplicate_rows(cleaned: pd.DataFrame) -> list[dict[str, object]]:
    """Return every editor row whose normalized product name appears more than once."""
    rows: list[dict[str, object]] = []
    for positions in duplicate_groups(cleaned):
        for position in positions:
            row = cleaned.iloc[position]
            rows.append({
                '행': _safe_row_number(row.get('행번호'), position + 1),
                '제품명': _clean_text(row.get('제품명')),
            })
    return rows


def merge_duplicate_rows(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Keep the first duplicate row, sum quantities, and remove later rows."""
    merged = cleaned.copy().reset_index(drop=True)
    remove_positions: set[int] = set()

    for positions in duplicate_groups(merged):
        first_position = positions[0]
        total_quantity = sum(_safe_number(merged.iloc[position].get('수량')) for position in positions)
        merged.at[first_position, '수량'] = total_quantity
        remove_positions.update(positions[1:])

    if remove_positions:
        merged = merged.drop(index=sorted(remove_positions)).reset_index(drop=True)

    merged = merged.drop(columns=['행번호'], errors='ignore')
    return with_row_numbers(merged)


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
            '<div style="margin:0.35rem 0 0.5rem;padding:0.72rem 0.82rem;'
            'border:1px solid #f3a8c5;border-radius:0.65rem;background:#fff0f6;">'
            '<div style="color:#7a173f;font-weight:750;margin-bottom:0.28rem;">'
            '같은 제품명이 주문 목록에 중복되어 있습니다.'
            '</div>'
            '<div style="color:#8f3157;font-size:0.9rem;margin-bottom:0.25rem;">'
            '먼저 생성된 행의 제품명·단위·매입가를 유지하고 수량만 합칠 수 있습니다.'
            '</div>'
            f'<div>{chips}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def save_order_items(case_id: int, edited) -> None:
    """Validate and normalize the order editor before using the existing save logic."""
    cleaned = edited.copy().drop(columns=['행번호'], errors='ignore')

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
