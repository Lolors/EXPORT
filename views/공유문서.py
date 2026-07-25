from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st
from services import export_service, folder_service, order_service
from services.shared_document_view_service import (
    display_stage,
    filter_and_sort_cases,
    format_case_option as build_case_option_label,
    shipment_date,
)
def open_selected_path(path: Path, label: str) -> None:
    try:
        path = Path(path)
        if not path.exists():
            st.error(f'{label} 경로가 없습니다: {path}')
            return
        activation_script = f'Start-Process -FilePath "{str(path).replace(chr(34), chr(34) * 2)}"'
        subprocess.Popen(
            ['powershell.exe', '-NoProfile', '-WindowStyle', 'Hidden', '-Command', activation_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        st.error(f'{label}을(를) 열 수 없습니다: {exc}')


st.title('공유용 자료')
st.caption('수출 건을 선택한 뒤 필요한 자료를 출력하거나 관련 폴더를 열 수 있습니다.')

cases = order_service.list_editable_cases()
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#document-case-filter-anchor) {
        width: 56vw;
        max-width: 56vw;
    }
    @media(max-width:900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#document-case-filter-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

with st.container():
    st.markdown('<span id="document-case-filter-anchor"></span>', unsafe_allow_html=True)
    now = datetime.now()
    years = sorted(
        {
            now.year,
            *{
                int(shipment_date(case)[:4])
                for case in cases
                if shipment_date(case)[:4].isdigit()
            },
        },
        reverse=True,
    )
    filter_cols = st.columns([1.5, 1.5, 3, 4])
    year_options: list[str | int] = ['전체'] + years
    selected_year = filter_cols[0].selectbox(
        '연도',
        year_options,
        index=year_options.index(now.year),
        key='document_case_year',
    )
    month_options: list[str | int] = ['전체'] + list(range(1, 13))
    selected_month = filter_cols[1].selectbox(
        '월',
        month_options,
        index=month_options.index(now.month),
        key='document_case_month',
    )
    countries = sorted({str(case['country']).strip() for case in cases if str(case['country']).strip()})
    selected_country = filter_cols[2].selectbox('국가', ['전체'] + countries, key='document_case_country')
    product_query = filter_cols[3].text_input('제품명 검색', key='document_case_product_search').strip().casefold()

filtered_cases = filter_and_sort_cases(
    cases,
    selected_year=selected_year,
    selected_month=selected_month,
    selected_country=selected_country,
    product_query=product_query,
)
if not filtered_cases:
    st.warning('조건에 맞는 수출 건이 없습니다.')
    st.stop()

case_by_id = {int(case['id']): case for case in filtered_cases}
case_options: list[int | None] = [None, *case_by_id.keys()]


case_filter_key = (
    f"{selected_year}_{selected_month}_{selected_country}_{product_query}_"
    f"{len(filtered_cases)}"
)
selected_case_id = st.selectbox(
    '수출 건 선택',
    case_options,
    format_func=lambda selected_id: (
        '수출 건을 선택하세요'
        if selected_id is None
        else build_case_option_label(case_by_id[int(selected_id)])
    ),
    key=f'document_case_select_{case_filter_key}',
)
if selected_case_id is None:
    st.session_state.pop('document_case_id', None)
    st.session_state.pop('shared_document_view', None)
    st.info('공유용 자료를 만들 수출 건을 선택하세요.')
    st.stop()

case_id = int(selected_case_id)
previous_case_id = st.session_state.get('document_case_id')
if previous_case_id != case_id:
    st.session_state['document_case_id'] = case_id
    st.session_state.pop('shared_document_view', None)
case = export_service.get_case(case_id)

action_cols = st.columns(5)
open_folder = action_cols[0].button('📂 폴더 열기', use_container_width=True)
open_workbook = action_cols[1].button('📄 수출진행내역', use_container_width=True)
open_photos = action_cols[2].button('🖼 출고제품사진', use_container_width=True)
open_ci = action_cols[3].button('📑 CI', use_container_width=True)
open_shipping_mark = action_cols[4].button('🚢 Shipping Mark', use_container_width=True)

if any([open_folder, open_workbook, open_photos, open_ci, open_shipping_mark]):
    try:
        case_folder = folder_service.ensure_case_folder(case_id)
        if open_folder:
            open_selected_path(case_folder, '수출 폴더')
        elif open_workbook:
            open_selected_path(case_folder / '수출진행내역.xlsx', '수출진행내역')
        elif open_photos:
            open_selected_path(folder_service.category_folder(case_id, '출고사진'), '출고제품사진 폴더')
        elif open_ci:
            open_selected_path(folder_service.category_folder(case_id, 'CI'), 'CI 폴더')
        elif open_shipping_mark:
            open_selected_path(folder_service.category_folder(case_id, 'Shipping Mark'), 'Shipping Mark 폴더')
    except Exception as exc:
        st.warning(f'수출 폴더를 준비하지 못했습니다: {exc}')
else:
    stored_folder_path = str(case['folder_path'] or '').strip()
    if stored_folder_path:
        st.caption(stored_folder_path)

is_final_document_available = str(case['stage'] or '').strip() in {'패킹 완료', '국내배송'}
output_cols = st.columns(2)
if output_cols[0].button(
    '최종문서 출력하기',
    type='primary',
    use_container_width=True,
    disabled=not is_final_document_available,
    help=None if is_final_document_available else '패킹 완료 또는 국내배송 단계에서 최종문서를 출력할 수 있습니다.',
):
    st.session_state['shared_document_view'] = 'final'
if output_cols[1].button('출고 예정 제품 리스트', use_container_width=True):
    st.session_state['shared_document_view'] = 'shipment_products'

if not is_final_document_available and st.session_state.get('shared_document_view') == 'final':
    st.session_state.pop('shared_document_view', None)

selected_view = st.session_state.get('shared_document_view')
if selected_view == 'final':
    from components.shared_document_renderer import render_document
    from services import document_service

    packed, _ = document_service.get_document_data(case_id)
    render_document(case, packed)
elif selected_view == 'shipment_products':
    from components.shared_document_renderer import render_shipment_product_list
    from services import document_service, shipment_service

    fresh_actual_rows = shipment_service.list_actual(case_id)
    actual_rows = document_service._aggregate_actual(fresh_actual_rows)
    render_shipment_product_list(case, actual_rows)
else:
    if not is_final_document_available:
        st.caption('최종문서는 패킹 완료 또는 국내배송 단계에서 출력할 수 있습니다.')
    st.info('출력할 문서 종류를 선택하세요.')
