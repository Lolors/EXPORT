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


def safe_number(value: object) -> float:
    try:
        if value is None or pd.isna(value) or value == '':
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


st.title('수출대기 입고')
st.caption('왼쪽 주문목록에서 한 행을 선택하고, 오른쪽에서 실제 수출대기 위치에 입고된 제품을 입력합니다.')

cases = export_service.active_cases()
if not cases:
    st.info('진행 중인 수출 건이 없습니다.')
    st.stop()

options = {
    f"{case_label(case)} · ID {int(case['id'])}": int(case['id'])
    for case in cases
}
selected_case_label = st.selectbox('수출 건 선택', list(options), key='linked_shipment_case')
case_id = options[selected_case_label]

st.session_state['actual_packing_case_id'] = case_id

shipment_service.cleanup_invalid_links(case_id)
orders = order_service.list_for_case(case_id)
if not orders:
    st.warning('먼저 주문품목을 입력하세요.')
    st.stop()

unlinked_count = shipment_service.count_unlinked(case_id)
if unlinked_count:
    with st.expander(f'구형 미연결 입고 데이터 {unlinked_count}개 정리'):
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
            '위 미연결 데이터를 삭제합니다.',
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

selected_order_key = f'linked_selected_order_{case_id}'
order_ids = [int(order['id']) for order in orders]
if st.session_state.get(selected_order_key) not in order_ids:
    st.session_state[selected_order_key] = order_ids[0]


def choose_order(order_id: int) -> None:
    checkbox_key = f'linked_order_check_{case_id}_{order_id}'
    if st.session_state.get(checkbox_key):
        st.session_state[selected_order_key] = order_id
        for other_id in order_ids:
            if other_id != order_id:
                st.session_state[f'linked_order_check_{case_id}_{other_id}'] = False
    elif st.session_state.get(selected_order_key) == order_id:
        st.session_state[checkbox_key] = True


for order_id in order_ids:
    checkbox_key = f'linked_order_check_{case_id}_{order_id}'
    st.session_state[checkbox_key] = st.session_state.get(selected_order_key) == order_id

left, right = st.columns([0.9, 1.45], gap='large')

with left:
    st.markdown('### 주문목록')
    st.caption('체크한 주문품목의 실제 입고 내역이 오른쪽에 표시됩니다.')

    header = st.columns([0.45, 2.3, 0.8, 0.8])
    for column, title in zip(header, ['선택', '제품명', '주문', '상태']):
        column.markdown(f'**{title}**')

    for order in orders:
        order_id = int(order['id'])
        order_qty = safe_number(order['quantity'])
        unit = str(order['unit'] or 'EA')
        current = shipment_service.list_linked(case_id, order_id)
        linked_qty = sum(safe_number(row['requested_qty']) for row in current)
        icon, state = order_state(order_qty, linked_qty)

        row_cols = st.columns([0.45, 2.3, 0.8, 0.8])
        row_cols[0].checkbox(
            '선택',
            key=f'linked_order_check_{case_id}_{order_id}',
            label_visibility='collapsed',
            on_change=choose_order,
            args=(order_id,),
        )
        row_cols[1].write(str(order['product_name'] or '-'))
        row_cols[2].write(f'{fmt_number(order_qty)} {unit}')
        row_cols[3].write(f'{icon} {state}')
        row_cols[1].caption(f'입고 {fmt_number(linked_qty)} {unit}')

with right:
    selected_order_id = int(st.session_state[selected_order_key])
    selected_order = next(order for order in orders if int(order['id']) == selected_order_id)
    order_qty = safe_number(selected_order['quantity'])
    unit = str(selected_order['unit'] or 'EA')
    current = shipment_service.list_linked(case_id, selected_order_id)
    linked_qty = sum(safe_number(row['requested_qty']) for row in current)
    icon, state = order_state(order_qty, linked_qty)

    st.markdown('### 실제 수출대기 입고제품')
    st.markdown(f"**선택 주문:** {selected_order['product_name']}")
    st.caption(
        f'주문 {fmt_number(order_qty)} {unit} · 현재 입고 {fmt_number(linked_qty)} {unit} · {icon} {state}'
    )
    st.caption('실제 제품이나 제조번호가 여러 개면 행을 추가해 각각 입력하세요.')

    if current:
        source = pd.DataFrame([
            {
                '사업장': row['business_unit'] or '',
                '실제 제품명': row['product_name'] or '',
                '제조번호': row['lot_no'] or '',
                '유통기한': row['expiry_date'] or '',
                '출고수량': safe_number(row['requested_qty']),
            }
            for row in current
        ])
    else:
        source = pd.DataFrame([{
            '사업장': '',
            '실제 제품명': '',
            '제조번호': '',
            '유통기한': '',
            '출고수량': 0.0,
        }])

    edited = shipment_editor(source, key=f'linked_order_editor_{case_id}_{selected_order_id}')
    preview_qty = sum(safe_number(value) for value in edited.get('출고수량', []))
    preview_icon, preview_state = order_state(order_qty, preview_qty)
    st.info(
        f'{preview_icon} 입력 합계 {fmt_number(preview_qty)} / '
        f'주문 {fmt_number(order_qty)} {unit} · {preview_state}'
    )

    if st.button(
        '선택 주문품목 입고 저장',
        type='primary',
        use_container_width=True,
        key=f'save_linked_order_{case_id}_{selected_order_id}',
    ):
        values: list[dict] = []
        for _, row in edited.iterrows():
            actual_name = str(row.get('실제 제품명', '') or '').strip()
            quantity = safe_number(row.get('출고수량', 0))
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
            shipment_service.save_for_order(case_id, selected_order_id, values)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state['actual_packing_case_id'] = case_id
            folder_service.sync_case_folder(case_id)
            history_service.add(
                case_id,
                '주문품목별 입고 저장',
                f"{selected_order['product_name']} · {fmt_number(preview_qty)} / {fmt_number(order_qty)} {unit}",
            )
            st.success('저장했습니다. 박스 패킹에 바로 반영됩니다.')
            st.rerun()

st.divider()
st.caption(
    f'현재 주문품목에 연결된 전체 입고 수량: '
    f'{fmt_number(shipment_service.total_linked_quantity(case_id))}'
)
