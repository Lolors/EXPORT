from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹_v3.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

# CTN 삭제 표는 화면 상단에서 읽은 boxes가 아니라 DB의 최신 값을 다시 사용한다.
# 제품요약은 전체 출고행을 한 번만 읽어 박스번호별로 묶어 사용한다.
source, fresh_boxes_count = re.subn(
    r"(?m)^(\s*)delete_rows = \[\]\n\1for delete_box in boxes:",
    lambda match: (
        f"{match.group(1)}delete_boxes = packing_service.list_boxes(case_id)\n"
        f"{match.group(1)}delete_items_by_box: dict[int, list] = {{}}\n"
        f"{match.group(1)}for delete_item_row in packing_service.list_items(case_id):\n"
        f"{match.group(1)}    raw_delete_box_no = delete_item_row['box_no']\n"
        f"{match.group(1)}    if raw_delete_box_no is not None:\n"
        f"{match.group(1)}        delete_items_by_box.setdefault(int(raw_delete_box_no), []).append(delete_item_row)\n"
        f"{match.group(1)}delete_rows = []\n"
        f"{match.group(1)}for delete_box in delete_boxes:"
    ),
    source,
    count=1,
)
if fresh_boxes_count != 1:
    raise RuntimeError('CTN 삭제용 최신 박스 조회 구간을 교체하지 못했습니다.')

item_lookup_old = "delete_items = packing_service.list_box_items(case_id, delete_box_no)"
item_lookup_new = "delete_items = delete_items_by_box.get(delete_box_no, [])"
if source.count(item_lookup_old) != 1:
    raise RuntimeError('CTN별 반복 제품 조회 구간을 찾지 못했습니다.')
source = source.replace(item_lookup_old, item_lookup_new, 1)

# 삭제 표의 규격·무게는 각 CTN 입력 위젯 값을 우선 사용하고, 없을 때 DB 값을 사용한다.
value_pattern = re.compile(
    r"(?m)^(\s*)dimensions = \[delete_box\['length_cm'\], delete_box\['width_cm'\], delete_box\['height_cm'\]\]\n"
    r"\1size_text = .*?\n"
    r"\1weight_text = .*?$"
)


def replace_box_values(match: re.Match[str]) -> str:
    indent = match.group(1)
    return (
        f"{indent}delete_box_id = int(delete_box['id'])\n"
        f"{indent}length_value = st.session_state.get(f'len_{{delete_box_id}}', delete_box['length_cm'])\n"
        f"{indent}width_value = st.session_state.get(f'wid_{{delete_box_id}}', delete_box['width_cm'])\n"
        f"{indent}height_value = st.session_state.get(f'hei_{{delete_box_id}}', delete_box['height_cm'])\n"
        f"{indent}weight_value = st.session_state.get(f'wei_{{delete_box_id}}', delete_box['weight_kg'])\n"
        f"{indent}dimensions = [length_value, width_value, height_value]\n"
        f"{indent}size_text = ' × '.join(fmt_number(value) for value in dimensions)\n"
        f"{indent}weight_text = f'{{fmt_number(weight_value)}} kg'"
    )


source, value_count = value_pattern.subn(replace_box_values, source, count=1)
if value_count != 1:
    raise RuntimeError('CTN 삭제 표 규격·무게 구간을 교체하지 못했습니다.')

# data_editor 호출 직전에 표시값 기반 갱신 키를 삽입한다.
editor_marker = "        edited_delete_rows = st.data_editor(\n            delete_rows,"
if editor_marker not in source:
    raise RuntimeError('CTN 삭제 표 구간을 찾지 못했습니다.')

editor_replacement = """        delete_table_signature = '|'.join(
            f"{row['_box_no']}:{row['가로 × 세로 × 높이']}:{row['GW']}"
            for row in delete_rows
        )
        delete_table_key = f'ctn_delete_table_{case_id}_{delete_table_signature}'

        edited_delete_rows = st.data_editor(
            delete_rows,"""
source = source.replace(editor_marker, editor_replacement, 1)

source, key_replace_count = re.subn(
    r"key=f'ctn_delete_table_\{case_id\}',",
    "key=delete_table_key,",
    source,
    count=1,
)
if key_replace_count != 1:
    raise RuntimeError('CTN 삭제 표 키를 교체하지 못했습니다.')

source, key_pop_count = re.subn(
    r"st\.session_state\.pop\(f'ctn_delete_table_\{case_id\}', None\)",
    "st.session_state.pop(delete_table_key, None)",
    source,
    count=1,
)
if key_pop_count != 1:
    raise RuntimeError('CTN 삭제 표 세션 정리 키를 교체하지 못했습니다.')

exec(compile(source, str(SOURCE_PATH), 'exec'), globals(), globals())
