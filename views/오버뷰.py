from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from services import export_service, overview_service


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


def _stage_style(value: object) -> str:
    return STAGE_COLORS.get(
        str(value or '').strip(),
        'background-color: #f3f4f6; color: #555; font-weight: 700;',
    )


def _order_products_summary(case_id: int) -> str:
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


st.title('대시보드')
st.caption('지금 진행 중인 수출 건과 직접 기록한 확인사항을 한 화면에서 관리합니다.')

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.export-table-anchor) {
        width: 60vw;
        max-width: 60vw;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.todo-section-anchor) {
        width: 40vw;
        max-width: 40vw;
    }
    .export-table-anchor,
    .todo-section-anchor,
    .sticky-note-anchor {
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.sticky-note-anchor) {
        min-height: 160px;
        padding: 1rem 1rem 0.7rem;
        border: 1px solid rgba(133, 105, 20, 0.24);
        border-radius: 4px 15px 5px 13px;
        background: linear-gradient(145deg, #fff7ad 0%, #ffef82 100%);
        box-shadow: 0 6px 16px rgba(81, 63, 7, 0.10);
        transform: rotate(-0.25deg);
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.sticky-note-anchor) p,
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.sticky-note-anchor) label {
        color: #4d410c;
    }
    @media (max-width: 900px) {
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.export-table-anchor),
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.todo-section-anchor) {
            width: 100%;
            max-width: 100%;
        }
    }
    </style>
    ''',
    unsafe_allow_html=True,
)

cases = sorted(
    export_service.active_cases(),
    key=lambda case: (
        str(case['country'] or '').casefold(),
        str(case['buyer'] or '').casefold(),
        str(case['transport_mode'] or '').casefold(),
        str(case['export_no'] or '').casefold(),
    ),
)

st.markdown('### 진행 중 수출 건')
if not cases:
    st.success('현재 진행 중인 수출 건이 없습니다.')
else:
    table_rows = []
    for index, case in enumerate(cases, start=1):
        raw_stage = str(case['stage'] or '').strip() or '단계 미입력'
        table_rows.append(
            {
                '구분': index,
                '국가': str(case['country'] or '').strip() or '국가 미입력',
                '바이어': str(case['buyer'] or '').strip() or '바이어 미입력',
                '운송방식': str(case['transport_mode'] or '').strip() or '운송방식 미입력',
                '수출번호': str(case['export_no'] or '').strip() or '수출번호 미입력',
                '현재 단계': STAGE_LABELS.get(raw_stage, raw_stage),
                '주문제품': _order_products_summary(int(case['id'])),
            }
        )

    table_df = pd.DataFrame(table_rows)
    styled_table = table_df.style.map(_stage_style, subset=['현재 단계'])

    with st.container():
        st.markdown('<div class="export-table-anchor"></div>', unsafe_allow_html=True)
        st.dataframe(
            styled_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                '구분': st.column_config.NumberColumn(width='small'),
                '국가': st.column_config.TextColumn(width='small'),
                '바이어': st.column_config.TextColumn(width='medium'),
                '운송방식': st.column_config.TextColumn(width='small'),
                '수출번호': st.column_config.TextColumn(width='medium'),
                '현재 단계': st.column_config.TextColumn(width='small'),
                '주문제품': st.column_config.TextColumn(width='large'),
            },
        )

st.divider()
with st.container():
    st.markdown('<div class="todo-section-anchor"></div>', unsafe_allow_html=True)
    st.markdown('### 내가 체크할 일')
    st.caption('확인할 내용을 포스트잇처럼 추가하고, 끝난 일은 체크하거나 삭제할 수 있습니다.')

    with st.form('overview_add_task_form', clear_on_submit=True):
        add_cols = st.columns([5, 1])
        task_text = add_cols[0].text_input(
            '새 메모',
            placeholder='예: 일본 바이어 패킹리스트 최종 확인',
            label_visibility='collapsed',
        )
        add_task = add_cols[1].form_submit_button('메모 추가', type='primary', use_container_width=True)

    if add_task:
        try:
            overview_service.add_task(task_text)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            st.rerun()

    tasks = overview_service.list_tasks()
    if not tasks:
        st.info('아직 등록한 메모가 없습니다.')
    else:
        note_columns = st.columns(2)
        for index, task in enumerate(tasks):
            column = note_columns[index % 2]
            with column:
                with st.container():
                    st.markdown('<div class="sticky-note-anchor"></div>', unsafe_allow_html=True)
                    done = st.checkbox(
                        '확인 완료',
                        value=bool(task['done']),
                        key=f"overview_task_done_{task['id']}",
                    )
                    text_style = 'text-decoration: line-through; opacity: 0.58;' if done else ''
                    st.markdown(
                        f'<div style="font-size:1.02rem;font-weight:700;line-height:1.55;{text_style}">'
                        f'{escape(task["text"])}</div>',
                        unsafe_allow_html=True,
                    )
                    if done != bool(task['done']):
                        overview_service.set_done(task['id'], done)
                        st.rerun()
                    if st.button(
                        '삭제',
                        key=f"overview_task_delete_{task['id']}",
                        use_container_width=True,
                    ):
                        overview_service.delete_task(task['id'])
                        st.rerun()
