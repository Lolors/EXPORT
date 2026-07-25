from __future__ import annotations

from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('실출고_입력.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

old = "'실제 제품명': selected_order_name,"
new = "'실제 제품명': '',"

if source.count(old) != 1:
    raise RuntimeError('실제 제품명 기본값을 변경하지 못했습니다.')

patched = source.replace(old, new, 1)
exec(compile(patched, str(SOURCE_PATH), 'exec'), globals(), globals())
