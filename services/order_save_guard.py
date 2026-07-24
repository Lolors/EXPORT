from __future__ import annotations

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


def _duplicate_rows(cleaned: pd.DataFrame) -> tuple[list[list[str]], list[dict[str, object]]]:
    normalized_names: dict[str, list[tuple[int, str]]] = {}

    for position, (_, row) in enumerate(cleaned.iterrows(), start=1):
        name = _clean_text(row.get('제품명'))
        if not name:
            continue

        key = order_service.normalize_product_name(name)
        if not key:
            key = name.casefold()
        normalized_names.setdefault(key, []).append((position, name))

    duplicate_groups = [items for items in normalized_names.values() if len(items) > 1]
    duplicate_names = [[name for _, name in items] for items in duplicate_groups]
    duplicate_rows = [
        {'행': position, '제품명': name}
        for items in duplicate_groups
        for position, name in items
    ]
    return duplicate_names, duplicate_rows


def _show_duplicate_rows(rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    duplicate_frame = pd.DataFrame(rows)
    styled = duplicate_frame.style.map(
        lambda _: 'background-color: #ffd6e7; color: #7a173f; font-weight: 600;',
        subset=['제품명'],
    )
    st.markdown('**중복된 주문 행**')
    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        column_config={
            '행': st.column_config.NumberColumn('행', format='%d', width='small'),
            '제품명': st.column_config.TextColumn('제품명'),
        },
    )


def save_order_items(case_id: int, edited) -> None:
    """Validate and normalize the order editor before using the existing save logic."""
    cleaned = edited.copy()

    if '매입가' not in cleaned.columns:
        cleaned['매입가'] = 0.0
    cleaned['매입가'] = cleaned['매입가'].map(lambda value: _safe_number(value, 0.0))

    if '수량' in cleaned.columns:
        cleaned['수량'] = cleaned['수량'].map(lambda value: _safe_number(value, 0.0))

    duplicate_names, duplicate_rows = _duplicate_rows(cleaned)
    if duplicate_names:
        duplicate_text = ', '.join(' / '.join(names) for names in duplicate_names)
        st.warning(
            '같은 제품명이 주문 목록에 중복되어 있습니다. '
            f'중복 행을 합치거나 제품명을 구분한 뒤 다시 저장하세요: {duplicate_text}'
        )
        _show_duplicate_rows(duplicate_rows)
        st.stop()

    _original_save_order_items(case_id, cleaned)


def install() -> None:
    order_service.save_order_items = save_order_items
