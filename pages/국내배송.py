from __future__ import annotations

from datetime import date

import streamlit as st

import db


def date_value(value: str | None):
    parsed = db.parse_date(value)
    return parsed.date() if parsed else date.today()


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return '0'


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['transport_mode']} · {case['stage']}"


def order_rows(case_id: int):
    return db.rows(
        '''SELECT o.id, o.product_name, o.quantity, o.unit,
                  COALESCE(SUM(s.requested_qty),0) AS linked_qty
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=?
           GROUP BY o.id, o.product_name, o.quantity, o.unit
           ORDER BY o.id''',
        (case_id,),
    )


st.title('국내배송')
st.caption('국내배송 방식과 송장 또는 배송기사 정보를 입력합니다.')

cases = db.rows(
    "SELECT * FROM export_cases WHERE status<>'취소' AND stage<>'취소' ORDER BY COALESCE(NULLIF(actual_ship_date,''),NULLIF(expected_ship_date,''),created_at) DESC"
)
if not cases:
    st.info('표시할 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='delivery_case')]
case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))
orders = order_rows(case_id)

method = st.radio('배송 방식', ['로젠택배', '퀵배송'], index=1 if case['domestic_method']=='퀵배송' else 0, horizontal=True)
with st.form(f'delivery_{case_id}_{method}'):
    actual_date = st.date_input('국내배송 일자', value=date_value(case['actual_ship_date']))
    tracking = st.text_input('송장번호', value=case['tracking_no'] or '') if method=='로젠택배' else ''
    if method == '퀵배송':
        c1, c2 = st.columns(2)
        driver = c1.text_input('배송기사 이름', value=case['driver_name'] or '')
        phone = c2.text_input('연락처', value=case['driver_phone'] or '')
    else:
        driver = phone = ''
    submitted = st.form_submit_button('배송정보 저장 및 완료 처리', type='primary')

if submitted:
    db.execute(
        "UPDATE export_cases SET domestic_method=?,tracking_no=?,driver_name=?,driver_phone=?,actual_ship_date=?,stage='국내배송',status='완료',updated_at=? WHERE id=?",
        (method, tracking, driver, phone, str(actual_date), db.now_text(), case_id),
    )
    folder = db.sync_case_folder(case_id)
    db.add_history(case_id, '국내배송 완료', f'{method} / {folder}')
    st.success('저장했습니다.')
    st.rerun()

st.markdown('#### 주문품목별 확보 현황')
for order in orders:
    ordered = float(order['quantity'] or 0)
    linked = float(order['linked_qty'] or 0)
    if ordered > 0 and linked >= ordered:
        icon, label = '🟢', '확보 완료'
    elif linked > 0:
        icon, label = '🟡', '일부 확보'
    else:
        icon, label = '🔴', '미확보'
    st.write(f"{icon} **{order['product_name']}** — {fmt_number(linked)} / {fmt_number(ordered)} {order['unit'] or 'EA'} · {label}")
