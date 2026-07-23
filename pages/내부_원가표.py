from __future__ import annotations

import pandas as pd
import streamlit as st

from services import history_service, order_service

st.title('내부 원가표')
st.caption('수출 건별 매입단가와 총 매입원가를 확인하고 수정합니다. 이 정보는 패킹리스트와 공유문서에 표시되지 않습니다.')

cases = order_service.list_cost_cases()
if not cases:
    st.info('등록된 수출 건이 없습니다.')
    st.stop()

case_options = {
    f"{row['export_no']} · {row['country']} · {row['buyer'] or '바이어 미입력'} · ₩{float(row['total_purchase_cost'] or 0):,.0f}": int(row['id'])
    for row in cases
}
selected_label = st.selectbox('수출 건 선택', list(case_options))
case_id = case_options[selected_label]
selected_case = next(row for row in cases if int(row['id']) == case_id)

summary_cols = st.columns(4)
summary_cols[0].metric('수출번호', selected_case['export_no'])
summary_cols[1].metric('국가', selected_case['country'])
summary_cols[2].metric('제품 행', f"{int(selected_case['item_count'] or 0)}개")
summary_cols[3].metric('총 매입원가', f"₩{float(selected_case['total_purchase_cost'] or 0):,.0f}")

items = order_service.get_cost_items_dataframe(case_id)
if items.empty:
    st.info('이 수출 건에 주문 제품이 없습니다.')
    st.stop()

edited = st.data_editor(
    items,
    hide_index=True,
    use_container_width=True,
    num_rows='fixed',
    disabled=['제품명', '수량', '단위', '매입금액'],
    column_order=['제품명', '수량', '단위', '매입가', '매입금액'],
    column_config={
        '_id': None,
        '제품명': st.column_config.TextColumn('제품명'),
        '수량': st.column_config.NumberColumn('수량', format='%,.0f'),
        '단위': st.column_config.TextColumn('단위'),
        '매입가': st.column_config.NumberColumn('매입가', min_value=0.0, step=100.0, format='₩ %,.0f'),
        '매입금액': st.column_config.NumberColumn('매입금액', format='₩ %,.0f'),
    },
    key=f'cost_items_{case_id}',
)

calculated_total = sum(
    float(row.get('수량', 0) or 0) * float(row.get('매입가', 0) or 0)
    for _, row in edited.iterrows()
)
st.markdown(f'### 합계: ₩{calculated_total:,.0f}')

save_left, save_center, save_right = st.columns([4, 2, 4])
with save_center:
    save = st.button('원가표 저장', type='primary', use_container_width=True)

if save:
    save_df = edited.copy()
    save_df['매입금액'] = save_df['수량'].fillna(0) * save_df['매입가'].fillna(0)
    order_service.save_order_items(case_id, save_df)
    history_service.add_history(case_id, '내부 원가표 저장', f'총 매입원가 ₩{calculated_total:,.0f}')
    st.success('매입가와 원가 이력을 저장했습니다.')
    st.rerun()

st.divider()
st.markdown('#### 유사 제품 매입가 조회')
lookup_name = st.text_input('제품명', placeholder='예: 리드카인 1% 10Am')
if lookup_name.strip():
    similar = order_service.find_similar_purchase_prices(lookup_name)
    if similar:
        lookup_df = pd.DataFrame([
            {
                '제품명': item['product_name'],
                '매입가': item['purchase_price'],
                '수량': item['quantity'],
                '단위': item['unit'],
                '수출번호': item['export_no'],
                '바이어': item['buyer'] or '',
                '등록일': str(item['created_at'])[:10],
                '유사도': f"{item['similarity'] * 100:.0f}%",
            }
            for item in similar
        ])
        st.dataframe(
            lookup_df,
            hide_index=True,
            use_container_width=True,
            column_config={'매입가': st.column_config.NumberColumn('매입가', format='₩ %,.0f')},
        )
    else:
        st.info('유사한 매입가 이력이 없습니다.')
