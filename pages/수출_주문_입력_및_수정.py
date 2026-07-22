from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components.editors import order_editor
from config import TRANSPORT_MODES
from services import export_service, folder_service, history_service, order_service
from utils.numbering import next_export_no


st.title('주문 입력')
st.caption('현재 진행 건은 주문목록을 등록하고, 과거 수출 건은 주문목록을 실출고 제품으로도 자동 저장합니다.')

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#new-case-basic-info-anchor) {
        width: 80vw;
        max-width: 80vw;
    }
    @media (max-width: 900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#new-case-basic-info-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

st.markdown('#### 수출 주문 등록')
case_type_label = st.radio(
    '등록 유형',
    ['현재 진행 건', '과거 수출 건'],
    horizontal=True,
    key='new_case_type',
)
is_historical = case_type_label == '과거 수출 건'

historical_date = None
if is_historical:
    historical_date = st.date_input(
        '과거 수출일',
        value=date.today(),
        help='수출번호의 연도와 폴더 연도를 결정하며, 국내배송 완료일로 저장됩니다.',
        key='historical_export_date',
    )
    export_no_preview = next_export_no('HIS', historical_date.year)
else:
    export_no_preview = next_export_no('EXP')

with st.container():
    st.markdown('<span id="new-case-basic-info-anchor"></span>', unsafe_allow_html=True)
    export_no_col, country_col, buyer_col, transport_col, note_col = st.columns([2, 2, 2, 1, 3])
    export_no_col.text_input('수출번호', value=export_no_preview, disabled=True, key='new_export_no')
    country = country_col.text_input('국가 *', key='new_country')
    buyer = buyer_col.text_input('바이어 (선택)', key='new_buyer')
    transport = transport_col.selectbox('운송방식', TRANSPORT_MODES, key='new_transport')
    note = note_col.text_input('비고', key='new_note')

st.markdown('#### 주문 목록' if not is_historical else '#### 실출고 제품 목록')
if is_historical:
    st.caption('과거 수출 건에서는 아래 목록이 주문목록과 실출고 제품에 동시에 저장됩니다.')
new_order_source = pd.DataFrame([{'제품명': '', '수량': 0.0, '단위': 'EA'}])
new_orders = order_editor(new_order_source, key='new_order_items')

if st.button('수출 건 생성', type='primary', key='create_case'):
    valid_orders = []
    for _, row in new_orders.iterrows():
        product_name = str(row.get('제품명', '') or '').strip()
        if not product_name:
            continue
        valid_orders.append((
            product_name,
            float(row.get('수량', 0) or 0),
            str(row.get('단위', 'EA') or 'EA').strip() or 'EA',
        ))

    if not country.strip():
        st.error('국가는 필수입니다.')
    elif not valid_orders:
        st.error('제품을 한 개 이상 입력하세요.')
    else:
        prefix = 'HIS' if is_historical else 'EXP'
        number_year = historical_date.year if historical_date else None
        export_no = next_export_no(prefix, number_year)
        case_type = 'historical' if is_historical else 'current'
        actual_ship_date = str(historical_date) if historical_date else ''
        stage = '완료' if is_historical else '주문 접수'
        status = '완료' if is_historical else '진행중'
        case_id = export_service.create_case(
            export_no=export_no,
            buyer=buyer,
            country=country,
            transport=transport,
            note=note,
            actual_ship_date=actual_ship_date,
            case_type=case_type,
            stage=stage,
            status=status,
        )
        order_service.create_order_items(case_id, valid_orders, historical=is_historical)
        folder_service.sync_case_folder(case_id)
        history_detail = f'{export_no} / 제품 {len(valid_orders)}개'
        if is_historical:
            history_detail += ' / 주문목록=실출고'
        history_service.add_history(case_id, '수출 건 생성', history_detail)
        st.session_state['order_case_id'] = case_id
        st.success(f'{export_no} 생성 완료')
        st.rerun()
