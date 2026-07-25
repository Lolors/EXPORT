from __future__ import annotations

from html import escape

import streamlit as st

from services import export_service, overview_service


STAGE_LABELS = {
    '출고 대기': '패킹 대기',
}

STAGE_CLASS = {
    '주문 접수': 'stage-order',
    '제품 준비': 'stage-product',
    '출고 대기': 'stage-shipment',
    '패킹 대기': 'stage-shipment',
    '패킹 완료': 'stage-packed',
    '완료': 'stage-complete',
}


st.title('대시보드')
st.caption('지금 진행 중인 수출 건과 직접 기록한 확인사항을 한 화면에서 관리합니다.')

st.markdown(
    '''
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlock"]:has(.export-table-anchor) {
        width: 70vw;
        max-width: 70vw;
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
    .export-table-wrap {
        width: 100%;
        overflow-x: auto;
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 14px;
    }
    .export-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 800px;
    }
    .export-table th {
        padding: 0.78rem 0.9rem;
        text-align: left;
        font-size: 0.9rem;
        font-weight: 800;
        background: rgba(247, 249, 252, 0.96);
        border-bottom: 1px solid rgba(49, 51, 63, 0.14);
        white-space: nowrap;
    }
    .export-table td {
        padding: 0.78rem 0.9rem;
        border-bottom: 1px solid rgba(49, 51, 63, 0.09);
        vertical-align: middle;
        white-space: nowrap;
    }
    .export-table tr:last-child td {
        border-bottom: 0;
    }
    .row-number {
        width: 3rem;
        text-align: center;
        font-weight: 750;
        color: #667085;
    }
    .stage-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.24rem 0.6rem;
        border-radius: 999px;
        font-size: 0.84rem;
        font-weight: 800;
        white-space: nowrap;
    }
    .stage-order { background: #eef1f5; color: #46505f; }
    .stage-product { background: #fff2cc; color: #7a5a00; }
    .stage-shipment { background: #dff3ff; color: #075f85; }
    .stage-packed { background: #e7e0ff; color: #5637a5; }
    .stage-complete { background: #dff5e7; color: #17683a; }
    .stage-default { background: #f1f1f1; color: #555; }
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
    rows = []
    for index, case in enumerate(cases, start=1):
        country = str(case['country'] or '').strip() or '국가 미입력'
        buyer = str(case['buyer'] or '').strip() or '바이어 미입력'
        transport = str(case['transport_mode'] or '').strip() or '운송방식 미입력'
        export_no = str(case['export_no'] or '').strip() or '수출번호 미입력'
        raw_stage = str(case['stage'] or '').strip() or '단계 미입력'
        stage = STAGE_LABELS.get(raw_stage, raw_stage)
        stage_class = STAGE_CLASS.get(stage, 'stage-default')
        rows.append(
            '<tr>'
            f'<td class="row-number">{index}</td>'
            f'<td>{escape(country)}</td>'
            f'<td>{escape(buyer)}</td>'
            f'<td>{escape(transport)}</td>'
            f'<td>{escape(export_no)}</td>'
            f'<td><span class="stage-badge {stage_class}">{escape(stage)}</span></td>'
            '</tr>'
        )

    with st.container():
        st.markdown('<div class="export-table-anchor"></div>', unsafe_allow_html=True)
        st.markdown(
            '''
            <div class="export-table-wrap">
                <table class="export-table">
                    <thead>
                        <tr>
                            <th>구분</th>
                            <th>국가</th>
                            <th>바이어</th>
                            <th>운송방식</th>
                            <th>수출번호</th>
                            <th>현재 단계</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            + ''.join(rows)
            + '''
                    </tbody>
                </table>
            </div>
            ''',
            unsafe_allow_html=True,
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
