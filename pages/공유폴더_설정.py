from __future__ import annotations

from pathlib import Path

import streamlit as st

import db


st.set_page_config(page_title='공유폴더 설정', page_icon='📁', layout='wide')
db.init_db()


def browse_folder() -> str:
    """로컬 Windows에서 폴더 선택 창을 엽니다."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(title='기존 수출 관련 폴더 선택')
        root.destroy()
        return selected or ''
    except Exception as exc:
        st.warning(f'폴더 선택 창을 열 수 없습니다. 경로를 직접 입력하세요. ({exc})')
        return ''


st.title('공유폴더 설정')
st.caption('기존 수출 관련 폴더의 최상위 위치를 설정합니다.')

current_root = db.get_setting('shared_root').strip()
if 'shared_root_input' not in st.session_state:
    st.session_state.shared_root_input = current_root

st.info(
    '설정한 폴더 아래에 국가 / 연도 / 수출건 폴더가 자동 생성됩니다. '
    '경로를 설정하지 않으면 프로그램 폴더의 uploads를 사용합니다.'
)

c1, c2 = st.columns([5, 1])
with c1:
    folder_text = st.text_input(
        '기존 수출 관련 폴더 위치',
        key='shared_root_input',
        placeholder=r'예: Z:\회사공유폴더\수출 또는 \\NAS\공유폴더\수출',
    )
with c2:
    st.write('')
    st.write('')
    if st.button('폴더 찾아보기', use_container_width=True):
        selected = browse_folder()
        if selected:
            st.session_state.shared_root_input = selected
            st.rerun()

b1, b2, b3 = st.columns(3)
if b1.button('연결 확인', use_container_width=True):
    ok, message = db.test_storage_root(folder_text)
    if ok:
        st.success(f'읽기·쓰기 확인 완료: {message}')
    else:
        st.error(f'폴더에 연결할 수 없습니다: {message}')

if b2.button('설정 저장', type='primary', use_container_width=True):
    ok, message = db.test_storage_root(folder_text)
    if ok:
        db.set_setting('shared_root', str(Path(folder_text).expanduser()))
        st.success(f'공유폴더 위치를 저장했습니다: {message}')
    else:
        st.error(f'저장하지 못했습니다: {message}')

if b3.button('기본 uploads 사용', use_container_width=True):
    db.set_setting('shared_root', '')
    st.session_state.shared_root_input = ''
    st.success('공유폴더 설정을 해제했습니다. 이제 프로그램의 uploads 폴더를 사용합니다.')
    st.rerun()

st.divider()
st.markdown('#### 현재 저장 위치')
saved_root = db.get_setting('shared_root').strip()
st.code(saved_root or str(db.UPLOAD_DIR.resolve()))

st.markdown('#### 자동 생성 예시')
st.code(
    '''선택한 수출 폴더
└─ 미국
   └─ 2026
      ├─ EXP-2026-001_비고
      └─ 0715_바이어_AIR_비고'''
)

st.caption(
    '폴더 찾아보기는 Streamlit이 실행되는 컴퓨터에서만 동작합니다. '
    'NAS나 네트워크 공유폴더는 UNC 경로를 직접 입력해도 됩니다.'
)
