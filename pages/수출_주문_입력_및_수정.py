from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from components.editors import order_editor
from config import TRANSPORT_MODES
from services import export_service, folder_service, history_service, order_service
from utils.formatters import case_label
from utils.numbering import next_export_no


st.title('수출 주문 입력 및 수정')
st.caption('현재 진행 건은 주문목록을 등록하고, 과거 수출 건은 주문목록을 실출고 제품으로도 자동 저장합니다.')

st.markdown('#### 수출 주문 등록')
case_type_label = st.radio(
    '등록 유형',
    ['현재 진행 건', '과거 수출 건'],
    horizontal=True,
    key='new_case_type',
)
is_historical = case_type_label == '과거 수출 건'

c1, c2 = st.columns(2)
country = c1.text_input('국가 *', key='new_country')
buyer = c2.text_input('바이어 (선택)', key='new_buyer')
transport = c1.selectbox('운송방식', TRANSPORT_MODES, key='new_transport')
note = c2.text_input('비고', key='new_note')

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

st.text_input('수출번호', value=export_no_preview, disabled=True, key='new_export_no')

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

cases = order_service.list_editable_cases()
if not cases:
    st.info('수정할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
selected_case_id = st.session_state.get('order_case_id')
labels = list(options)
default_index = 0
if selected_case_id in options.values():
    default_index = list(options.values()).index(selected_case_id)
case_id = options[st.selectbox('주문을 수정할 수출 건', labels, index=default_index)]

case_map = {int(row['id']): row for row in cases}
case = case_map[case_id]

with st.form(f'case_edit_{case_id}'):
    st.markdown('#### 기본 정보 수정')
    c1, c2 = st.columns(2)
    new_country = c1.text_input('국가 *', value=case['country'])
    new_buyer = c2.text_input('바이어 (선택)', value=case['buyer'])
    transport_index = TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in TRANSPORT_MODES else 0
    new_transport = c1.selectbox('운송방식', TRANSPORT_MODES, index=transport_index)
    new_note = c2.text_input('비고', value=case['note'])
    save_basic = st.form_submit_button('기본 정보 저장')

if save_basic:
    if not new_country.strip():
        st.error('국가는 필수입니다.')
    else:
        export_service.update_basic(case_id, new_country, new_buyer, new_transport, new_note)
        folder_service.sync_case_folder(case_id)
        history_service.add_history(case_id, '수출 기본 정보 수정', f'{new_country} / {new_transport}')
        st.success('기본 정보를 저장했습니다.')
        st.rerun()

existing = order_service.get_order_items_dataframe(case_id)
if existing.empty:
    existing = pd.DataFrame([{'_id': None, '제품명': '', '수량': 0.0, '단위': 'EA'}])

historical_case = case['case_type'] == 'historical'
st.markdown('#### 실출고 제품 수정' if historical_case else '#### 주문품목 수정')
if historical_case:
    st.caption('과거 수출 건에서는 수정한 내용이 주문목록과 실출고 제품에 함께 반영됩니다.')
else:
    st.caption('실출고가 연결된 행은 삭제할 수 없지만 제품명·수량·단위는 수정할 수 있습니다.')

edited = order_editor(existing, key=f'orders_{case_id}')
if st.button('목록 저장' if historical_case else '주문 목록 저장', type='primary', key=f'save_orders_{case_id}'):
    try:
        order_service.save_order_items(case_id, edited)
    except ValueError as exc:
        st.error(str(exc))
    else:
        folder_service.sync_case_folder(case_id)
        action = '과거 실출고 목록 저장' if historical_case else '주문 목록 저장'
        history_service.add_history(case_id, action, f'{len(edited)}행')
        st.success('목록을 저장했습니다.')
        st.rerun()
