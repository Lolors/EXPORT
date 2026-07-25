from __future__ import annotations

import streamlit as st

from components.case_selector import select_export_case
from services import export_service, history_service, packing_service
from services.packing_view_service import packing_summary
from utils.formatters import fmt_number


st.title('CTN 패킹')
st.caption('실제 출고제품을 기준으로 제품·수량과 CTN 번호를 연결하고, CTN별 규격과 무게를 입력합니다.')

cases = [
    case for case in export_service.active_cases()
    if str(case['stage'] or '').strip() in {'패킹 대기', '패킹 완료'}
]
if not cases:
    st.info('패킹 대기 또는 패킹 완료 단계인 수출 건이 없습니다.')
    st.stop()

saved_case_id = st.session_state.get('actual_packing_case_id')
case_id = select_export_case(
    cases,
    key_prefix='packing_export_selector',
    saved_case_id=saved_case_id,
    show_stage=True,
)
st.session_state['actual_packing_case_id'] = case_id

items = packing_service.list_items(case_id)
if not items:
    st.warning('연결된 입고 제품이 없습니다. 먼저 수출대기 입고에서 제품을 입력하세요.')
    st.stop()

summary = packing_summary(items)

m1, m2, m3, m4 = st.columns(4)
m1.metric('실제 출고 행', f"{summary['row_count']}개")
m2.metric('총 출고수량', fmt_number(summary['total_quantity']))
m3.metric('패킹 완료 행', f"{summary['packed_count']}개")
m4.metric('사용 CTN', f"{summary['box_count']}개")

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
    assign_clicked = st.button(
        '선택 제품을 CTN에 배정',
        type='primary',
        use_container_width=True,
    )

with partial_col:
    st.write('')
    st.write('')
    partial_clicked = st.button(
        '선택 제품의 일부만 CTN에 배정',
        use_container_width=True,
    )

if assign_clicked:
    if not selected_ids:
        st.error('CTN에 넣을 실제 출고제품을 선택하세요.')
    else:
        assigned_box_no = int(box_no)
        packing_service.assign_items(case_id, selected_ids, assigned_box_no)
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
    partial_item = next(
        (item for item in items if int(item['id']) == int(partial_item_id)),
        None,
    )
    if partial_item is None:
        st.session_state.pop('partial_pack_item_id', None)
        st.session_state.pop('partial_pack_box_no', None)
    else:
        @st.dialog('선택 제품 일부 수량 배정')
        def partial_assign_dialog() -> None:
            total_quantity = int(float(partial_item['requested_qty'] or 0))
            target_box_no = int(st.session_state.get('partial_pack_box_no', next_box))
            unit = partial_item['unit'] if 'unit' in partial_item.keys() else ''
            st.write(f"**{partial_item['product_name']}**")
            st.caption(
                f'남은 출고수량 {fmt_number(total_quantity)} {unit} · '
                f'배정 대상 CTN {target_box_no}'
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
            if confirm_col.button(
                '일부 수량 배정',
                type='primary',
                use_container_width=True,
            ):
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
    history_service.add(case_id, 'CTN 배정 해제', f'{len(selected_ids)}개 실제 출고 행')
    st.success('선택한 제품의 CTN 배정을 해제했습니다.')
    st.rerun()

@st.fragment
def render_ctn_management() -> None:
    st.divider()
    st.markdown('#### CTN 정보')
    boxes = packing_service.list_boxes(case_id)
    if not boxes:
        st.info('아직 생성된 CTN이 없습니다. 위에서 제품을 CTN에 배정하면 프리셋과 연속 적용을 사용할 수 있습니다.')
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
        pending_selector_key = f'pending_{selector_key}'
        pending_selector = st.session_state.pop(pending_selector_key, None)
        if pending_selector in box_labels:
            st.session_state[selector_key] = pending_selector
        elif st.session_state.get(selector_key) not in box_labels:
            st.session_state[selector_key] = default_box_label

        left_column, right_column = st.columns([6, 4], gap='large')

        with left_column:
            selected_box_label = st.selectbox('CTN 선택', box_labels, key=selector_key)
            selected_box_no = box_options[selected_box_label]
            box = next(box for box in boxes if int(box['box_no']) == selected_box_no)
            box_items = [
                item for item in items
                if item['box_no'] is not None and int(item['box_no']) == selected_box_no
            ]
            box_qty = sum(float(item['requested_qty'] or 0) for item in box_items)

            st.caption(f'{selected_box_label} · {len(box_items)}개 행 · 수량 {fmt_number(box_qty)}')
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
            active_values_key = f'active_box_values_{case_id}'
            continuous_key = f'continuous_box_preset_{case_id}'

            active_values = st.session_state.get(active_values_key)
            box_is_blank = not any(
                float(box[field] or 0) > 0
                for field in ['length_cm', 'width_cm', 'height_cm', 'weight_kg']
            )
            if (
                pending_values_key not in st.session_state
                and st.session_state.get(continuous_key, False)
                and active_values
                and box_is_blank
            ):
                st.session_state[pending_values_key] = active_values

            if pending_values_key in st.session_state:
                pending_values = st.session_state.pop(pending_values_key)
                st.session_state[length_key] = float(pending_values['length_cm'])
                st.session_state[width_key] = float(pending_values['width_cm'])
                st.session_state[height_key] = float(pending_values['height_cm'])
                st.session_state[weight_key] = float(pending_values['weight_kg'])

            with st.form(f'box_info_{case_id}_{box["id"]}'):
                c1, c2, c3, c4 = st.columns(4)
                length = c1.number_input('가로(cm)', min_value=0.0, value=float(box['length_cm'] or 0), key=length_key)
                width = c2.number_input('세로(cm)', min_value=0.0, value=float(box['width_cm'] or 0), key=width_key)
                height = c3.number_input('높이(cm)', min_value=0.0, value=float(box['height_cm'] or 0), key=height_key)
                weight = c4.number_input('무게(kg)', min_value=0.0, value=float(box['weight_kg'] or 0), key=weight_key)
                _, save_button_col, _ = st.columns([1, 1, 1])
                with save_button_col:
                    save_box = st.form_submit_button('CTN 정보 저장', type='primary', use_container_width=True)

            if save_box:
                packing_service.update_box(int(box['id']), length, width, height, weight)
                packing_service.save_last_box_values(length, width, height, weight)
                history_service.add(case_id, 'CTN 정보 수정', selected_box_label)
                current_values = {
                    'length_cm': float(length),
                    'width_cm': float(width),
                    'height_cm': float(height),
                    'weight_kg': float(weight),
                }
                st.session_state[active_values_key] = current_values

                if st.session_state.get(continuous_key, False):
                    current_index = box_labels.index(selected_box_label)
                    if current_index + 1 < len(box_labels):
                        next_label = box_labels[current_index + 1]
                        next_box_no = box_options[next_label]
                        next_box = next(
                            box_row for box_row in boxes
                            if int(box_row['box_no']) == next_box_no
                        )
                        st.session_state[f'pending_box_values_{next_box["id"]}'] = current_values
                        st.session_state[pending_selector_key] = next_label
                        st.success(f'{selected_box_label} 저장 완료. {next_label}에 같은 값을 자동 적용했습니다.')
                        st.rerun()

                st.success(f'{selected_box_label} 정보가 저장됐습니다.')

        with right_column:
            st.markdown('##### 박스 프리셋 및 연속 적용')
            st.caption('자주 쓰는 박스 규격과 무게를 저장하고, 연속 적용을 켜면 다음 CTN에도 같은 값이 자동 입력됩니다.')

            presets = packing_service.list_box_presets()
            last_values = packing_service.get_last_box_values()
            preset_labels = ['선택 안 함']
            if last_values is not None:
                preset_labels.append('마지막 사용값')
            preset_labels.extend(sorted(presets))

            selected_preset = st.selectbox('박스 프리셋', preset_labels, key=f'box_preset_select_{case_id}')
            preset_buttons = st.columns(3)
            apply_preset = preset_buttons[0].button('적용', use_container_width=True)
            save_preset_open = preset_buttons[1].button('현재 값 저장', use_container_width=True)
            delete_preset = preset_buttons[2].button(
                '삭제',
                use_container_width=True,
                disabled=selected_preset not in presets,
            )
            continuous_apply = st.toggle(
                '연속 적용',
                key=continuous_key,
                help='현재 적용한 규격과 무게를 다음 CTN에 자동으로 입력합니다.',
            )

            if continuous_apply and active_values:
                st.info('연속 적용 중입니다. CTN 정보를 저장하면 다음 CTN으로 이동하면서 같은 값이 자동 입력됩니다.')

            if apply_preset:
                values = None
                if selected_preset == '마지막 사용값':
                    values = last_values
                elif selected_preset in presets:
                    values = presets[selected_preset]
                if values is None:
                    st.warning('적용할 프리셋을 선택하세요.')
                else:
                    st.session_state[active_values_key] = values
                    st.session_state[pending_values_key] = values
                    st.success(f'{selected_preset} 값을 적용했습니다.')
                    st.rerun()

            if delete_preset and selected_preset in presets:
                packing_service.delete_box_preset(selected_preset)
                st.session_state.pop(f'box_preset_select_{case_id}', None)
                st.success(f'{selected_preset} 프리셋을 삭제했습니다.')
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

            st.divider()
            st.markdown('##### CTN 구성 복제')
            st.caption('현재 CTN의 제품 구성과 박스 규격·무게를 그대로 복제합니다.')
            clone_count = st.number_input(
                '복제할 CTN 개수',
                min_value=1,
                step=1,
                value=1,
                key=f'clone_count_{case_id}_{selected_box_no}',
            )
            clone_clicked = st.button('CTN 구성 복제', type='primary', use_container_width=True)

            if clone_clicked:
                try:
                    created_boxes = packing_service.clone_box(case_id, selected_box_no, int(clone_count))
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    created_text = ', '.join(f'CTN {number}' for number in created_boxes)
                    history_service.add(case_id, 'CTN 구성 복제', f'{selected_box_label} → {created_text}')
                    st.session_state[pending_selector_key] = f'CTN {created_boxes[0]}'
                    st.success(f'{created_text}을 생성했습니다.')
                    st.rerun()

        st.divider()
        st.markdown(
            """
            <style>
            div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#ctn-delete-anchor) {
                width: 60vw !important;
                max-width: 60vw !important;
            }
            @media(max-width:900px) {
                div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#ctn-delete-anchor) {
                    width: 100% !important;
                    max-width: 100% !important;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        with st.container():
            st.markdown('<span id="ctn-delete-anchor"></span>', unsafe_allow_html=True)
            st.markdown('#### CTN 삭제')
            st.caption('삭제할 CTN을 복수 선택할 수 있습니다. 삭제된 CTN의 제품은 다시 미패킹 상태로 돌아갑니다.')
            show_delete_tools = st.toggle('CTN 삭제 도구 열기', value=False, key=f'ctn_delete_tools_{case_id}')

            if show_delete_tools:
                delete_boxes = boxes
                delete_items_by_box: dict[int, list] = {}
                for delete_item_row in items:
                    raw_delete_box_no = delete_item_row['box_no']
                    if raw_delete_box_no is not None:
                        delete_items_by_box.setdefault(int(raw_delete_box_no), []).append(delete_item_row)
                delete_rows = []
                for delete_box in delete_boxes:
                    delete_box_no = int(delete_box['box_no'])
                    delete_items = delete_items_by_box.get(delete_box_no, [])
                    product_names = []
                    for delete_item in delete_items:
                        name = str(delete_item['product_name'] or '').strip() or '-'
                        if name not in product_names:
                            product_names.append(name)
                    if len(product_names) > 2:
                        product_summary = f'{product_names[0]}, {product_names[1]} 외 {len(product_names) - 2}품목'
                    else:
                        product_summary = ', '.join(product_names) or '-'
                    delete_box_id = int(delete_box['id'])
                    length_value = st.session_state.get(f'len_{delete_box_id}', delete_box['length_cm'])
                    width_value = st.session_state.get(f'wid_{delete_box_id}', delete_box['width_cm'])
                    height_value = st.session_state.get(f'hei_{delete_box_id}', delete_box['height_cm'])
                    weight_value = st.session_state.get(f'wei_{delete_box_id}', delete_box['weight_kg'])
                    dimensions = [length_value, width_value, height_value]
                    size_text = ' × '.join(fmt_number(value) for value in dimensions)
                    weight_text = f'{fmt_number(weight_value)} kg'
                    delete_rows.append({
                        '삭제': False,
                        '_box_no': delete_box_no,
                        'CTN': f'CTN {delete_box_no}',
                        '가로 × 세로 × 높이': size_text,
                        'GW': weight_text,
                        '포함된 제품요약': product_summary,
                    })

                delete_table_signature = '|'.join(
                    f"{row['_box_no']}:{row['가로 × 세로 × 높이']}:{row['GW']}"
                    for row in delete_rows
                )
                delete_table_key = f'ctn_delete_table_{case_id}_{delete_table_signature}'

                edited_delete_rows = st.data_editor(
                    delete_rows,
                    hide_index=True,
                    use_container_width=True,
                    disabled=['CTN', '가로 × 세로 × 높이', 'GW', '포함된 제품요약'],
                    column_config={
                        '삭제': st.column_config.CheckboxColumn('삭제'),
                        '_box_no': None,
                        'CTN': st.column_config.TextColumn('CTN'),
                        '가로 × 세로 × 높이': st.column_config.TextColumn('가로 × 세로 × 높이'),
                        'GW': st.column_config.TextColumn('GW'),
                        '포함된 제품요약': st.column_config.TextColumn('포함된 제품요약'),
                    },
                    key=delete_table_key,
                )
                selected_delete_boxes = [
                    int(row['_box_no'])
                    for row in edited_delete_rows
                    if bool(row.get('삭제'))
                ]
                delete_button = st.button(
                    f'선택한 CTN 삭제 ({len(selected_delete_boxes)}개)',
                    type='primary',
                    disabled=not selected_delete_boxes,
                    use_container_width=True,
                )
                if delete_button:
                    for delete_box_no in selected_delete_boxes:
                        packing_service.clear_box(case_id, delete_box_no)
                    deleted_text = ', '.join(f'CTN {number}' for number in selected_delete_boxes)
                    history_service.add(case_id, 'CTN 삭제', deleted_text)
                    st.session_state.pop(selector_key, None)
                    st.session_state.pop(delete_table_key, None)
                    st.success(f'{deleted_text}을 삭제했습니다. 포함 제품은 미패킹 상태로 돌아갔습니다.')
                    st.rerun()



render_ctn_management()

st.caption(f'현재 미패킹 실제 출고 행: {unpacked_count}개')
