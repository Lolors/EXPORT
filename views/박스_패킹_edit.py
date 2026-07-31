from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

import_marker = 'from services import export_service, history_service, packing_service\n'
import_replacement = '''import db
from services import export_service, history_service, packing_edit_service, packing_service
from utils.dates import now_text
'''
if source.count(import_marker) != 1:
    raise RuntimeError('박스 패킹 서비스 import 구간을 찾지 못했습니다.')
source = source.replace(import_marker, import_replacement, 1)

layout_marker = "left_column, right_column = st.columns([7, 3], gap='large')"
layout_replacement = "left_column, right_column = st.columns([6, 4], gap='large')"
if source.count(layout_marker) != 1:
    raise RuntimeError('박스 패킹 좌우 영역 비율 구간을 찾지 못했습니다.')
source = source.replace(layout_marker, layout_replacement, 1)

style_marker = "st.title('CTN 패킹')\n"
style_replacement = '''st.title('CTN 패킹')
st.markdown(
    """
    <style>
    div[data-testid="stDataEditor"] {
        font-size: 0.76rem;
    }
    div[data-testid="stDataEditor"] [role="columnheader"],
    div[data-testid="stDataEditor"] [role="gridcell"] {
        font-size: 0.76rem !important;
        padding-left: 3px !important;
        padding-right: 3px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@db.backup_batch
def assign_repeated_ctns(
    case_id: int,
    item_id: int,
    *,
    quantity_per_box: int,
    length_cm: float,
    width_cm: float,
    height_cm: float,
    weight_kg: float,
) -> list[dict]:
    item = db.row(
        """SELECT id, case_id, order_item_id, business_unit, location, product_name,
                  lot_no, expiry_date, requested_qty, box_no, created_at
           FROM shipment_items
           WHERE id=? AND case_id=?""",
        (item_id, case_id),
    )
    if item is None:
        raise ValueError('선택한 실제 출고제품을 찾을 수 없습니다.')
    if item['box_no'] is not None:
        raise ValueError('이미 CTN에 담긴 제품은 반복 담기를 할 수 없습니다.')

    total_quantity = int(float(item['requested_qty'] or 0))
    if total_quantity <= 0:
        raise ValueError('남은 출고수량이 없습니다.')
    if quantity_per_box <= 0:
        raise ValueError('CTN당 수량은 1개 이상이어야 합니다.')

    full_count, remainder = divmod(total_quantity, quantity_per_box)
    quantities = [quantity_per_box] * full_count
    if remainder:
        quantities.append(remainder)
    if not quantities:
        quantities = [total_quantity]

    first_box_no = packing_service.next_box_no(case_id)
    target_box_numbers = [first_box_no + offset for offset in range(len(quantities))]
    placeholders = ','.join('?' for _ in target_box_numbers)
    occupied = db.rows(
        f'SELECT box_no FROM boxes WHERE case_id=? AND box_no IN ({placeholders})',
        (case_id, *target_box_numbers),
    )
    if occupied:
        raise ValueError('생성 예정 CTN 번호 중 이미 사용 중인 번호가 있습니다. 화면을 새로고침한 뒤 다시 시도하세요.')

    now = now_text()
    preview_rows: list[dict] = []
    for index, (box_no, quantity) in enumerate(zip(target_box_numbers, quantities)):
        is_remainder = remainder > 0 and index == len(quantities) - 1
        box_weight = 0.0 if is_remainder else float(weight_kg)
        db.execute(
            """INSERT INTO boxes(
                   case_id, box_no, length_cm, width_cm, height_cm, weight_kg, updated_at
               ) VALUES (?,?,?,?,?,?,?)""",
            (case_id, box_no, length_cm, width_cm, height_cm, box_weight, now),
        )

        if index == 0:
            db.execute(
                'UPDATE shipment_items SET requested_qty=?,box_no=?,updated_at=? WHERE id=? AND case_id=?',
                (quantity, box_no, now, item_id, case_id),
            )
        else:
            db.execute(
                """INSERT INTO shipment_items(
                       case_id, order_item_id, business_unit, location, product_name,
                       lot_no, expiry_date, requested_qty, box_no, created_at, updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    case_id,
                    item['order_item_id'],
                    item['business_unit'],
                    item['location'],
                    item['product_name'],
                    item['lot_no'],
                    item['expiry_date'],
                    quantity,
                    box_no,
                    item['created_at'] or now,
                    now,
                ),
            )

        preview_rows.append({
            'box_no': box_no,
            'quantity': quantity,
            'is_remainder': is_remainder,
            'weight_kg': box_weight,
        })

    packing_service._sync_packing_stage(case_id, now)
    return preview_rows
'''
if source.count(style_marker) != 1:
    raise RuntimeError('박스 패킹 제목 구간을 찾지 못했습니다.')
source = source.replace(style_marker, style_replacement, 1)

grid_config_marker = '''            '선택': st.column_config.CheckboxColumn('선택', width='small'),
            '_id': None,
            '사업장': st.column_config.TextColumn('사업장', width='small'),
            '실제 제품명': st.column_config.TextColumn('실제 제품명', width='large'),
            '제조번호': st.column_config.TextColumn('제조번호', width='medium'),
            '유통기한': st.column_config.TextColumn('유통기한', width='medium'),
            '출고수량': st.column_config.NumberColumn('출고수량', format='%.0f'),
            '현재 CTN': st.column_config.TextColumn('현재 CTN', width='small'),
'''
grid_config_replacement = '''            '선택': st.column_config.CheckboxColumn('선택', width=46),
            '_id': None,
            '사업장': st.column_config.TextColumn('사업장', width=62),
            '실제 제품명': st.column_config.TextColumn('실제 제품명', width=190),
            '제조번호': st.column_config.TextColumn('제조번호', width=88),
            '유통기한': st.column_config.TextColumn('유통기한', width=88),
            '출고수량': st.column_config.NumberColumn('출고수량', format='%.0f', width=72),
            '현재 CTN': st.column_config.TextColumn('현재 CTN', width=68),
'''
if source.count(grid_config_marker) != 1:
    raise RuntimeError('미패킹 제품 표 컬럼 설정 구간을 찾지 못했습니다.')
source = source.replace(grid_config_marker, grid_config_replacement, 1)

active_items_pattern = re.compile(
    r"    if active_items:\n"
    r"        st\.dataframe\(.*?"
    r"    else:\n"
    r"        st\.info\('왼쪽에서 제품을 선택해 이 CTN에 담으세요\.'\)\n",
    re.S,
)
active_items_replacement = '''    if active_items:
        active_item_rows = [
            {
                '빼기': False,
                '_id': int(item['id']),
                '제품명': item['product_name'],
                '제조번호': item['lot_no'],
                '유통기한': item['expiry_date'],
                '수량': float(item['requested_qty'] or 0),
            }
            for item in active_items
        ]
        edited_active_items = st.data_editor(
            pd.DataFrame(active_item_rows),
            hide_index=True,
            use_container_width=True,
            height=min(300, 70 + len(active_items) * 35),
            disabled=['_id', '제품명', '제조번호', '유통기한', '수량'],
            column_config={
                '빼기': st.column_config.CheckboxColumn('빼기', width=46),
                '_id': None,
                '제품명': st.column_config.TextColumn('제품명', width=150),
                '제조번호': st.column_config.TextColumn('제조번호', width=82),
                '유통기한': st.column_config.TextColumn('유통기한', width=82),
                '수량': st.column_config.NumberColumn('수량', format='%.0f', width=62),
            },
            key=f'active_ctn_items_{case_id}_{active_box_no}',
        )
        remove_item_ids = [
            int(row['_id'])
            for _, row in edited_active_items.iterrows()
            if bool(row['빼기'])
        ]
        if st.button(
            f'선택 제품 CTN에서 빼기 ({len(remove_item_ids)}개)',
            use_container_width=True,
            disabled=not remove_item_ids,
            key=f'remove_active_ctn_items_{case_id}_{active_box_no}',
        ):
            packing_service.unassign_items(case_id, remove_item_ids)
            history_service.add(
                case_id,
                'CTN 배정 해제',
                f'CTN {active_box_no}에서 {len(remove_item_ids)}개 실제 출고 행 제거',
            )
            st.success(f'{len(remove_item_ids)}개 제품을 CTN {active_box_no}에서 뺐습니다.')
            st.rerun()
    else:
        st.info('왼쪽에서 제품을 선택해 이 CTN에 담으세요.')
'''
source, active_items_count = active_items_pattern.subn(active_items_replacement, source, count=1)
if active_items_count != 1:
    raise RuntimeError('현재 CTN 제품 목록 구간을 교체하지 못했습니다.')

active_box_marker = '''    if active_box is not None:
        dimension_keys = {
'''
active_box_replacement = '''    if active_box is not None:
        with st.expander('CTN No. 변경'):
            with st.form(f'rename_ctn_{case_id}_{active_box_no}'):
                new_box_no = st.number_input(
                    '새 CTN No.',
                    min_value=1,
                    step=1,
                    value=int(active_box_no),
                    key=f'new_ctn_no_{case_id}_{active_box_no}',
                )
                rename_box_clicked = st.form_submit_button(
                    'CTN No. 변경',
                    use_container_width=True,
                )
            if rename_box_clicked:
                try:
                    packing_edit_service.rename_box(case_id, active_box_no, int(new_box_no))
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    history_service.add(
                        case_id,
                        'CTN No. 변경',
                        f'CTN {active_box_no} → CTN {int(new_box_no)}',
                    )
                    st.session_state[pending_active_key] = f'CTN {int(new_box_no)}'
                    st.session_state.pop(active_label_key, None)
                    st.success(f'CTN {active_box_no}을 CTN {int(new_box_no)}으로 변경했습니다.')
                    st.rerun()

        dimension_keys = {
'''
if source.count(active_box_marker) != 1:
    raise RuntimeError('CTN 정보 입력 시작 구간을 찾지 못했습니다.')
source = source.replace(active_box_marker, active_box_replacement, 1)

action_marker = '''    action_cols = st.columns([2, 2, 1.5])
    assign_clicked = action_cols[0].button(
        '선택 제품 전량 담기', type='primary', use_container_width=True, disabled=not selected_ids
    )
    partial_clicked = action_cols[1].button(
        '선택 제품 일부 담기', use_container_width=True, disabled=len(selected_ids) != 1
    )
    unassign_clicked = action_cols[2].button(
        'CTN에서 빼기', use_container_width=True, disabled=not selected_ids
    )
'''
action_replacement = '''    action_cols = st.columns([2, 2, 2, 1.5])
    assign_clicked = action_cols[0].button(
        '선택 제품 전량 담기', type='primary', use_container_width=True, disabled=not selected_ids
    )
    partial_clicked = action_cols[1].button(
        '선택 제품 일부 담기', use_container_width=True, disabled=len(selected_ids) != 1
    )
    repeated_clicked = action_cols[2].button(
        '동일 CTN 반복 담기', use_container_width=True, disabled=len(selected_ids) != 1
    )
    unassign_clicked = action_cols[3].button(
        'CTN에서 빼기', use_container_width=True, disabled=not selected_ids
    )
'''
if source.count(action_marker) != 1:
    raise RuntimeError('CTN 담기 버튼 구간을 찾지 못했습니다.')
source = source.replace(action_marker, action_replacement, 1)

partial_click_marker = '''    if unassign_clicked:
'''
repeated_click_replacement = '''    if repeated_clicked:
        selected_item = next(item for item in items if int(item['id']) == selected_ids[0])
        if selected_item['box_no'] is not None:
            st.error('동일 CTN 반복 담기는 미패킹 제품만 사용할 수 있습니다.')
        else:
            st.session_state['repeat_pack_item_id'] = selected_ids[0]
            st.session_state.pop(f'repeat_pack_preview_{case_id}', None)
            st.rerun()

    if unassign_clicked:
'''
if source.count(partial_click_marker) != 1:
    raise RuntimeError('CTN 배정 해제 구간을 찾지 못했습니다.')
source = source.replace(partial_click_marker, repeated_click_replacement, 1)

partial_dialog_marker = "partial_item_id = st.session_state.get('partial_pack_item_id')\n"
repeated_dialog = '''repeat_item_id = st.session_state.get('repeat_pack_item_id')
if repeat_item_id:
    repeat_item = next((item for item in items if int(item['id']) == int(repeat_item_id)), None)
    if repeat_item is None or repeat_item['box_no'] is not None:
        st.session_state.pop('repeat_pack_item_id', None)
        st.session_state.pop(f'repeat_pack_preview_{case_id}', None)
    else:
        @dialog('동일 CTN 반복 담기', width='large')
        def repeated_assign_dialog() -> None:
            total_quantity = int(float(repeat_item['requested_qty'] or 0))
            start_box_no = packing_service.next_box_no(case_id)
            st.write(f"**{repeat_item['product_name']}**")
            st.caption(f'남은 수량 {fmt_number(total_quantity)} · 생성 시작 CTN {start_box_no}')

            quantity_per_box = st.number_input(
                'CTN당 수량', min_value=1, max_value=max(total_quantity, 1),
                value=min(10, max(total_quantity, 1)), step=1,
                key=f'repeat_qty_per_box_{case_id}_{repeat_item_id}',
            )
            size_cols = st.columns(4)
            length_cm = size_cols[0].number_input(
                '가로(cm)', min_value=0.0, step=0.1,
                key=f'repeat_length_{case_id}_{repeat_item_id}',
            )
            width_cm = size_cols[1].number_input(
                '세로(cm)', min_value=0.0, step=0.1,
                key=f'repeat_width_{case_id}_{repeat_item_id}',
            )
            height_cm = size_cols[2].number_input(
                '높이(cm)', min_value=0.0, step=0.1,
                key=f'repeat_height_{case_id}_{repeat_item_id}',
            )
            weight_kg = size_cols[3].number_input(
                'CTN당 GW(kg)', min_value=0.0, step=0.1,
                key=f'repeat_weight_{case_id}_{repeat_item_id}',
            )

            preview_key = f'repeat_pack_preview_{case_id}'
            if st.button('미리보기 생성', type='primary', use_container_width=True):
                full_count, remainder = divmod(total_quantity, int(quantity_per_box))
                quantities = [int(quantity_per_box)] * full_count
                if remainder:
                    quantities.append(remainder)
                preview_rows = []
                for offset, quantity in enumerate(quantities):
                    is_remainder = remainder > 0 and offset == len(quantities) - 1
                    preview_rows.append({
                        'CTN': f'CTN {start_box_no + offset}',
                        '수량': quantity,
                        '박스 사이즈': f'{length_cm:g} × {width_cm:g} × {height_cm:g} cm',
                        'GW': '입력 필요' if is_remainder else f'{weight_kg:g} kg',
                        '구분': '⚠ 잔여 수량 CTN' if is_remainder else '',
                    })
                st.session_state[preview_key] = {
                    'quantity_per_box': int(quantity_per_box),
                    'length_cm': float(length_cm),
                    'width_cm': float(width_cm),
                    'height_cm': float(height_cm),
                    'weight_kg': float(weight_kg),
                    'rows': preview_rows,
                }
                st.rerun()

            preview = st.session_state.get(preview_key)
            if preview:
                st.markdown(f"#### 생성 예정: 총 {len(preview['rows'])} CTN")
                preview_df = pd.DataFrame(preview['rows'])
                styled_preview = preview_df.style.apply(
                    lambda row: ['background-color: #fff1d6'] * len(row)
                    if row['구분'] else [''] * len(row),
                    axis=1,
                )
                st.dataframe(styled_preview, hide_index=True, use_container_width=True)
                if any(row['구분'] for row in preview['rows']):
                    st.warning('마지막 행은 잔여 수량 CTN입니다. GW는 비워 두며 실제 계량 후 입력해야 합니다.')

                confirm_col, edit_col = st.columns(2)
                if confirm_col.button('CTN 생성 확정', type='primary', use_container_width=True):
                    try:
                        created = assign_repeated_ctns(
                            case_id,
                            int(repeat_item_id),
                            quantity_per_box=int(preview['quantity_per_box']),
                            length_cm=float(preview['length_cm']),
                            width_cm=float(preview['width_cm']),
                            height_cm=float(preview['height_cm']),
                            weight_kg=float(preview['weight_kg']),
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        created_numbers = ', '.join(f"CTN {row['box_no']}" for row in created)
                        history_service.add(
                            case_id,
                            '동일 CTN 반복 담기',
                            f"{repeat_item['product_name']} {total_quantity}개 → {created_numbers}",
                        )
                        st.session_state.pop('repeat_pack_item_id', None)
                        st.session_state.pop(preview_key, None)
                        st.session_state[selection_key] = []
                        st.session_state[version_key] = int(st.session_state.get(version_key, 0)) + 1
                        st.session_state[pending_active_key] = f"CTN {created[0]['box_no']}"
                        st.success(f'{len(created)}개 CTN을 생성했습니다.')
                        st.rerun()
                if edit_col.button('입력값 수정', use_container_width=True):
                    st.session_state.pop(preview_key, None)
                    st.rerun()

            if st.button('취소', use_container_width=True):
                st.session_state.pop('repeat_pack_item_id', None)
                st.session_state.pop(preview_key, None)
                st.rerun()

        repeated_assign_dialog()


partial_item_id = st.session_state.get('partial_pack_item_id')
'''
if source.count(partial_dialog_marker) != 1:
    raise RuntimeError('일부 수량 담기 모달 구간을 찾지 못했습니다.')
source = source.replace(partial_dialog_marker, repeated_dialog, 1)

exec(compile(source, str(SOURCE_PATH), 'exec'), globals(), globals())
