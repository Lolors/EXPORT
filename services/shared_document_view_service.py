from __future__ import annotations

import re

from utils.formatters import fmt_number


STAGE_LABELS = {
    '주문 접수': '주문 접수',
    '주문 입력': '주문 접수',
    '제품 준비': '제품 준비',
    '실출고 입력': '출고 대기',
    '출고 대기': '출고 대기',
    '패킹': '패킹',
    '박스 패킹': '패킹',
    '패킹 진행': '패킹 진행',
    '패킹 대기': '패킹 대기',
    '패킹 완료': '패킹 완료',
    '국내배송': '국내배송',
    '선적 준비': '선적 준비',
    '선적 완료': '선적 완료',
    '완료': '완료',
    '취소': '주문 취소',
    '주문 취소': '주문 취소',
}

STAGE_SORT_ORDER = {
    '패킹 완료': 0,
    '패킹 대기': 1,
    '입고 진행': 2,
    '제품 준비': 2,
    '출고 대기': 2,
    '주문 접수': 3,
    '주문 입력': 3,
    '국내배송': 99,
}


def display_stage(value: object) -> str:
    stage = str(value or '').strip()
    return STAGE_LABELS.get(stage, stage or '-')


def summarize_product_names(raw_names: object) -> str:
    names = [name.strip() for name in re.split(r'[,\n]+', str(raw_names or '')) if name.strip()]
    if len(names) <= 2:
        return ', '.join(names)
    return f"{', '.join(names[:2])} 외 {len(names) - 2}품목"


def quantity_with_unit(row) -> str:
    quantity = fmt_number(row['requested_qty'])
    try:
        unit = str(row['unit'] or '').strip()
    except (KeyError, IndexError):
        unit = ''
    return f'{quantity} {unit}'.strip()


def shipment_date(case) -> str:
    return str(case['actual_ship_date'] or '').strip()


def filter_and_sort_cases(
    cases,
    *,
    selected_year,
    selected_month,
    selected_country: str,
    product_query: str,
):
    filtered = []
    for case in cases:
        raw_date = shipment_date(case)
        case_year = int(raw_date[:4]) if raw_date[:4].isdigit() else None
        case_month = int(raw_date[5:7]) if len(raw_date) >= 7 and raw_date[5:7].isdigit() else None
        if raw_date:
            if selected_year != '전체' and case_year != selected_year:
                continue
            if selected_month != '전체' and case_month != selected_month:
                continue
        if selected_country != '전체' and str(case['country']).strip() != selected_country:
            continue
        if product_query and product_query not in str(case['product_names'] or '').casefold():
            continue
        filtered.append(case)
    return sorted(
        filtered,
        key=lambda case: STAGE_SORT_ORDER.get(str(case['stage'] or '').strip(), 90),
    )


def format_case_option(case) -> str:
    ship_date = shipment_date(case) or '미출고'
    buyer = str(case['buyer'] or '').strip() or '바이어 미입력'
    products = summarize_product_names(case['product_names'])
    return (
        f"{display_stage(case['stage'])} · {ship_date} · "
        f"{case['export_no']} · {case['country']} · {buyer} · {products}"
    )
