from __future__ import annotations

from collections import defaultdict

import streamlit as st

from services.export_service import active_cases, get_order_items_with_actual
from utils.formatters import fmt_number


st.title('오버뷰')
st.caption('현재 진행 중인 주문과 수출대기 입고 진행률을 국가별로 확인합니다.')

cases = active_cases()
if not cases:
    st.info('현재 진행 중인 주문이 없습니다.')
    st.stop()

country_groups: dict[str, list] = defaultdict(list)
for case in cases:
    country = str(case['country'] or '').strip() or '국가 미지정'
    country_groups[country].append(case)

for country in sorted(country_groups):
    st.markdown(f'## {country}')

    for case in country_groups[country]:
        orders = get_order_items_with_actual(int(case['id']))
        order_total = sum(float(order['quantity'] or 0) for order in orders)
        received_total = sum(float(order['actual_qty'] or 0) for order in orders)
        progress = received_total / order_total if order_total > 0 else 0.0
        display_progress = min(max(progress, 0.0), 1.0)

        with st.container(border=True):
            header_left, header_right = st.columns([4, 1])
            header_left.markdown(f"### {case['export_no']} · {case['buyer'] or '바이어 미입력'}")
            header_right.markdown(f"**{progress * 100:.1f}%**")

            st.progress(display_progress)
            st.caption(
                f"주문수량 {fmt_number(order_total)} / 입고수량 {fmt_number(received_total)}"
                f" · 운송 {case['transport_mode']} · 단계 {case['stage']}"
            )

            if not orders:
                st.caption('주문품목이 아직 입력되지 않았습니다.')
                continue

            for order in orders:
                order_qty = float(order['quantity'] or 0)
                received_qty = float(order['actual_qty'] or 0)
                item_progress = received_qty / order_qty if order_qty > 0 else 0.0
                st.markdown(
                    f"**{order['product_name']}**  "
                    f"주문 {fmt_number(order_qty)} {order['unit']} · "
                    f"입고 {fmt_number(received_qty)} {order['unit']} · "
                    f"{item_progress * 100:.1f}%"
                )
                st.progress(min(max(item_progress, 0.0), 1.0))

    st.divider()
