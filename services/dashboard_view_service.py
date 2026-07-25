from __future__ import annotations

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
