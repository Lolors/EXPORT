from __future__ import annotations

INVALID_FOLDER_CHARS = '\\/:*?"<>|'


def fmt_number(value) -> str:
    try:
        return f'{float(value):g}'
    except (TypeError, ValueError):
        return '0'


def sanitize_folder_part(value: str | None, fallback: str = '미입력') -> str:
    text = str(value or '').strip() or fallback
    for char in INVALID_FOLDER_CHARS:
        text = text.replace(char, '_')
    text = ' '.join(text.split())
    return text.strip(' .') or fallback


def case_label(case, include_type: bool = False) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    prefix = ''
    if include_type and 'case_type' in case.keys():
        prefix = '[과거] ' if case['case_type'] == 'historical' else '[진행] '
    return f"{prefix}{case['export_no']} · {case['country']}{buyer} · {case['stage']}"
