from __future__ import annotations

from collections import defaultdict
from math import ceil

import streamlit as st

from services.export_service import active_cases, get_order_items_with_actual
from utils.formatters import fmt_number


st.title('오버뷰')
st.caption('현재 진행 중인 수출 건을 국가별로 묶어 보고, 상세 보기 버튼으로 주문목록과 입고상황을 확인합니다.')

st.markdown(
    '''
    <style>
    .overview-country-group {
        width: 40vw;
        max-width: 40vw;
        margin: 1.2rem 0 0.7rem;
        padding-bottom: 0.35rem;
        border-bottom: 2px solid rgba(49, 51, 63, 0.12);
        font-size: 1.45rem;
        font-weight: 800;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-card-anchor) {
        width: 40vw;
        max-width: 40vw;
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 16px;
        padding: 1.1rem 1.25rem 1.2rem;
        margin-bottom: 0.8rem;
        overflow: hidden;
        transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-card-anchor):hover {
        border-color: rgba(79, 139, 249, 0.72);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
        transform: translateY(-1px);
    }
    .overview-card-anchor {
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
    }
    .overview-buyer {
        font-size: 1.2rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .overview-export-no {
        font-size: 0.98rem;
        font-weight: 700;
        margin-bottom: 0.7rem;
        opacity: 0.82;
    }
    .overview-progress-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 0.25rem 0 0.65rem 0;
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
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-card-anchor) div[data-testid="stButton"] {
        display: flex;
        justify-content: center;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-card-anchor) div[data-testid="stButton"] button {
        width: auto;
        min-width: 8rem;
        padding-left: 1.4rem;
        padding-right: 1.4rem;
    }
    .overview-details {
        width: 40vw;
        max-width: 40vw;
        margin: -0.2rem 0 1rem;
        padding: 0 1.25rem 1rem;
    }
    @media (max-width: 900px) {
        .overview-country-group,
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.overview-card-anchor),
        .overview-details {
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

selected_case_id = st.session_state.get('overview_selected_case_id')

for country in sorted(country_groups):
    st.markdown(f'<div class="overview-country-group">{country}</div>', unsafe_allow_html=True)

    for case in country_groups[country]:
        case_id = int(case['id'])
        orders = get_order_items_with_actual(case_id)
        order_total = sum(float(order['quantity'] or 0) for order in orders)
        received_total = sum(float(order['actual_qty'] or 0) for order in orders)
        progress = received_total / order_total if order_total > 0 else 0.0

        buyer = str(case['buyer'] or '').strip()
        if not buyer or buyer.casefold() == '미지정':
            buyer = '바이어 미지정'

        export_no = str(case['export_no'] or '').strip() or '수출번호 미지정'
        is_open = selected_case_id == case_id

        with st.container():
            st.markdown('<div class="overview-card-anchor"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="overview-buyer">{buyer}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="overview-export-no">{export_no}</div>', unsafe_allow_html=True)
            render_progress_bar(progress)
            if st.button(
                '상세 닫기' if is_open else '상세 보기',
                key=f'overview_toggle_{case_id}',
            ):
                st.session_state['overview_selected_case_id'] = None if is_open else case_id
                st.rerun()

        if not is_open:
            continue

        with st.container():
            st.markdown('<div class="overview-details">', unsafe_allow_html=True)
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
