from __future__ import annotations

import streamlit as st


def order_editor(dataframe, *, key: str, dynamic: bool = True):
    return st.data_editor(
        dataframe,
        num_rows='dynamic' if dynamic else 'fixed',
        hide_index=True,
        use_container_width=True,
        key=key,
        column_order=['제품명', '수량', '단위'],
        column_config={
            '_id': None,
            '제품명': st.column_config.TextColumn('제품명', required=True),
            '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0, width='small'),
            '단위': st.column_config.TextColumn('단위', width='small'),
        },
    )


def shipment_editor(dataframe, *, key: str):
    return st.data_editor(
        dataframe,
        num_rows='dynamic',
        hide_index=True,
        use_container_width=True,
        key=key,
    )