from __future__ import annotations

import streamlit as st

import db
from config import APP_ICON, APP_LAYOUT, APP_TITLE

PAGES = {
    '': [
        st.Page('pages/오버뷰.py', title='오버뷰', icon='📊', default=True),
        st.Page('pages/수출_주문_입력_및_수정.py', title='주문 입력', icon='📝'),
        st.Page('pages/주문_검색_및_수정.py', title='주문 검색 및 수정', icon='🔎'),
        st.Page('pages/실출고_입력.py', title='실출고 입력', icon='📦'),
        st.Page('pages/박스_패킹.py', title='박스 패킹', icon='📦'),
        st.Page('pages/국내배송.py', title='국내배송', icon='🚚'),
        st.Page('pages/공유문서.py', title='공유문서', icon='📄'),
        st.Page('pages/내_폴더.py', title='내 폴더', icon='📁'),
    ]
}


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
    db.init_db()
    st.navigation(PAGES, position='sidebar').run()


if __name__ == '__main__':
    main()
