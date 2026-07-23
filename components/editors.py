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
            '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0, width=30),
            '단위': st.column_config.TextColumn('단위', width=30),
        },
    )


def historical_order_editor(dataframe, *, key: str):
    return st.data_editor(
        dataframe,
        num_rows='dynamic',
        hide_index=True,
        use_container_width=True,
        key=key,
        column_order=['제품명', '수량', '단위', 'CTN 번호'],
        column_config={
            '제품명': st.column_config.TextColumn('제품명', required=True),
            '수량': st.column_config.NumberColumn('수량', min_value=0.0, step=1.0),
            '단위': st.column_config.TextColumn('단위'),
            'CTN 번호': st.column_config.NumberColumn('CTN 번호', min_value=1, step=1),
        },
    )


def historical_box_editor(dataframe, *, key: str):
    return st.data_editor(
        dataframe,
        num_rows='dynamic',
        hide_index=True,
        use_container_width=True,
        key=key,
        column_order=['CTN 번호', '가로 (cm)', '세로 (cm)', '높이 (cm)', 'GW (kg)'],
        column_config={
            'CTN 번호': st.column_config.NumberColumn('CTN 번호', min_value=1, step=1, required=True),
            '가로 (cm)': st.column_config.NumberColumn('가로 (cm)', min_value=0.0, step=0.1),
            '세로 (cm)': st.column_config.NumberColumn('세로 (cm)', min_value=0.0, step=0.1),
            '높이 (cm)': st.column_config.NumberColumn('높이 (cm)', min_value=0.0, step=0.1),
            'GW (kg)': st.column_config.NumberColumn('GW (kg)', min_value=0.0, step=0.1),
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
