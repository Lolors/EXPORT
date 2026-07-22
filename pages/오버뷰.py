from __future__ import annotations

from collections import defaultdict
from math import ceil

import streamlit as st

from services.export_service import active_cases, get_order_items_with_actual
from utils.formatters import fmt_number


st.title('오버뷰')
st.caption('현재 진행 중인 주문과 수출대기 입고 진행률을 국가별로 확인합니다.')

st.markdown(
    '''
    <style>
    .overview-progress-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0.25rem 0 0.65rem 0;
    }
    .overview-progress-track {
        width: 30vw;
        max-width: 30vw;
        height: 0.8rem;
        background: rgba(49, 51, 63, 0.14);
        border-radius: 999px;
        overflow: hidden;
    }
    .overview-progress-fill {
        height: 100%;
        background: #4f8bf9;
        border-radius: 999px;
    }
    .overview-progress-label {
        min-width: 3.5rem;
        font-weight: 700;
        text-align: left;
    }
    @media (max-width: 900px) {
        .overview-progress-track {
            width: 70vw;
            max-width: 70vw;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)


def render_progress_bar(progress: float) -> None:
    bounded = min(max(progress, 0.0), 1.0)
    percent = ceil(progress * 100) if progress > 0 else 0
    st.markdown(
        f'''
        <div class="overview-progress-row">
            <div class="overview-progress-track">
                <div class="overview-progress-fill" style="width: {bounded * 100:.4f}%;"></div>
            </div>
            <div class="overview-progress-label">{percent}%</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


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

        with st.container(border=True):
            buyer = str(case['buyer'] or '').strip()
            if buyer.casefold() == '미지정':
                buyer = ''

            transport_mode = str(case['transport_mode'] or '').strip()
            if transport_mode.casefold() == '미지정':
                transport_mode = ''

            header_parts = [part for part in [transport_mode, str(case['export_no']), buyer] if part]
            st.markdown(f"### {' · '.join(header_parts)}")

            render_progress_bar(progress)
            st.caption(
                f"주문수량 {fmt_number(order_total)} / 입고수량 {fmt_number(received_total)}"
                f" · 단계 {case['stage']}"
            )

            if not orders:
                st.caption('주문품목이 아직 입력되지 않았습니다.')
                continue

            for order in orders:
                order_qty = float(order['quantity'] or 0)
                received_qty = float(order['actual_qty'] or 0)
                st.markdown(
                    f"**{order['product_name']}**  "
                    f"주문 {fmt_number(order_qty)} {order['unit']} · "
                    f"입고 {fmt_number(received_qty)} {order['unit']}"
                )

    st.divider()
