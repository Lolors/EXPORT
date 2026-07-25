from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹_v3.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

# CTN 삭제 표는 화면 상단에서 읽은 boxes가 아니라 DB의 최신 값을 다시 사용한다.
source, fresh_boxes_count = re.subn(
    r"(?m)^(\s*)delete_rows = \[\]\n\1for delete_box in boxes:",
    lambda match: (
        f"{match.group(1)}delete_boxes = packing_service.list_boxes(case_id)\n"
        f"{match.group(1)}delete_rows = []\n"
        f"{match.group(1)}for delete_box in delete_boxes:"
    ),
    source,
    count=1,
)
if fresh_boxes_count != 1:
    raise RuntimeError('CTN 삭제용 최신 박스 조회 구간을 교체하지 못했습니다.')

# data_editor 호출 직전에 갱신용 키를 삽입한다.
editor_marker = "        edited_delete_rows = st.data_editor(\n            delete_rows,"
if editor_marker not in source:
    raise RuntimeError('CTN 삭제 표 구간을 찾지 못했습니다.')

editor_replacement = """        delete_table_signature = '|'.join(
            f"{int(row['box_no'])}:{row['length_cm']}:{row['width_cm']}:{row['height_cm']}:{row['weight_kg']}:{row['updated_at']}"
            for row in delete_boxes
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
