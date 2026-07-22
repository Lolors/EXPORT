from __future__ import annotations

import streamlit as st

import db


st.set_page_config(page_title='수출 취소', page_icon='🚫', layout='wide')
db.init_db()


def case_label(case) -> str:
    buyer = f" · {case['buyer']}" if case['buyer'] else ''
    return f"{case['export_no']} · {case['country']}{buyer} · {case['stage']}"


st.title('수출 취소')
st.caption('수출 건을 삭제하지 않고 취소 상태로 변경합니다. 취소 사유와 일시는 기록되며 폴더명에는 [취소]가 붙습니다.')

active_cases = db.rows(
    "SELECT * FROM export_cases WHERE status<>'취소' AND stage<>'취소' ORDER BY expected_ship_date, created_at"
)

if active_cases:
    options = {case_label(case): int(case['id']) for case in active_cases}
    selected_label = st.selectbox('취소할 수출 건', list(options), key='cancel_case')
    case_id = options[selected_label]
    case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))

    st.info(
        f"수출번호: {case['export_no']}\n\n"
        f"국가: {case['country']}\n\n"
        f"바이어: {case['buyer'] or '-'}\n\n"
        f"현재 단계: {case['stage']}"
    )

    reason = st.text_area('취소 사유 *', key=f'cancel_reason_{case_id}', placeholder='취소 사유를 입력하세요.')
    confirmed = st.checkbox('이 수출 건을 삭제하지 않고 취소 처리하는 것에 동의합니다.', key=f'cancel_confirm_{case_id}')

    if st.button('수출 취소 처리', type='primary', disabled=not confirmed, key=f'cancel_submit_{case_id}'):
        clean_reason = reason.strip()
        if not clean_reason:
            st.error('취소 사유를 입력하세요.')
        else:
            previous_stage = case['stage'] or '주문 접수'
            cancelled_at = db.now_text()
            db.execute(
                '''UPDATE export_cases
                   SET previous_stage=?, stage='취소', status='취소', cancel_reason=?,
                       cancelled_at=?, updated_at=?
                   WHERE id=?''',
                (previous_stage, clean_reason, cancelled_at, cancelled_at, case_id),
            )
            folder = db.sync_case_folder(case_id)
            db.add_history(case_id, '수출 취소', f'{clean_reason} / {folder}')
            st.success(f'취소 처리했습니다.\n\n폴더: {folder}')
            st.rerun()
else:
    st.info('취소할 수출 건이 없습니다.')

st.divider()
st.subheader('취소 건 복원')

cancelled_cases = db.rows(
    "SELECT * FROM export_cases WHERE status='취소' OR stage='취소' ORDER BY cancelled_at DESC, updated_at DESC"
)

if not cancelled_cases:
    st.caption('복원할 취소 건이 없습니다.')
else:
    restore_options = {case_label(case): int(case['id']) for case in cancelled_cases}
    restore_label = st.selectbox('복원할 수출 건', list(restore_options), key='restore_case')
    restore_id = restore_options[restore_label]
    restore_case = db.row('SELECT * FROM export_cases WHERE id=?', (restore_id,))

    st.caption(f"취소 사유: {restore_case['cancel_reason'] or '-'}")
    restore_confirmed = st.checkbox('이 수출 건의 취소를 해제하고 이전 단계로 복원합니다.', key=f'restore_confirm_{restore_id}')

    if st.button('취소 건 복원', disabled=not restore_confirmed, key=f'restore_submit_{restore_id}'):
        restored_stage = restore_case['previous_stage'] or '주문 접수'
        restored_status = '완료' if restored_stage == '완료' else '진행중'
        now = db.now_text()
        db.execute(
            '''UPDATE export_cases
               SET stage=?, status=?, cancel_reason='', cancelled_at='', previous_stage='', updated_at=?
               WHERE id=?''',
            (restored_stage, restored_status, now, restore_id),
        )
        folder = db.sync_case_folder(restore_id)
        db.add_history(restore_id, '수출 취소 복원', f'{restored_stage} / {folder}')
        st.success(f'복원했습니다.\n\n폴더: {folder}')
        st.rerun()
