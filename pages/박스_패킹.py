from __future__ import annotations

import time

import streamlit as st
from services import export_service, folder_service, history_service, packing_service
from utils.formatters import case_label, fmt_number


st.title('CTN 패킹')
st.caption('실제 출고제품을 기준으로 제품·수량과 CTN 번호를 연결하고, CTN별 규격과 무게를 입력합니다.')

cases = export_service.active_cases()
if not cases:
    st.info('진행 중 수출 건이 없습니다.')
    st.stop()

options = {case_label(case): int(case['id']) for case in cases}
option_labels = list(options)
saved_case_id = st.session_state.get('actual_packing_case_id')
default_index = 0
if saved_case_id is not None:
    for index, label in enumerate(option_labels):
        if options[label] == int(saved_case_id):
            default_index = index
            break
selected_case_label = st.selectbox('수출 건 선택', option_labels, index=default_index, key='actual_packing_case')
case_id = options[selected_case_label]
st.session_state['actual_packing_case_id'] = case_id

items = packing_service.list_items(case_id)
if not items:
    st.warning('연결된 입고 제품이 없습니다. 먼저 수출대기 입고에서 제품을 입력하세요.')
    st.stop()

unpacked_count = sum(1 for item in items if item['box_no'] is None)
packed_count = len(items) - unpacked_count
box_count = len({item['box_no'] for item in items if item['box_no'] is not None})
total_qty = sum(float(item['requested_qty'] or 0) for item in items)

m1, m2, m3, m4 = st.columns(4)
m1.metric('실제 출고 행', f'{len(items)}개')
m2.metric('총 출고수량', fmt_number(total_qty))
m3.metric('패킹 완료 행', f'{packed_count}개')
m4.metric('사용 CTN', f'{box_count}개')

st.divider()
st.markdown('#### 실제 출고제품 선택')
st.caption('사업장·실제 제품명·제조번호·유통기한·출고수량을 확인한 뒤 CTN 번호를 배정하세요.')

header = st.columns([0.55, 1.15, 2.5, 1.35, 1.35, 0.9, 1.0])
for column, title in zip(
    header,
    ['선택', '사업장', '실제 제품명', '제조번호', '유통기한', '출고수량', '현재 CTN'],
):
    column.markdown(f'**{title}**')

selected_ids: list[int] = []
for item in items:
    checkbox_key = f'pack_select_{case_id}_{item["id"]}'
    cols = st.columns([0.55, 1.15, 2.5, 1.35, 1.35, 0.9, 1.0])
    selected = cols[0].checkbox(
        '선택',
        key=checkbox_key,
        label_visibility='collapsed',
    )
    if selected:
        selected_ids.append(int(item['id']))
    cols[1].write(item['business_unit'] or '-')
    cols[2].write(item['product_name'] or '-')
    cols[3].write(item['lot_no'] or '-')
    cols[4].write(item['expiry_date'] or '-')
    cols[5].write(fmt_number(item['requested_qty']))
    cols[6].write(f"CTN {item['box_no']}" if item['box_no'] is not None else '미패킹')

st.divider()
next_box = packing_service.next_box_no(case_id)
box_number_key = f'packing_box_no_{case_id}'
pending_box_number_key = f'pending_packing_box_no_{case_id}'
if pending_box_number_key in st.session_state:
    st.session_state[box_number_key] = int(st.session_state.pop(pending_box_number_key))
elif box_number_key not in st.session_state:
    st.session_state[box_number_key] = next_box
assign_col, full_col, partial_col = st.columns([1, 2, 2])
box_no = assign_col.number_input(
    '배정할 CTN 번호',
    min_value=1,
    step=1,
    key=box_number_key,
)

with full_col:
    st.write('')
    st.write('')
    assign_clicked = st.button('선택 제품을 CTN에 배정', type='primary', use_container_width=True)

with partial_col:
    st.write('')
    st.write('')
    partial_clicked = st.button('선택 제품의 일부만 CTN에 배정', use_container_width=True)

if assign_clicked:
    if not selected_ids:
        st.error('CTN에 넣을 실제 출고제품을 선택하세요.')
    else:
        assigned_box_no = int(box_no)
        packing_service.assign_items(case_id, selected_ids, assigned_box_no)
        folder_service.sync_case_folder(case_id)
        history_service.add(
            case_id,
            'CTN 패킹',
            f'{len(selected_ids)}개 실제 출고 행 → CTN {assigned_box_no}',
        )
        st.session_state[pending_box_number_key] = assigned_box_no + 1
        st.session_state[f'packing_box_detail_{case_id}'] = f'CTN {assigned_box_no}'
        for item_id in selected_ids:
            st.session_state.pop(f'pack_select_{case_id}_{item_id}', None)
        st.success(f'{len(selected_ids)}개 실제 출고 행을 CTN {assigned_box_no}에 배정했습니다.')
        st.rerun()

if partial_clicked:
    if not selected_ids:
        st.error('일부 수량을 배정할 실제 출고제품을 선택하세요.')
    elif len(selected_ids) > 1:
        st.error('일부 수량 배정은 실제 출고제품 한 개만 선택할 수 있습니다.')
    else:
        st.session_state['partial_pack_item_id'] = selected_ids[0]
        st.session_state['partial_pack_box_no'] = int(box_no)
        st.rerun()

partial_item_id = st.session_state.get('partial_pack_item_id')
if partial_item_id:
    partial_item = next((item for item in items if int(item['id']) == int(partial_item_id)), None)
    if partial_item is None:
        st.session_state.pop('partial_pack_item_id', None)
        st.session_state.pop('partial_pack_box_no', None)
    else:
        @st.dialog('선택 제품 일부 수량 배정')
        def partial_assign_dialog() -> None:
            total_quantity = int(float(partial_item['requested_qty'] or 0))
            target_box_no = int(st.session_state.get('partial_pack_box_no', next_box))
            st.write(f"**{partial_item['product_name']}**")
            st.caption(
                f"남은 출고수량 {fmt_number(total_quantity)} {partial_item['unit'] if 'unit' in partial_item.keys() else ''} · "
                f"배정 대상 CTN {target_box_no}"
            )
            quantity = st.number_input(
                'CTN에 배정할 수량',
                min_value=0,
                max_value=total_quantity,
                value=total_quantity,
                step=1,
                format='%d',
                key=f'partial_pack_qty_{case_id}_{partial_item_id}',
            )
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button('일부 수량 배정', type='primary', use_container_width=True):
                try:
                    packing_service.assign_partial_item(
                        case_id,
                        int(partial_item_id),
                        target_box_no,
                        int(quantity),
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    folder_service.sync_case_folder(case_id)
                    history_service.add(
                        case_id,
                        'CTN 일부 수량 배정',
                        f"{partial_item['product_name']} {fmt_number(quantity)} → CTN {target_box_no}",
                    )
                    st.session_state.pop('partial_pack_item_id', None)
                    st.session_state.pop('partial_pack_box_no', None)
                    st.session_state.pop(f'pack_select_{case_id}_{partial_item_id}', None)
                    st.session_state[pending_box_number_key] = target_box_no + 1
                    st.session_state[f'packing_box_detail_{case_id}'] = f'CTN {target_box_no}'
                    st.success(f'{fmt_number(quantity)}개를 CTN {target_box_no}에 배정했습니다.')
                    st.rerun()
            if cancel_col.button('취소', use_container_width=True):
                st.session_state.pop('partial_pack_item_id', None)
                st.session_state.pop('partial_pack_box_no', None)
                st.rerun()

        partial_assign_dialog()

if selected_ids and st.button('선택 제품 CTN 배정 해제'):
    packing_service.unassign_items(case_id, selected_ids)
    folder_service.sync_case_folder(case_id)
    history_service.add(case_id, 'CTN 배정 해제', f'{len(selected_ids)}개 실제 출고 행')
    st.success('선택한 제품의 CTN 배정을 해제했습니다.')
    st.rerun()

st.divider()
st.markdown('#### CTN 정보')
boxes = packing_service.list_boxes(case_id)
if not boxes:
    st.info('아직 생성된 CTN이 없습니다.')
else:
    box_options = {f"CTN {int(box['box_no'])}": int(box['box_no']) for box in boxes}
    box_labels = list(box_options)
    incomplete_labels = [
        label
        for label, box_number in box_options.items()
        if not all(
            float(next(box for box in boxes if int(box['box_no']) == box_number)[field] or 0) > 0
            for field in ['length_cm', 'width_cm', 'height_cm', 'weight_kg']
        )
    ]
    default_box_label = incomplete_labels[0] if incomplete_labels else box_labels[0]
    selector_key = f'packing_box_detail_{case_id}'
    if st.session_state.get(selector_key) not in box_labels:
        st.session_state[selector_key] = default_box_label

    selected_box_label = st.selectbox(
        'CTN 선택',
        box_labels,
        key=selector_key,
    )
    selected_box_no = box_options[selected_box_label]
    box = next(box for box in boxes if int(box['box_no']) == selected_box_no)
    box_items = packing_service.list_box_items(case_id, selected_box_no)
    box_qty = sum(float(item['requested_qty'] or 0) for item in box_items)

    st.caption(f"{selected_box_label} · {len(box_items)}개 행 · 수량 {fmt_number(box_qty)}")
    if box_items:
        st.dataframe(
            [
                {
                    '사업장': item['business_unit'],
                    '실제 제품명': item['product_name'],
                    '제조번호': item['lot_no'],
                    '유통기한': item['expiry_date'],
                    '수량': item['requested_qty'],
                }
                for item in box_items
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption('이 CTN에 연결된 제품이 없습니다.')

    length_key = f'len_{box["id"]}'
    width_key = f'wid_{box["id"]}'
    height_key = f'hei_{box["id"]}'
    weight_key = f'wei_{box["id"]}'
    pending_values_key = f'pending_box_values_{box["id"]}'
    if pending_values_key in st.session_state:
        pending_values = st.session_state.pop(pending_values_key)
        st.session_state[length_key] = pending_values['length_cm']
        st.session_state[width_key] = pending_values['width_cm']
        st.session_state[height_key] = pending_values['height_cm']
        st.session_state[weight_key] = pending_values['weight_kg']

    presets = packing_service.list_box_presets()
    last_values = packing_service.get_last_box_values()
    preset_labels = ['선택 안 함']
    if last_values is not None:
        preset_labels.append('마지막 사용값')
    preset_labels.extend(sorted(presets))

    preset_col, apply_col, save_col = st.columns([2.5, 1.2, 1.2])
    selected_preset = preset_col.selectbox(
        '박스 프리셋',
        preset_labels,
        key=f'box_preset_select_{case_id}',
    )
    apply_preset = apply_col.button('프리셋 적용', use_container_width=True)
    save_preset_open = save_col.button('현재 값 저장', use_container_width=True)
    continuous_apply = st.checkbox(
        '다음 CTN에도 계속 적용',
        key=f'continuous_box_preset_{case_id}',
    )

    if apply_preset:
        values = None
        if selected_preset == '마지막 사용값':
            values = last_values
        elif selected_preset in presets:
            values = presets[selected_preset]
        if values is None:
            st.warning('적용할 프리셋을 선택하세요.')
        else:
            st.session_state[pending_values_key] = values
            st.session_state[f'active_box_values_{case_id}'] = values
            st.rerun()

    if save_preset_open:
        st.session_state[f'show_preset_save_{case_id}'] = True

    if st.session_state.get(f'show_preset_save_{case_id}'):
        with st.form(f'box_preset_save_form_{case_id}_{box["id"]}'):
            preset_name = st.text_input('프리셋 이름')
            save_preset = st.form_submit_button('프리셋 저장', type='primary')
        if save_preset:
            try:
                packing_service.save_box_preset(
                    preset_name,
                    float(st.session_state.get(length_key, box['length_cm'] or 0)),
                    float(st.session_state.get(width_key, box['width_cm'] or 0)),
                    float(st.session_state.get(height_key, box['height_cm'] or 0)),
                    float(st.session_state.get(weight_key, box['weight_kg'] or 0)),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state.pop(f'show_preset_save_{case_id}', None)
                st.success(f'{preset_name.strip()} 프리셋을 저장했습니다.')
                st.rerun()

    with st.form(f'box_info_{case_id}_{box["id"]}'):
        c1, c2, c3, c4 = st.columns(4)
        length = c1.number_input('가로(cm)', min_value=0.0, value=float(box['length_cm'] or 0), key=length_key)
        width = c2.number_input('세로(cm)', min_value=0.0, value=float(box['width_cm'] or 0), key=width_key)
        height = c3.number_input('높이(cm)', min_value=0.0, value=float(box['height_cm'] or 0), key=height_key)
        weight = c4.number_input('무게(kg)', min_value=0.0, value=float(box['weight_kg'] or 0), key=weight_key)
        left_button_col, center_button_col, right_button_col = st.columns([1, 1, 1])
        with center_button_col:
            save_box = st.form_submit_button('CTN 정보 저장', type='primary', use_container_width=True)

    if save_box:
        packing_service.update_box(int(box['id']), length, width, height, weight)
        packing_service.save_last_box_values(length, width, height, weight)
        folder_service.sync_case_folder(case_id)
        history_service.add(case_id, 'CTN 정보 수정', selected_box_label)
        st.session_state[f'active_box_values_{case_id}'] = {
            'length_cm': float(length),
            'width_cm': float(width),
            'height_cm': float(height),
            'weight_kg': float(weight),
        }

        if continuous_apply:
            current_index = box_labels.index(selected_box_label)
            if current_index + 1 < len(box_labels):
                next_label = box_labels[current_index + 1]
                next_box_no = box_options[next_label]
                next_box = next(box for box in boxes if int(box['box_no']) == next_box_no)
                st.session_state[f'pending_box_values_{next_box["id"]}'] = st.session_state[f'active_box_values_{case_id}']
                st.session_state[selector_key] = next_label
                st.success(f'{selected_box_label} 저장 완료. {next_label}에 같은 값을 적용했습니다.')
                st.rerun()

        notice = st.empty()
        notice.success(f'{selected_box_label} 정보가 저장됐습니다.')
        time.sleep(2)
        notice.empty()

    st.markdown('##### CTN 구성 복제')
    st.caption('현재 CTN의 제품 구성과 박스 규격·무게를 그대로 복제합니다.')
    clone_col, clone_button_col = st.columns([1, 2])
    clone_count = clone_col.number_input(
        '복제할 CTN 개수',
        min_value=1,
        step=1,
        value=1,
        key=f'clone_count_{case_id}_{selected_box_no}',
    )
    with clone_button_col:
        st.write('')
        st.write('')
        clone_clicked = st.button('CTN 구성 복제', type='primary', use_container_width=True)

    if clone_clicked:
        try:
            created_boxes = packing_service.clone_box(case_id, selected_box_no, int(clone_count))
        except ValueError as exc:
            st.error(str(exc))
        else:
            folder_service.sync_case_folder(case_id)
            created_text = ', '.join(f'CTN {number}' for number in created_boxes)
            history_service.add(
                case_id,
                'CTN 구성 복제',
                f'{selected_box_label} → {created_text}',
            )
            st.session_state[selector_key] = f'CTN {created_boxes[0]}'
            st.success(f'{created_text}을 생성했습니다.')
            st.rerun()

st.caption(f'현재 미패킹 실제 출고 행: {unpacked_count}개')
