from __future__ import annotations

import streamlit as st

import db


def get_pandas():
    import pandas as pd
    return pd


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['stage']}"


st.title('오버뷰')
st.caption('수출 진행 현황을 확인합니다.')

cases = db.active_cases()
if not cases:
    st.info('현재 진행 중인 수출 건이 없습니다.')

for case in cases:
    orders = db.rows(
        '''SELECT o.id, o.product_name, o.quantity, o.unit,
                  COALESCE(SUM(s.requested_qty),0) AS actual_qty
           FROM order_items o
           LEFT JOIN shipment_items s ON s.order_item_id=o.id
           WHERE o.case_id=?
           GROUP BY o.id, o.product_name, o.quantity, o.unit
           ORDER BY o.id''',
        (case['id'],),
    )
    title = case_label(case)
    if case['note']:
        title += f" · {case['note']}"

    with st.expander(title):
        if orders:
            pd = get_pandas()
            st.dataframe(
                pd.DataFrame([
                    {
                        '주문품목': order['product_name'],
                        '주문수량': order['quantity'],
                        '실출고수량': order['actual_qty'],
                        '단위': order['unit'],
                    }
                    for order in orders
                ]),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption('주문품목이 아직 입력되지 않았습니다.')

        cols = st.columns(5)
        cols[0].metric('국가', case['country'])
        cols[1].metric('운송', case['transport_mode'])
        cols[2].metric('예상 출고일', case['expected_ship_date'] or '-')
        cols[3].metric('단계', case['stage'])
        cols[4].metric('비고', case['note'] or '-')
        st.caption(f"폴더: {case['folder_path'] or '아직 생성되지 않음'}")
