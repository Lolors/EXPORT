from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

selector_replacement = r'''cases = [
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
'''

selector_pattern = (
    r'cases = \[.*?'
    r"st\.session_state\['actual_packing_case_id'\] = case_id\n"
)
patched, selector_count = re.subn(
    selector_pattern,
    lambda _match: selector_replacement,
    source,
    count=1,
    flags=re.S,
)
if selector_count != 1:
    raise RuntimeError('박스 패킹 수출 건 선택 영역을 교체하지 못했습니다.')

ctn_replacement = r'''st.divider()
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
        box_items = packing_service.list_box_items(case_id, selected_box_no)
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
            folder_service.sync_case_folder(case_id)
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
                folder_service.sync_case_folder(case_id)
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

        delete_rows = []
        for delete_box in boxes:
            delete_box_no = int(delete_box['box_no'])
            delete_items = packing_service.list_box_items(case_id, delete_box_no)
            product_names = []
            for delete_item in delete_items:
                name = str(delete_item['product_name'] or '').strip() or '-'
                if name not in product_names:
                    product_names.append(name)
            if len(product_names) > 2:
                product_summary = f'{product_names[0]}, {product_names[1]} 외 {len(product_names) - 2}품목'
            else:
                product_summary = ', '.join(product_names) or '-'
            dimensions = [delete_box['length_cm'], delete_box['width_cm'], delete_box['height_cm']]
            size_text = ' × '.join(fmt_number(value) for value in dimensions) if all(value not in (None, '') for value in dimensions) else '-'
            weight_text = f'{fmt_number(delete_box["weight_kg"])} kg' if delete_box['weight_kg'] not in (None, '') else '-'
            delete_rows.append({
                '삭제': False,
                '_box_no': delete_box_no,
                'CTN': f'CTN {delete_box_no}',
                '가로 × 세로 × 높이': size_text,
                'GW': weight_text,
                '포함된 제품요약': product_summary,
            })

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
            key=f'ctn_delete_table_{case_id}',
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
            folder_service.sync_case_folder(case_id)
            deleted_text = ', '.join(f'CTN {number}' for number in selected_delete_boxes)
            history_service.add(case_id, 'CTN 삭제', deleted_text)
            st.session_state.pop(selector_key, None)
            st.session_state.pop(f'ctn_delete_table_{case_id}', None)
            st.success(f'{deleted_text}을 삭제했습니다. 포함 제품은 미패킹 상태로 돌아갔습니다.')
            st.rerun()

st.caption(f'현재 미패킹 실제 출고 행: {unpacked_count}개')'''

ctn_pattern = r"st\.divider\(\)\nst\.markdown\('#### CTN 정보'\).*?st\.caption\(f'현재 미패킹 실제 출고 행: \{unpacked_count\}개'\)"
patched, ctn_count = re.subn(
    ctn_pattern,
    lambda _match: ctn_replacement,
    patched,
    count=1,
    flags=re.S,
)
if ctn_count != 1:
    raise RuntimeError('CTN 정보 영역을 교체하지 못했습니다.')

exec(compile(patched, str(SOURCE_PATH), 'exec'), globals(), globals())