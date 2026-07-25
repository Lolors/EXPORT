from __future__ import annotations

import re
from pathlib import Path

from utils.page_patch_cache import compile_cached, read_text_cached


SOURCE_PATH = Path(__file__).with_name('박스_패킹.py')
SOURCE_VERSION = SOURCE_PATH.stat().st_mtime_ns
source = read_text_cached(str(SOURCE_PATH), SOURCE_VERSION)

replacement = r'''cases = [
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

pattern = (
    r'cases = \[.*?'
    r"st\.session_state\['actual_packing_case_id'\] = case_id\n"
)
patched, count = re.subn(pattern, lambda _match: replacement, source, count=1, flags=re.S)
if count != 1:
    raise RuntimeError('박스 패킹 수출 건 선택 영역을 교체하지 못했습니다.')

selector_original = '''    selector_key = f'packing_box_detail_{case_id}'
    if st.session_state.get(selector_key) not in box_labels:
        st.session_state[selector_key] = default_box_label

    selected_box_label = st.selectbox('CTN 선택', box_labels, key=selector_key)
'''
selector_replacement = '''    selector_key = f'packing_box_detail_{case_id}'
    pending_selector_key = f'pending_packing_box_detail_{case_id}'
    if pending_selector_key in st.session_state:
        pending_label = st.session_state.pop(pending_selector_key)
        if pending_label in box_labels:
            st.session_state[selector_key] = pending_label
    if st.session_state.get(selector_key) not in box_labels:
        st.session_state[selector_key] = default_box_label

    selected_box_label = st.selectbox('CTN 선택', box_labels, key=selector_key)
'''
if selector_original not in patched:
    raise RuntimeError('CTN 선택 상태 초기화 영역을 찾지 못했습니다.')
patched = patched.replace(selector_original, selector_replacement, 1)

patched = patched.replace(
    "                st.session_state[selector_key] = next_label\n",
    "                st.session_state[pending_selector_key] = next_label\n",
    1,
)
patched = patched.replace(
    "            st.session_state[selector_key] = f'CTN {created_boxes[0]}'\n",
    "            st.session_state[pending_selector_key] = f'CTN {created_boxes[0]}'\n",
    1,
)

code = compile_cached(patched, str(SOURCE_PATH), f'packing-v2-{SOURCE_VERSION}')
exec(code, globals(), globals())
