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

    # 동일한 수출번호와 조건을 가진 수출 건이 여러 개 있어도
    # selectbox 옵션 딕셔너리에서 서로 덮어쓰지 않도록 내부 ID를 포함한다.
    case_id = ''
    try:
        case_id = str(case['id']).strip()
    except (KeyError, TypeError, AttributeError):
        case_id = ''
    if case_id:
        parts.append(f'ID {case_id}')

    return prefix + ' · '.join(parts)
