from __future__ import annotations

import pandas as pd
import streamlit as st

from components.editors import shipment_editor
from services import export_service, folder_service, history_service, order_service, shipment_service
from utils.formatters import case_label, fmt_number


def order_state(order_qty: float, linked_qty: float) -> tuple[str, str]:
    if order_qty > 0 and linked_qty >= order_qty:
        return '🟢', '입고 완료'
    if linked_qty > 0:
        return '🟡', '일부 입고'
    return '🔴', '미입고'


st.title('수출대기 입고')
st.caption('주문품목별로 수출대기 위치에 입고할 제품의 사업장, 제품명, 제조번호, 유통기한과 수량을 연결합니다.')

cases = export_service.active_cases()
if not cases:
    st.info('진행 중인 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
case_id = options[st.selectbox('수출 건 선택', list(options), key='linked_shipment_case')]
shipment_service.cleanup_invalid_links(case_id)
orders = order_service.list_for_case(case_id)

if not orders:
    st.warning('먼저 주문품목을 입력하세요.')
    st.stop()

unlinked_count = shipment_service.count_unlinked(case_id)
if unlinked_count:
    st.warning(
        f'구형 입고 데이터 중 주문품목에 연결되지 않은 행이 {unlinked_count}개 있습니다. '
        '이 데이터는 현재 주문품목별 입고 화면에 표시되지 않으며, 필요하지 않다면 아래에서 삭제할 수 있습니다.'
    )
    with st.expander('구형 미연결 입고 데이터 정리', expanded=True):
        legacy_rows = shipment_service.list_unlinked(case_id)
        st.dataframe(
            [
                {
                    '사업장': row['business_unit'],
                    '실제 제품명': row['product_name'],
                    '제조번호': row['lot_no'],
                    '유통기한': row['expiry_date'],
                    '입고수량': row['requested_qty'],
                    '박스번호': row['box_no'],
                }
                for row in legacy_rows
            ],
            hide_index=True,
            use_container_width=True,
        )
        delete_confirmed = st.checkbox(
            f'위 구형 미연결 데이터 {unlinked_count}개를 삭제합니다.',
            key=f'delete_legacy_confirm_{case_id}',
        )
        if st.button(
            '구형 미연결 데이터 삭제',
            disabled=not delete_confirmed,
            key=f'delete_legacy_{case_id}',
        ):
            shipment_service.delete_unlinked(case_id)
            folder_service.sync_case_folder(case_id)
            history_service.add(case_id, '구형 미연결 입고 삭제', f'{unlinked_count}개 행')
            st.success('구형 미연결 입고 데이터를 삭제했습니다.')
            st.rerun()

for order in orders:
    order_id = int(order['id'])
    order_qty = float(order['quantity'] or 0)
    unit = str(order['unit'] or 'EA')
    current = shipment_service.list_linked(case_id, order_id)
    linked_qty = sum(float(row['requested_qty'] or 0) for row in current)
    icon, state = order_state(order_qty, linked_qty)

    with st.expander(
        f"{icon} {order['product_name']} · 주문 {fmt_number(order_qty)} {unit} · 입고 {fmt_number(linked_qty)} {unit} · {state}",
        expanded=linked_qty < order_qty,
    ):
        st.caption('한 주문품목에 실제 제품이나 제조번호가 여러 개면 행을 추가해 각각 입력하세요.')

        if current:
            source = pd.DataFrame([
                {
                    '사업장': row['business_unit'] or '',
                    '실제 제품명': row['product_name'] or '',
                    '제조번호': row['lot_no'] or '',
                    '유통기한': row['expiry_date'] or '',
                    '입고수량': float(row['requested_qty'] or 0),
                }
                for row in current
            ])
        else:
            source = pd.DataFrame([{
                '사업장': '',
                '실제 제품명': '',
                '제조번호': '',
                '유통기한': '',
                '입고수량': 0.0,
            }])

        edited = shipment_editor(source.rename(columns={'입고수량': '출고수량'}), key=f'linked_order_editor_{order_id}')
        preview_qty = sum(float(value or 0) for value in edited.get('출고수량', []))
        preview_icon, preview_state = order_state(order_qty, preview_qty)
        st.info(f'{preview_icon} 입력 합계 {fmt_number(preview_qty)} / 주문 {fmt_number(order_qty)} {unit} · {preview_state}')

        if st.button('이 주문품목의 입고 저장', type='primary', key=f'save_linked_order_{order_id}'):
            values: list[dict] = []
            for _, row in edited.iterrows():
                actual_name = str(row.get('실제 제품명', '') or '').strip()
                quantity = float(row.get('출고수량', 0) or 0)
                has_any_value = any(
                    str(row.get(column, '') or '').strip()
                    for column in ['사업장', '실제 제품명', '제조번호', '유통기한']
                ) or quantity > 0
                if not has_any_value:
                    continue
                values.append({
                    'business_unit': row.get('사업장', ''),
                    'product_name': actual_name,
                    'lot_no': row.get('제조번호', ''),
                    'expiry_date': row.get('유통기한', ''),
                    'requested_qty': quantity,
                })

            try:
                shipment_service.save_for_order(case_id, order_id, values)
            except ValueError as exc:
                st.error(str(exc))
            else:
                folder_service.sync_case_folder(case_id)
                history_service.add(
                    case_id,
                    '주문품목별 입고 저장',
                    f"{order['product_name']} · {fmt_number(preview_qty)} / {fmt_number(order_qty)} {unit}",
                )
                st.success('저장했습니다.')
                st.rerun()

st.divider()
st.caption(f'현재 주문품목에 연결된 전체 입고 수량: {fmt_number(shipment_service.total_linked_quantity(case_id))}')
