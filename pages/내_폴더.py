from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import db


st.set_page_config(page_title='내 폴더', page_icon='📁', layout='wide')
db.init_db()


def browse_folder() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        selected = filedialog.askdirectory(title='내 폴더 선택')
        root.destroy()
        return selected or ''
    except Exception as exc:
        st.warning(f'폴더 선택 창을 열 수 없습니다. 경로를 직접 입력하세요. ({exc})')
        return ''


def check_folder_path(path_text: str) -> tuple[bool, str]:
    path_text = path_text.strip()
    if not path_text:
        return False, '내 폴더 위치를 입력하거나 선택하세요.'

    path = Path(path_text).expanduser()
    if os.name == 'nt' and path.drive:
        drive_root = Path(f'{path.drive}\\')
        if not drive_root.exists():
            return False, f'{path.drive} 드라이브를 찾을 수 없습니다. USB가 연결되어 있는지 확인하세요.'

    ok, message = db.test_storage_root(path_text)
    if not ok:
        return False, f'선택한 폴더에 저장할 수 없습니다.\n\n원인: {message}'
    return True, message


st.title('내 폴더')
st.caption('수출 관련 문서와 출고사진을 저장할 최상위 폴더를 설정하고 전체 수출 폴더를 정리합니다.')

current_root = db.get_setting('shared_root').strip()
if 'folder_path_input' not in st.session_state:
    st.session_state['folder_path_input'] = current_root
if 'pending_folder_path' in st.session_state:
    st.session_state['folder_path_input'] = st.session_state.pop('pending_folder_path')

st.info(
    '설정한 내 폴더 아래에 국가 / 연도 / 수출건 폴더가 자동 생성됩니다. '
    '경로를 설정하지 않으면 프로그램 폴더의 uploads를 사용합니다.'
)

c1, c2 = st.columns([5, 1])
with c2:
    st.write('')
    st.write('')
    if st.button('폴더 찾아보기', use_container_width=True):
        selected = browse_folder()
        if selected:
            st.session_state['pending_folder_path'] = selected
            st.rerun()

with c1:
    folder_text = st.text_input(
        '내 폴더 위치',
        key='folder_path_input',
        placeholder=r'예: E:\수출관리 또는 \\NAS\수출관리',
    )

b1, b2, b3 = st.columns(3)
if b1.button('경로 검사', use_container_width=True):
    ok, message = check_folder_path(folder_text)
    if ok:
        st.success(f'읽기·쓰기 확인 완료\n\n{message}')
    else:
        st.error(message)

if b2.button('설정 저장', type='primary', use_container_width=True):
    ok, message = check_folder_path(folder_text)
    if ok:
        saved_path = str(Path(folder_text).expanduser())
        db.set_setting('shared_root', saved_path)
        st.success(f'내 폴더 위치를 저장했습니다.\n\n{message}')
    else:
        st.error(message)

if b3.button('기본 uploads 사용', use_container_width=True):
    db.set_setting('shared_root', '')
    st.session_state['pending_folder_path'] = ''
    st.rerun()

st.divider()
st.markdown('#### 현재 저장 위치')
saved_root = db.get_setting('shared_root').strip()
st.code(saved_root or str(db.UPLOAD_DIR.resolve()))

if saved_root:
    saved_ok, saved_message = check_folder_path(saved_root)
    if saved_ok:
        st.success('현재 내 폴더에 정상적으로 연결되어 있습니다.')
    else:
        st.warning(saved_message)

st.markdown('#### 자동 생성 예시')
st.code(
    '''내 폴더
└─ 미국
   └─ 2026
      ├─ EXP-2026-001_비고
      ├─ 0715_바이어_AIR_비고
      └─ [취소]0715_바이어_AIR_비고'''
)

st.caption(
    '폴더 찾아보기는 Streamlit이 실행되는 컴퓨터에서만 동작합니다. '
    'USB를 분리하면 저장할 수 없으므로 작업 전에 현재 연결 상태를 확인하세요.'
)

st.divider()
st.markdown('#### 수출 폴더 관리')
st.caption('모든 수출 건의 폴더를 현재 국가 / 연도 / 폴더명 규칙에 맞게 다시 생성하거나 정리합니다.')
folder_confirm = st.checkbox(
    '기존 폴더를 현재 구조로 이동·정리하는 것에 동의합니다.',
    key='folder_rebuild_confirm',
)

if st.button('모든 수출 폴더 재생성·정리', type='primary', disabled=not folder_confirm):
    all_cases = db.rows('SELECT id, export_no FROM export_cases ORDER BY id')
    successes: list[str] = []
    failures: list[str] = []
    progress = st.progress(0, text='수출 폴더를 확인하고 있습니다.')
    total = max(len(all_cases), 1)

    for index, case in enumerate(all_cases, start=1):
        try:
            folder = db.sync_case_folder(int(case['id']))
            successes.append(f"{case['export_no']} → {folder}")
        except Exception as exc:
            failures.append(f"{case['export_no']}: {exc}")
        progress.progress(index / total, text=f'{index}/{len(all_cases)} 처리 중')

    progress.empty()
    if successes:
        db.add_history(None, '전체 수출 폴더 재정리', f'{len(successes)}건 완료 / {len(failures)}건 실패')
        st.success(f'{len(successes)}건의 폴더를 생성·정리했습니다.')
    if failures:
        st.error('일부 폴더를 처리하지 못했습니다.\n\n' + '\n'.join(f'- {item}' for item in failures))
