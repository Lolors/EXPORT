from __future__ import annotations

import streamlit as st

import db

st.set_page_config(page_title='수출 취소', page_icon='🚫', layout='wide')
db.init_db()

st.title('수출 취소')
st.caption('수출 건을 삭제하지 않고 취소 처리합니다. 기존 문서와 출고사진은 그대로 유지됩니다.')

cancel_tab, restore_tab = st.tabs(['수출 취소', '취소 건 복원'])

with cancel_tab:
    active = db.active_cases()
    if not active:
        st.info('취소할 수 있는 진행 중 수출 건이 없습니다.')
    else:
        labels = {
            f"{case['export_no']} | {case['country']} | {case['buyer'] or '바이어 미입력'} | {case['stage']}": int(case['id'])
            for case in active
        }
        selected_label = st.selectbox('취소할 수출 건', list(labels), key='cancel_case_select')
        case_id = labels[selected_label]
        case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('수출번호', case['export_no'])
        c2.metric('국가', case['country'])
        c3.metric('바이어', case['buyer'] or '-')
        c4.metric('현재 단계', case['stage'])
        if case['folder_path']:
            st.caption(f"현재 폴더: {case['folder_path']}")

        with st.form(f'cancel_form_{case_id}'):
            reason_type = st.selectbox(
                '취소사유 *',
                ['바이어 주문 취소', '재고 부족', '생산 중단', '가격 협상 결렬', '중복 등록', '기타'],
            )
            other_reason = st.text_input('기타 사유', disabled=reason_type != '기타')
            st.info('취소 시 폴더명 앞에 [취소]가 붙습니다. 문서와 출고사진은 삭제하지 않고 그대로 유지합니다.')
            confirm = st.checkbox('해당 수출 건을 취소 처리하는 것에 동의합니다.')
            submitted = st.form_submit_button('수출 취소', type='primary')

        if submitted:
            reason = other_reason.strip() if reason_type == '기타' else reason_type
            if not confirm:
                st.error('취소 확인란을 선택하세요.')
            elif not reason:
                st.error('취소사유를 입력하세요.')
            else:
                try:
                    folder = db.cancel_case(case_id, reason)
                    st.success(f'수출 건을 취소했습니다. 문서와 사진은 유지됩니다.\n\n폴더: {folder}')
                    st.rerun()
                except Exception as exc:
                    st.error(f'취소 처리 중 오류가 발생했습니다: {exc}')

with restore_tab:
    cancelled = db.rows(
        "SELECT * FROM export_cases WHERE status='취소' OR stage='취소' ORDER BY cancelled_at DESC, updated_at DESC"
    )
    if not cancelled:
        st.info('복원할 취소 수출 건이 없습니다.')
    else:
        labels = {
            f"{case['export_no']} | {case['country']} | {case['buyer'] or '바이어 미입력'} | {case['cancelled_at'] or '취소일 미기록'}": int(case['id'])
            for case in cancelled
        }
        selected_label = st.selectbox('복원할 수출 건', list(labels), key='restore_case_select')
        case_id = labels[selected_label]
        case = db.row('SELECT * FROM export_cases WHERE id=?', (case_id,))

        c1, c2, c3 = st.columns(3)
        c1.metric('수출번호', case['export_no'])
        c2.metric('취소일', case['cancelled_at'] or '-')
        c3.metric('복원 단계', case['previous_stage'] or '주문 접수')
        st.write(f"**취소사유:** {case['cancel_reason'] or '-'}")
        if case['folder_path']:
            st.caption(f"현재 폴더: {case['folder_path']}")

        st.info('복원하면 폴더명 앞의 [취소] 접두사가 제거되고 취소 전 단계로 돌아갑니다.')
        if st.button('진행중으로 복원', type='primary'):
            try:
                folder = db.restore_cancelled_case(case_id)
                st.success(f'수출 건을 복원했습니다. 폴더: {folder}')
                st.rerun()
            except Exception as exc:
                st.error(f'복원 처리 중 오류가 발생했습니다: {exc}')
