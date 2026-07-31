from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from services import export_service, overview_service
from services.dashboard_view_service import (
    order_products_summary as _order_products_summary,
    recent_order_cases,
    recent_order_period_label,
    stage_label,
    stage_style as _stage_style,
    timeline_date,
    timeline_date_label,
)


st.title('대시보드')
st.caption('타임라인 기준 최근 2개월 주문과 직접 기록한 확인사항을 한 화면에서 관리합니다.')

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
    .order-timeline {
        position: relative;
        margin: 0.35rem 0 1.4rem 0.35rem;
        padding-left: 1.55rem;
    }
    .order-timeline::before {
        content: "";
        position: absolute;
        top: 0.55rem;
        bottom: 0.45rem;
        left: 0.35rem;
        width: 3px;
        border-radius: 3px;
        background: linear-gradient(#5b8def, #c6d5f4);
    }
    .timeline-day {
        position: relative;
        margin: 0 0 1.1rem;
    }
    .timeline-day::before {
        content: "";
        position: absolute;
        top: 0.42rem;
        left: -1.55rem;
        width: 0.78rem;
        height: 0.78rem;
        border: 3px solid #5b8def;
        border-radius: 50%;
        background: white;
        box-shadow: 0 0 0 3px rgba(91, 141, 239, 0.13);
    }
    .timeline-date {
        margin-bottom: 0.48rem;
        color: #315d9b;
        font-size: 0.94rem;
        font-weight: 800;
    }
    .timeline-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 0.55rem;
    }
    .timeline-card {
        padding: 0.78rem 0.9rem;
        border: 1px solid rgba(91, 141, 239, 0.22);
        border-radius: 10px;
        background: #fff;
        box-shadow: 0 3px 10px rgba(36, 58, 95, 0.06);
    }
    .timeline-card-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.3rem;
    }
    .timeline-export-no { font-weight: 800; color: #243b62; }
    .timeline-stage {
        padding: 0.13rem 0.5rem;
        border-radius: 999px;
        background: #eef3fb;
        color: #46658f;
        font-size: 0.77rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .timeline-party { font-size: 0.88rem; color: #3f4855; }
    .timeline-products { margin-top: 0.22rem; font-size: 0.82rem; color: #77808d; }
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

cases = recent_order_cases(
    export_service.list_cases(),
    month_count=2,
)
cases = sorted(
    cases,
    key=lambda case: (
        timeline_date(case),
        str(case['country'] or '').casefold(),
        str(case['buyer'] or '').casefold(),
        str(case['export_no'] or '').casefold(),
    ),
    reverse=True,
)

st.markdown(f'### 최근 2개월 주문 건 ({recent_order_period_label(month_count=2)})')
if not cases:
    st.info('타임라인 기준 최근 2개월 주문 건이 없습니다.')
else:
    timeline_groups: dict[str, list] = {}
    for case in cases:
        timeline_groups.setdefault(timeline_date(case), []).append(case)

    timeline_html = ['<div class="order-timeline">']
    for date_value, date_cases in timeline_groups.items():
        timeline_html.append(
            '<section class="timeline-day">'
            f'<div class="timeline-date">{escape(timeline_date_label(date_value))} · '
            f'{len(date_cases)}건</div><div class="timeline-cards">'
        )
        for case in date_cases:
            raw_stage = str(case['stage'] or '').strip() or '단계 미입력'
            country = str(case['country'] or '').strip() or '국가 미입력'
            buyer = str(case['buyer'] or '').strip() or '바이어 미입력'
            timeline_html.append(
                '<article class="timeline-card">'
                '<div class="timeline-card-head">'
                f'<span class="timeline-export-no">{escape(str(case["export_no"] or "수출번호 미입력"))}</span>'
                f'<span class="timeline-stage">{escape(stage_label(raw_stage))}</span>'
                '</div>'
                f'<div class="timeline-party">{escape(country)} · {escape(buyer)}</div>'
                f'<div class="timeline-products">{escape(_order_products_summary(int(case["id"])))}</div>'
                '</article>'
            )
        timeline_html.append('</div></section>')
    timeline_html.append('</div>')
    st.markdown(''.join(timeline_html), unsafe_allow_html=True)

    with st.expander('주문 표로 보기', expanded=True):
        st.caption('아래 표에서는 컬럼별 정렬과 검색을 사용할 수 있습니다.')
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
                    '현재 단계': stage_label(raw_stage),
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
