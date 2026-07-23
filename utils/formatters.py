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
    prefix = ''
    if include_type and 'case_type' in case.keys():
        prefix = '[과거] ' if case['case_type'] == 'historical' else '[진행] '

    values = [
        case['export_no'],
        case['country'],
        case['buyer'],
        case['transport_mode'],
        case['stage'],
    ]
    parts = [str(value).strip() for value in values if str(value or '').strip()]
    return prefix + ' · '.join(parts)
