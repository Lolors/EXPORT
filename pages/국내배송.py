from __future__ import annotations

from datetime import date

import streamlit as st

from services import delivery_service, export_service, folder_service, history_service
from utils.dates import parse_date
from utils.formatters import case_label, fmt_number


def date_value(value: str | None):
    parsed = parse_date(value)
    return parsed.date() if parsed else date.today()


def order_state(ordered: float, linked: float) -> tuple[str, str]:
    if ordered > 0 and linked >= ordered:
        return '🟢', '확보 완료'
    if linked > 0:
        return '🟡', '일부 확보'
    return '🔴', '미확보'


st.title('국내배송')
st.caption('국내배송 방식과 송장 또는 배송기사 정보를 입력합니다.')

cases = export_service.list_cases()
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

options = {
    f"{case_label(case)} · {case['transport_mode']}": int(case['id'])
    for case in cases
}
case_id = options[st.selectbox('수출 건 선택', list(options), key='delivery_case')]
case = export_service.get_case(case_id)
orders = export_service.get_order_items_with_actual(case_id)

method = st.radio(
    '배송 방식',
    ['로젠택배', '퀵배송'],
    index=1 if case['domestic_method'] == '퀵배송' else 0,
    horizontal=True,
)
with st.form(f'delivery_{case_id}_{method}'):
    actual_date = st.date_input('국내배송 일자', value=date_value(case['actual_ship_date']))
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
    )
    folder = folder_service.sync_case_folder(case_id)
    history_service.add(case_id, '국내배송 완료', f'{method} / {folder}')
    st.success('저장했습니다.')
    st.rerun()

st.markdown('#### 주문품목별 확보 현황')
for order in orders:
    ordered = float(order['quantity'] or 0)
    linked = float(order['actual_qty'] or 0)
    icon, label = order_state(ordered, linked)
    st.write(
        f"{icon} **{order['product_name']}** — "
        f"{fmt_number(linked)} / {fmt_number(ordered)} {order['unit'] or 'EA'} · {label}"
    )
