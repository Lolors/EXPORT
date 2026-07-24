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


def save_order_items(case_id: int, edited) -> None:
    """Validate and normalize the order editor before using the existing save logic."""
    cleaned = edited.copy()

    if '매입가' not in cleaned.columns:
        cleaned['매입가'] = 0.0
    cleaned['매입가'] = cleaned['매입가'].map(lambda value: _safe_number(value, 0.0))

    if '수량' in cleaned.columns:
        cleaned['수량'] = cleaned['수량'].map(lambda value: _safe_number(value, 0.0))

    product_names = [
        _clean_text(value)
        for value in cleaned.get('제품명', [])
        if _clean_text(value)
    ]
    normalized_names: dict[str, list[str]] = {}
    for name in product_names:
        key = order_service.normalize_product_name(name)
        if not key:
            key = name.casefold()
        normalized_names.setdefault(key, []).append(name)

    duplicates = [names for names in normalized_names.values() if len(names) > 1]
    if duplicates:
        duplicate_text = ', '.join(' / '.join(names) for names in duplicates)
        st.warning(
            '같은 제품명이 주문 목록에 중복되어 있습니다. '
            f'중복 행을 합치거나 제품명을 구분한 뒤 다시 저장하세요: {duplicate_text}'
        )
        st.stop()

    _original_save_order_items(case_id, cleaned)


def install() -> None:
    order_service.save_order_items = save_order_items
