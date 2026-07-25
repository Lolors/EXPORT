from __future__ import annotations

from collections import defaultdict
from html import escape

import streamlit as st

from services import export_service, overview_service


st.title('오버뷰')
st.caption('지금 진행 중인 수출 건과 직접 기록한 확인사항을 한 화면에서 관리합니다.')

st.markdown(
    '''
    <style>
    .overview-summary {
        padding: 1rem 1.15rem;
        border: 1px solid rgba(49, 51, 63, 0.16);
        border-radius: 16px;
        margin-bottom: 1rem;
        background: rgba(247, 249, 252, 0.72);
    }
    .overview-summary-number {
        font-size: 2rem;
        line-height: 1;
        font-weight: 850;
        margin-bottom: 0.35rem;
    }
    .overview-summary-label {
        font-size: 0.95rem;
        opacity: 0.72;
    }
    div[data-testid="stExpander"] {
        border-radius: 14px;
        overflow: hidden;
        margin-bottom: 0.65rem;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.export-card-anchor) {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 13px;
        padding: 0.85rem 1rem 0.8rem;
        margin: 0.25rem 0 0.65rem;
    }
    .export-card-anchor,
    .sticky-note-anchor {
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
    }
    .export-card-title {
        font-size: 1.02rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }
    .export-card-detail {
        font-size: 0.93rem;
        opacity: 0.82;
    }
    .stage-chip {
        display: inline-flex;
        padding: 0.22rem 0.55rem;
        border-radius: 999px;
        background: #edf3ff;
        color: #234f9b;
        font-weight: 750;
        font-size: 0.86rem;
        margin-top: 0.55rem;
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
    </style>
    ''',
    unsafe_allow_html=True,
)


cases = export_service.active_cases()
country_groups: dict[str, list] = defaultdict(list)
for case in cases:
    country = str(case['country'] or '').strip() or '국가 미입력'
    country_groups[country].append(case)

country_count = len(country_groups)
buyer_count = len({str(case['buyer'] or '').strip() or '바이어 미입력' for case in cases})
transport_count = len({str(case['transport_mode'] or '').strip() or '운송방식 미입력' for case in cases})

summary_cols = st.columns(4)
summary_values = [
    ('완료되지 않은 수출 건', f'{len(cases):,}건'),
    ('진행 국가', f'{country_count:,}개'),
    ('관련 바이어', f'{buyer_count:,}곳'),
    ('운송방식', f'{transport_count:,}종'),
]
for column, (label, value) in zip(summary_cols, summary_values):
    column.markdown(
        f'''
        <div class="overview-summary">
            <div class="overview-summary-number">{escape(value)}</div>
            <div class="overview-summary-label">{escape(label)}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

st.markdown('### 진행 중 수출 건')
if not cases:
    st.success('현재 완료되지 않은 수출 건이 없습니다.')
else:
    st.caption('국가별로 묶어서 바이어·운송방식·현재 단계를 보여줍니다.')
    for country in sorted(country_groups, key=str.casefold):
        country_cases = sorted(
            country_groups[country],
            key=lambda case: (
                str(case['stage'] or ''),
                str(case['buyer'] or ''),
                str(case['export_no'] or ''),
            ),
        )
        with st.expander(f'{country} · {len(country_cases)}건', expanded=True):
            for case in country_cases:
                buyer = str(case['buyer'] or '').strip() or '바이어 미입력'
                transport = str(case['transport_mode'] or '').strip() or '운송방식 미입력'
                export_no = str(case['export_no'] or '').strip() or '수출번호 미입력'
                stage = str(case['stage'] or '').strip() or '단계 미입력'
                with st.container():
                    st.markdown('<div class="export-card-anchor"></div>', unsafe_allow_html=True)
                    st.markdown(
                        f'''
                        <div class="export-card-title">{escape(buyer)}</div>
                        <div class="export-card-detail">
                            수출번호 <b>{escape(export_no)}</b> · 운송방식 <b>{escape(transport)}</b>
                        </div>
                        <div class="stage-chip">{escape(stage)}</div>
                        ''',
                        unsafe_allow_html=True,
                    )

st.divider()
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
    note_columns = st.columns(3)
    for index, task in enumerate(tasks):
        column = note_columns[index % 3]
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
