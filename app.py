from __future__ import annotations

import streamlit as st

import db
from config import APP_ICON, APP_LAYOUT, APP_TITLE
from services import (
    order_save_guard,
    order_service,
    packing_service,
    product_name_match_service,
    shipment_service,
    usb_storage_service,
)

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


def _format_db_time(value) -> str:
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else '-'


def check_usb_restore_before_start() -> None:
    if st.session_state.get('usb_database_choice_complete'):
        return
    usb_path = usb_storage_service.usb_database_path()
    comparison = usb_storage_service.compare_databases(db.DB_PATH, usb_path)
    if not comparison['usb_is_newer']:
        st.session_state['usb_database_choice_complete'] = True
        return

    local = comparison['local']
    usb = comparison['usb']
    st.warning('USB에 현재 컴퓨터보다 최신인 export.db 백업이 있습니다.')
    st.write(
        f"로컬 DB: 버전 {local['version']} / {_format_db_time(local['modified_at'])}\n\n"
        f"USB DB: 버전 {usb['version']} / {_format_db_time(usb['modified_at'])}"
    )
    restore_col, keep_col = st.columns(2)
    if restore_col.button('USB 데이터로 복원', type='primary', use_container_width=True):
        try:
            for suffix in ('-wal', '-shm'):
                sidecar = db.DB_PATH.with_name(db.DB_PATH.name + suffix)
                if sidecar.exists():
                    sidecar.unlink()
            usb_storage_service.restore_database_from_usb(db.DB_PATH, usb_path)
            db._initialize_database_runtime.cache_clear()
            db.init_db.cache_clear()
            st.session_state['usb_database_choice_complete'] = True
            st.success('USB 백업을 로컬 DB로 복원했습니다.')
            st.rerun()
        except Exception as exc:
            st.error(f'USB DB 복원에 실패했습니다: {exc}')
    if keep_col.button('로컬 데이터 유지', use_container_width=True):
        st.session_state['usb_database_choice_complete'] = True
        st.rerun()
    st.stop()


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
    check_usb_restore_before_start()
    db.init_db()

    # 주문 수정 저장 전 빈 매입가를 0으로 정리하고 중복 제품명을 검사한다.
    order_service.normalize_product_name = product_name_match_service.normalize_for_match
    order_save_guard.install()

    # 수출대기 입고와 박스 패킹은 반드시 같은 현재 출고행 목록을 사용한다.
    packing_service.list_items = shipment_service.list_case_items

    st.navigation(PAGES, position='sidebar').run()


if __name__ == '__main__':
    main()
