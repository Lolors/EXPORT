from __future__ import annotations

from datetime import date, datetime

from services import export_service


STAGE_LABELS = {
    '출고 대기': '패킹 대기',
}

STAGE_COLORS = {
    '주문 접수': 'background-color: #eef1f5; color: #46505f; font-weight: 700;',
    '제품 준비': 'background-color: #fff2cc; color: #7a5a00; font-weight: 700;',
    '패킹 대기': 'background-color: #dff3ff; color: #075f85; font-weight: 700;',
    '패킹 진행': 'background-color: #e8f0ff; color: #315d9b; font-weight: 700;',
    '패킹 완료': 'background-color: #e7e0ff; color: #5637a5; font-weight: 700;',
    '국내배송': 'background-color: #ffe7d6; color: #9a4b0b; font-weight: 700;',
    '선적 준비': 'background-color: #dff5f2; color: #14685f; font-weight: 700;',
    '선적 완료': 'background-color: #dcecff; color: #174f8f; font-weight: 700;',
    '완료': 'background-color: #dff5e7; color: #17683a; font-weight: 700;',
}



def _recent_month_prefixes(reference: datetime, month_count: int) -> list[str]:
    prefixes: list[str] = []
    year = reference.year
    month = reference.month
    for _ in range(max(1, month_count)):
        prefixes.append(f'{year:04d}-{month:02d}')
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return prefixes


def recent_order_cases(
    cases: list,
    *,
    reference: datetime | None = None,
    month_count: int = 2,
) -> list:
    prefixes = set(_recent_month_prefixes(reference or datetime.now(), month_count))
    return [
        case
        for case in cases
        if timeline_date(case)[:7] in prefixes
    ]


def timeline_date(case) -> str:
    """Return the date used to place an order on the dashboard timeline."""
    export_no = str(case['export_no'] or '').strip().upper()
    actual_ship_date = str(case['actual_ship_date'] or '').strip()[:10]
    created_at = str(case['created_at'] or '').strip()[:10]
    if export_no.startswith('HIS') and actual_ship_date:
        return actual_ship_date
    return created_at


def timeline_date_label(value: object) -> str:
    raw = str(value or '').strip()[:10]
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return raw or '날짜 미입력'
    return f'{parsed.month}월 {parsed.day}일'


def recent_order_period_label(
    *,
    reference: datetime | None = None,
    month_count: int = 2,
) -> str:
    prefixes = list(reversed(_recent_month_prefixes(reference or datetime.now(), month_count)))
    start_year, start_month = prefixes[0].split('-')
    end_year, end_month = prefixes[-1].split('-')
    if start_year == end_year:
        return f'{start_year}년 {int(start_month)}월~{int(end_month)}월'
    return (
        f'{start_year}년 {int(start_month)}월~'
        f'{end_year}년 {int(end_month)}월'
    )

def stage_label(value: object) -> str:
    stage = str(value or '').strip()
    return STAGE_LABELS.get(stage, stage)


def stage_style(value: object) -> str:
    return STAGE_COLORS.get(
        str(value or '').strip(),
        'background-color: #f3f4f6; color: #555; font-weight: 700;',
    )


def order_products_summary(case_id: int) -> str:
    product_names = [
        str(item['product_name'] or '').strip()
        for item in export_service.get_order_items(case_id)
        if str(item['product_name'] or '').strip()
    ]
    if not product_names:
        return '-'

    visible_names = product_names[:2]
    summary = ', '.join(visible_names)
    remaining_count = len(product_names) - len(visible_names)
    if remaining_count > 0:
        summary += f' + 그 외 {remaining_count}품목'
    return summary
