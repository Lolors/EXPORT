from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from components.editors import order_editor
from config import TRANSPORT_MODES
from services import export_service, folder_service, history_service, order_service


def summarize_product_names(raw_names: object) -> str:
    names = [
        name.strip()
        for name in re.split(r'[,\n]+', str(raw_names or ''))
        if name.strip()
    ]
    if len(names) <= 2:
        return ', '.join(names)
    return f"{', '.join(names[:2])} ~ 외 {len(names) - 2}품목"


st.title('주문 검색 및 수정')

cases = order_service.list_editable_cases()
if not cases:
    st.info('수정할 수출 건이 없습니다.')
    st.stop()

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#editable-case-filter-anchor) {
        width: 56vw;
        max-width: 56vw;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#order-edit-panel-anchor) {
        width: 50vw;
        max-width: 50vw;
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 16px;
        padding: 1.25rem 1.35rem 1.35rem;
        margin-top: 0.5rem;
    }
    @media (max-width: 900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#editable-case-filter-anchor),
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(#order-edit-panel-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

with st.container():
    st.markdown('<span id="editable-case-filter-anchor"></span>', unsafe_allow_html=True)

    years = sorted({
        int(str(case['actual_ship_date'] or case['created_at'])[:4])
        for case in cases
        if str(case['actual_ship_date'] or case['created_at'])[:4].isdigit()
    }, reverse=True)

    filter_cols = st.columns([1.5, 1.5, 3, 4])
    selected_year = filter_cols[0].selectbox('연도', ['전체'] + years, key='edit_case_year')

    if selected_year == '전체':
        month_options: list[str | int] = ['전체']
    else:
        month_values = sorted({
            int(str(case['actual_ship_date'] or case['created_at'])[5:7])
            for case in cases
            if str(case['actual_ship_date'] or case['created_at']).startswith(str(selected_year))
            and str(case['actual_ship_date'] or case['created_at'])[5:7].isdigit()
        })
        month_options = ['전체'] + month_values

    selected_month = filter_cols[1].selectbox('월', month_options, key='edit_case_month')
    countries = sorted({str(case['country']).strip() for case in cases if str(case['country']).strip()})
    selected_country = filter_cols[2].selectbox('국가', ['전체'] + countries, key='edit_case_country')
    product_query = filter_cols[3].text_input('제품명 검색', key='edit_case_product_search').strip().casefold()

filtered_cases = []
for case in cases:
    raw_date = str(case['actual_ship_date'] or case['created_at'] or '')
    case_year = int(raw_date[:4]) if raw_date[:4].isdigit() else None
    case_month = int(raw_date[5:7]) if len(raw_date) >= 7 and raw_date[5:7].isdigit() else None

    if selected_year != '전체' and case_year != selected_year:
        continue
    if selected_month != '전체' and case_month != selected_month:
        continue
    if selected_country != '전체' and str(case['country']).strip() != selected_country:
        continue
    if product_query and product_query not in str(case['product_names'] or '').casefold():
        continue
    filtered_cases.append(case)

if not filtered_cases:
    st.warning('조건에 맞는 수출 건이 없습니다.')
    st.stop()

with st.container():
    selected_case_id = st.session_state.get('order_case_id')
    selection_rows = []
    for case in filtered_cases:
        raw_date = str(case['actual_ship_date'] or case['created_at'] or '')
        selection_rows.append({
            '선택': int(case['id']) == selected_case_id,
            '_case_id': int(case['id']),
            '등록일자': raw_date[:10],
            '수출번호': case['export_no'],
            '국가': case['country'],
            '바이어': case['buyer'] or '',
            '운송방식': case['transport_mode'],
            '단계': case['stage'],
            '주문제품': summarize_product_names(case['product_names']),
        })

    selection_df = pd.DataFrame(selection_rows)
    edited_selection = st.data_editor(
        selection_df,
        hide_index=True,
        disabled=['_case_id', '등록일자', '수출번호', '국가', '바이어', '운송방식', '단계', '주문제품'],
        column_config={
            '선택': st.column_config.CheckboxColumn('선택', help='수정할 주문 한 건만 체크하세요.'),
            '_case_id': None,
            '등록일자': st.column_config.TextColumn('등록일자'),
            '수출번호': st.column_config.TextColumn('수출번호'),
            '국가': st.column_config.TextColumn('국가'),
            '바이어': st.column_config.TextColumn('바이어'),
            '운송방식': st.column_config.TextColumn('운송방식'),
            '단계': st.column_config.TextColumn('단계'),
            '주문제품': st.column_config.TextColumn('주문제품'),
        },
        key='editable_case_table',
    )

checked_rows = edited_selection[edited_selection['선택'] == True]
if checked_rows.empty:
    st.info('수정할 수출 건의 선택 칸을 체크하세요.')
    st.stop()
if len(checked_rows) > 1:
    st.warning('수정할 수출 건은 한 건만 체크할 수 있습니다.')
    st.stop()

case_id = int(checked_rows.iloc[0]['_case_id'])
st.session_state['order_case_id'] = case_id
case_map = {int(row['id']): row for row in filtered_cases}
case = case_map[case_id]

with st.container():
    st.markdown('<span id="order-edit-panel-anchor"></span>', unsafe_allow_html=True)
    st.markdown('#### 기본 정보 수정')
    info_cols = st.columns(4)
    new_country = info_cols[0].text_input('국가 *', value=case['country'])
    new_buyer = info_cols[1].text_input('바이어 (선택)', value=case['buyer'])
    transport_index = TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in TRANSPORT_MODES else 0
    new_transport = info_cols[2].selectbox('운송방식', TRANSPORT_MODES, index=transport_index)
    new_note = info_cols[3].text_input('비고', value=case['note'])

    save_col, cancel_col, confirm_col = st.columns([2, 2, 6])
    save_basic = save_col.button('기본 정보 저장', use_container_width=True, key=f'save_basic_{case_id}')
    cancel_confirmed = confirm_col.checkbox(
        f"{case['export_no']} 주문 취소를 확인합니다.",
        key=f'cancel_confirm_{case_id}',
    )
    cancel_order = cancel_col.button(
        '주문 취소',
        type='secondary',
        disabled=not cancel_confirmed,
        use_container_width=True,
        key=f'cancel_order_{case_id}',
    )

    if save_basic:
        if not new_country.strip():
            st.error('국가는 필수입니다.')
        else:
            export_service.update_basic(case_id, new_country, new_buyer, new_transport, new_note)
            folder_service.sync_case_folder(case_id)
            history_service.add_history(case_id, '수출 기본 정보 수정', f'{new_country} / {new_transport}')
            st.success('기본 정보를 저장했습니다.')
            st.rerun()

    if cancel_order:
        export_service.cancel_case(case_id)
        history_service.add_history(case_id, '주문 취소', case['export_no'])
        st.session_state.pop('order_case_id', None)
        st.session_state.pop(f'cancel_confirm_{case_id}', None)
        st.success(f"{case['export_no']} 주문을 취소했습니다.")
        st.rerun()

    existing = order_service.get_order_items_dataframe(case_id)
    if existing.empty:
        existing = pd.DataFrame([{'_id': None, '제품명': '', '수량': 0.0, '단위': 'EA'}])

    historical_case = case['case_type'] == 'historical'
    st.markdown('#### 실출고 제품 수정' if historical_case else '#### 주문품목 수정')
    if historical_case:
        st.caption('과거 수출 건에서는 수정한 내용이 주문목록과 실출고 제품에 함께 반영됩니다.')
    else:
        st.caption('실출고가 연결된 행은 삭제할 수 없지만 제품명·수량·단위는 수정할 수 있습니다.')

    edited = order_editor(existing, key=f'orders_{case_id}')
    if st.button('목록 저장' if historical_case else '주문 목록 저장', type='primary', key=f'save_orders_{case_id}'):
        try:
            order_service.save_order_items(case_id, edited)
        except ValueError as exc:
            st.error(str(exc))
        else:
            folder_service.sync_case_folder(case_id)
            action = '과거 실출고 목록 저장' if historical_case else '주문 목록 저장'
            history_service.add_history(case_id, action, f'{len(edited)}행')
            st.success('목록을 저장했습니다.')
            st.rerun()
