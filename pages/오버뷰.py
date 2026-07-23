from __future__ import annotations

from collections import defaultdict
from math import ceil

import streamlit as st

from services.export_service import active_cases, get_order_items_with_actual
from utils.formatters import fmt_number


st.title('오버뷰')
st.caption('국가명을 눌러 해당 국가의 진행 중 주문과 입고상황을 한 번에 확인합니다.')

st.markdown(
    '''
    <style>
    div[data-testid="stExpander"] {
        width: 40vw;
        max-width: 40vw;
        margin-bottom: 0.85rem;
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 14px;
        overflow: hidden;
    }
    div[data-testid="stExpander"] summary {
        font-size: 1.35rem;
        font-weight: 800;
        padding-top: 0.9rem;
        padding-bottom: 0.9rem;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-order-anchor) {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 14px;
        padding: 1rem 1.15rem 1.05rem;
        margin: 0.35rem 0 0.9rem;
    }
    .overview-order-anchor {
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
    }
    .overview-buyer {
        font-size: 1.12rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .overview-export-no {
        font-size: 0.96rem;
        font-weight: 700;
        margin-bottom: 0.65rem;
        opacity: 0.82;
    }
    .overview-progress-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0.2rem 0 0.75rem;
    }
    .overview-progress-track {
        width: 100%;
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
    .overview-order-details {
        margin-top: 0.55rem;
        padding-top: 0.75rem;
        border-top: 1px solid rgba(49, 51, 63, 0.12);
    }
    @media (max-width: 900px) {
        div[data-testid="stExpander"] {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)


def render_progress_bar(progress: float) -> None:
    bounded = min(max(progress, 0.0), 1.0)
    percent = ceil(bounded * 100) if bounded > 0 else 0
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


def order_status_icon(order_qty: float, received_qty: float) -> str:
    if order_qty > 0 and received_qty >= order_qty:
        return '🟢'
    if received_qty > 0:
        return '🟡'
    return '🔴'


cases = active_cases()
if not cases:
    st.info('현재 진행 중인 주문이 없습니다.')
    st.stop()

country_groups: dict[str, list] = defaultdict(list)
for case in cases:
    country = str(case['country'] or '').strip() or '국가 미지정'
    country_groups[country].append(case)

for country in sorted(country_groups):
    country_cases = country_groups[country]
    with st.expander(f'{country}  ·  {len(country_cases)}건', expanded=False):
        for case in country_cases:
            case_id = int(case['id'])
            orders = get_order_items_with_actual(case_id)
            order_total = sum(float(order['quantity'] or 0) for order in orders)
            received_total = sum(float(order['actual_qty'] or 0) for order in orders)
            progress = received_total / order_total if order_total > 0 else 0.0

            buyer = str(case['buyer'] or '').strip()
            if not buyer or buyer.casefold() == '미지정':
                buyer = '바이어 미지정'

            export_no = str(case['export_no'] or '').strip() or '수출번호 미지정'

            with st.container():
                st.markdown('<div class="overview-order-anchor"></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="overview-buyer">{buyer}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="overview-export-no">{export_no}</div>', unsafe_allow_html=True)
                render_progress_bar(progress)

                st.markdown('<div class="overview-order-details">', unsafe_allow_html=True)
                st.markdown('#### 주문목록 및 입고상황')
                st.caption(
                    f"주문수량 {fmt_number(order_total)} / 입고수량 {fmt_number(received_total)}"
                    f" · 단계 {case['stage']}"
                )

                if not orders:
                    st.caption('주문품목이 아직 입력되지 않았습니다.')
                else:
                    for index, order in enumerate(orders, start=1):
                        order_qty = float(order['quantity'] or 0)
                        received_qty = float(order['actual_qty'] or 0)
                        status_icon = order_status_icon(order_qty, received_qty)
                        st.markdown(
                            f"{status_icon} {index}. **{order['product_name']}**  "
                            f"주문 {fmt_number(order_qty)} {order['unit']} · "
                            f"입고 {fmt_number(received_qty)} {order['unit']}"
                        )
                st.markdown('</div>', unsafe_allow_html=True)
