from __future__ import annotations

from pathlib import Path


SOURCE_PATH = Path(__file__).with_name('실출고_입력.py')
source = SOURCE_PATH.read_text(encoding='utf-8')

product_name_old = "'실제 제품명': selected_order_name,"
product_name_new = "'실제 제품명': '',"

if source.count(product_name_old) != 1:
    raise RuntimeError('실제 제품명 기본값을 변경하지 못했습니다.')

patched = source.replace(product_name_old, product_name_new, 1)

price_lookup_width_old = '''    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.shipment-price-lookup-anchor) {
        width: 100vw;
        max-width: 100vw;
    }
'''
price_lookup_width_new = '''    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.shipment-price-lookup-anchor) {
        width: 60vw;
        max-width: 60vw;
    }
    @media (max-width: 900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.shipment-price-lookup-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
'''

if patched.count(price_lookup_width_old) != 1:
    raise RuntimeError('유사 제품 매입가 조회 너비 구간을 변경하지 못했습니다.')

patched = patched.replace(price_lookup_width_old, price_lookup_width_new, 1)

prefetch_old = '''orders = order_service.list_for_case(case_id)

unlinked_count = shipment_service.count_unlinked(case_id)
'''
prefetch_new = '''orders = order_service.list_for_case(case_id)
all_linked_rows = shipment_service.list_case_items(case_id)
linked_rows_by_order: dict[int, list] = {}
for linked_row in all_linked_rows:
    linked_order_id = int(linked_row['order_item_id'])
    linked_rows_by_order.setdefault(linked_order_id, []).append(linked_row)

unlinked_count = shipment_service.count_unlinked(case_id)
'''
if patched.count(prefetch_old) != 1:
    raise RuntimeError('수출대기 입고 일괄 조회 삽입 구간을 찾지 못했습니다.')
patched = patched.replace(prefetch_old, prefetch_new, 1)

linked_replacements = {
    "shipment_service.list_linked(case_id, order_id)": "linked_rows_by_order.get(order_id, [])",
    "shipment_service.list_linked(case_id, selected_order_id)": "linked_rows_by_order.get(selected_order_id, [])",
}
for old, new in linked_replacements.items():
    if old not in patched:
        raise RuntimeError(f'반복 입고 조회 구간을 찾지 못했습니다: {old}')
    patched = patched.replace(old, new)

progress_old = '''    total_order_qty = sum(safe_number(order['quantity']) for order in orders)
    total_received_qty = shipment_service.total_linked_quantity(case_id)
    progress_ratio = min(total_received_qty / total_order_qty, 1.0) if total_order_qty > 0 else 0.0

    st.divider()
    st.markdown('#### 전체 입고 진행률')
    st.progress(
        progress_ratio,
        text=(
            f'{fmt_number(total_received_qty)} / {fmt_number(total_order_qty)} '
            f'({progress_ratio * 100:.1f}%)'
        ),
    )
    if total_order_qty > 0 and total_received_qty >= total_order_qty:
        st.success('🎉 모든 제품이 입고되었습니다!')
'''

progress_new = '''    item_progress_ratios: list[float] = []
    completed_item_count = 0
    for progress_order in orders:
        progress_order_id = int(progress_order['id'])
        progress_order_qty = safe_number(progress_order['quantity'])
        progress_received_qty = sum(
            safe_number(row['requested_qty'])
            for row in linked_rows_by_order.get(progress_order_id, [])
        )
        if progress_order_qty > 0:
            item_ratio = min(progress_received_qty / progress_order_qty, 1.0)
            item_progress_ratios.append(item_ratio)
            if progress_received_qty + 0.000001 >= progress_order_qty:
                completed_item_count += 1
        else:
            item_progress_ratios.append(0.0)

    order_item_count = len(item_progress_ratios)
    progress_ratio = (
        sum(item_progress_ratios) / order_item_count
        if order_item_count > 0
        else 0.0
    )
    all_items_received = (
        order_item_count > 0
        and completed_item_count == order_item_count
    )

    st.divider()
    st.markdown('#### 전체 입고 진행률')
    st.progress(
        progress_ratio,
        text=(
            f'완료 품목 {completed_item_count} / {order_item_count}개 '
            f'({progress_ratio * 100:.1f}%)'
        ),
    )
    st.caption('각 주문품목의 입고율을 최대 100%로 계산한 뒤 품목별 입고율의 평균을 표시합니다.')
    if all_items_received:
        st.success('🎉 모든 주문품목이 각각 100% 입고되었습니다!')
'''

if patched.count(progress_old) != 1:
    raise RuntimeError('전체 입고 진행률 계산 구간을 변경하지 못했습니다.')

patched = patched.replace(progress_old, progress_new, 1)
exec(compile(patched, str(SOURCE_PATH), 'exec'), globals(), globals())
