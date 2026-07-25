from __future__ import annotations

import re
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('박스_패킹.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

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

exec(compile(patched, str(SOURCE_PATH), 'exec'), globals(), globals())
