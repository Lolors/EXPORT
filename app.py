from __future__ import annotations

import streamlit as st

import db
from config import APP_ICON, APP_LAYOUT, APP_TITLE
from services import order_save_guard, packing_service, shipment_service

PAGES = {
    '': [
        st.Page('pages/오버뷰.py', title='오버뷰', icon='📊', default=True),
        st.Page('pages/수출_주문_입력_및_수정.py', title='주문 입력', icon='📝'),
        st.Page('pages/주문_검색_및_수정_v2.py', title='주문 검색 및 수정', icon='🔎'),
        st.Page('pages/실출고_입력.py', title='수출대기 입고', icon='📦'),
        st.Page('pages/박스_패킹.py', title='박스 패킹', icon='📦'),
        st.Page('pages/국내배송.py', title='국내배송', icon='🚚'),
        st.Page('pages/공유문서.py', title='공유문서', icon='📄'),
        st.Page('pages/내_폴더.py', title='내 폴더', icon='📁'),
    ]
}


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
    db.init_db()

    # 주문 수정 저장 전 빈 매입가를 0으로 정리하고 중복 제품명을 검사한다.
    order_save_guard.install()

    # 수출대기 입고와 박스 패킹은 반드시 같은 현재 출고행 목록을 사용한다.
    packing_service.list_items = shipment_service.list_case_items

    st.navigation(PAGES, position='sidebar').run()


if __name__ == '__main__':
    main()
