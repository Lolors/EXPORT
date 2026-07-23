from __future__ import annotations

from datetime import date

import streamlit as st

from services import delivery_service, export_service, folder_service, history_service
from utils.dates import parse_date
from utils.formatters import case_label


def date_value(value: str | None):
    parsed = parse_date(value)
    return parsed.date() if parsed else date.today()


st.title('국내배송')
st.caption('국내배송 방식, 수하인 정보와 송장 또는 배송기사 정보를 입력합니다.')

cases = export_service.active_cases()
if not cases:
    st.info('국내배송 처리할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='delivery_case')]
case = export_service.get_case(case_id)

method = st.radio(
    '배송 방식',
    ['로젠택배', '퀵배송'],
    index=1 if case['domestic_method'] == '퀵배송' else 0,
    horizontal=True,
)
with st.form(f'delivery_{case_id}_{method}'):
    actual_date = st.date_input('국내배송 일자', value=date_value(case['actual_ship_date']))
    receiver_cols = st.columns([1, 2])
    consignee_name = receiver_cols[0].text_input('수하인명', value=case['consignee_name'] or '')
    consignee_address = receiver_cols[1].text_input('수하인주소', value=case['consignee_address'] or '')
    tracking = st.text_input('송장번호', value=case['tracking_no'] or '') if method == '로젠택배' else ''
    if method == '퀵배송':
        c1, c2 = st.columns(2)
        driver = c1.text_input('배송기사 이름', value=case['driver_name'] or '')
        phone = c2.text_input('연락처', value=case['driver_phone'] or '')
    else:
        driver = phone = ''
    submitted = st.form_submit_button('배송정보 저장 및 완료 처리', type='primary')

if submitted:
    delivery_service.save_delivery(
        case_id,
        method=method,
        actual_ship_date=str(actual_date),
        tracking_no=tracking,
        driver_name=driver,
        driver_phone=phone,
        consignee_name=consignee_name,
        consignee_address=consignee_address,
    )
    folder = folder_service.sync_case_folder(case_id)
    history_service.add(case_id, '국내배송 완료', f'{method} / {consignee_name} / {folder}')
    st.success('저장했습니다.')
    st.rerun()
