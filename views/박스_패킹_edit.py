from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

import_marker = 'from services import export_service, history_service, packing_service\n'
import_replacement = 'from services import export_service, history_service, packing_edit_service, packing_service\n'
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

exec(compile(source, str(SOURCE_PATH), 'exec'), globals(), globals())