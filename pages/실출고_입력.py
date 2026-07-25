from __future__ import annotations

import pandas as pd
import streamlit as st

from components.editors import order_editor, shipment_editor
from services import (
    export_service,
    folder_service,
    history_service,
    order_save_guard,
    order_service,
    shipment_service,
)
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
st.caption('왼쪽에서 주문목록을 수정하고, 오른쪽에서 주문을 선택해 실제 수출대기 입고제품을 입력합니다.')

cases = export_service.active_cases()
if not cases:
    st.info('진행 중인 수출 건이 없습니다.')
    st.stop()

case_by_id = {int(case['id']): case for case in cases}
case_ids = list(case_by_id)
case_id = st.selectbox(
    '수출 건 선택',
    case_ids,
    format_func=lambda value: case_label(case_by_id[int(value)]),
    key='linked_shipment_case',
)

st.session_state['actual_packing_case_id'] = case_id

shipment_service.cleanup_invalid_links(case_id)
orders = order_service.list_for_case(case_id)

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

left, right = st.columns([1.05, 1.45], gap='large')

with left:
    st.markdown('### 주문목록')
    st.caption('제품명·주문수량·단위·매입가를 수정한 뒤 저장할 수 있습니다.')

    draft_key = f'shipment_order_draft_{case_id}'
    version_key = f'shipment_order_editor_version_{case_id}'
    merge_message_key = f'shipment_order_merge_message_{case_id}'

    if merge_message := st.session_state.pop(merge_message_key, None):
        st.success(merge_message)

    if draft_key not in st.session_state:
        order_source = order_service.get_order_items_dataframe(case_id)
        if order_source.empty:
            order_source = pd.DataFrame([
                {'_id': None, '제품명': '', '수량': 0.0, '단위': 'EA', '매입가': 0.0}
            ])
        st.session_state[draft_key] = order_save_guard.with_row_numbers(order_source)

    editor_version = int(st.session_state.get(version_key, 0))
    edited_orders = order_editor(
        st.session_state[draft_key],
        key=f'shipment_orders_{case_id}_{editor_version}',
    )
    numbered_orders = order_save_guard.with_row_numbers(
        edited_orders.drop(columns=['행번호'], errors='ignore')
    )
    duplicate_order_rows = order_save_guard.find_duplicate_rows(numbered_orders)

    if duplicate_order_rows:
        order_save_guard.render_duplicate_notice(duplicate_order_rows)
        st.markdown('**중복된 행끼리 수량을 합칠까요?**')
        st.caption('가장 먼저 생성된 행의 제품명·단위·매입가를 보존하고, 수량만 모두 더한 뒤 나중 행을 삭제합니다.')
        if st.button(
            '중복 행 수량 합치기',
            type='secondary',
            use_container_width=True,
            key=f'merge_duplicate_orders_{case_id}_{editor_version}',
        ):
            merged_orders = order_save_guard.merge_duplicate_rows(numbered_orders)
            st.session_state[draft_key] = merged_orders
            st.session_state[version_key] = editor_version + 1
            st.session_state[merge_message_key] = '중복 행을 합쳤습니다. 합산된 수량을 확인한 뒤 주문목록을 저장하세요.'
            st.rerun()

    st.caption('주문행을 삭제하고 저장하면 그 주문에 연결된 실제 출고제품도 함께 삭제됩니다.')

    if st.button(
        '주문목록 저장',
        type='primary',
        use_container_width=True,
        disabled=bool(duplicate_order_rows),
        key=f'save_shipment_orders_{case_id}',
    ):
        try:
            order_service.save_order_items(case_id, numbered_orders)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.pop(draft_key, None)
            st.session_state[version_key] = editor_version + 1
            folder_service.sync_case_folder(case_id)
            history_service.add(case_id, '출고 단계 주문목록 수정', f'{len(numbered_orders)}개 행')
            st.success('주문목록을 저장했습니다.')
            st.rerun()

with right:
    st.markdown('### 실제 수출대기 입고제품')

    if not orders:
        st.info('왼쪽에서 주문목록을 입력하고 저장하세요.')
    else:
        order_options: dict[str, int] = {}
        for order in orders:
            order_id = int(order['id'])
            order_qty = safe_number(order['quantity'])
            unit = str(order['unit'] or 'EA')
            current_rows = shipment_service.list_linked(case_id, order_id)
            linked_qty = sum(safe_number(row['requested_qty']) for row in current_rows)
            icon, _ = order_state(order_qty, linked_qty)
            label = (
                f"{icon} {order['product_name']} · "
                f"{fmt_number(linked_qty)} / {fmt_number(order_qty)} {unit}"
            )
            order_options[label] = order_id

        selected_label = st.selectbox(
            '출고제품을 입력할 주문',
            list(order_options),
            key=f'linked_selected_order_{case_id}',
        )
        selected_order_id = order_options[selected_label]
        selected_order = next(order for order in orders if int(order['id']) == selected_order_id)
        order_qty = safe_number(selected_order['quantity'])
        unit = str(selected_order['unit'] or 'EA')
        current = shipment_service.list_linked(case_id, selected_order_id)

        st.markdown(f"**선택 주문:** {selected_order['product_name']}")

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
                '실제 제품명': selected_order['product_name'] or '',
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
