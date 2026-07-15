from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import db
from export_excel import build_packing_list

st.set_page_config(page_title="NTP Export", page_icon="🌏", layout="wide")
db.init_db()


def rerun() -> None:
    st.rerun()


def df(query: str, params: tuple = ()) -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in db.rows(query, params)])


def selected_case_id() -> int | None:
    case_rows = db.case_summary()
    if not case_rows:
        return None
    options = {f"{r['export_no']} | {r['buyer']} | {r['stage']}": r["id"] for r in case_rows}
    label = st.sidebar.selectbox("수출 건 선택", list(options.keys()))
    return int(options[label])


def save_case(case_id: int | None, data: dict) -> int:
    now = db.now_text()
    if case_id:
        old = db.row("SELECT * FROM export_cases WHERE id = ?", (case_id,))
        db.execute(
            """
            UPDATE export_cases
               SET export_no=?, buyer=?, country=?, manager=?, expected_ship_date=?, stage=?, status=?,
                   invoice_no=?, incoterms=?, transport_mode=?, port_loading=?, final_destination=?, memo=?, updated_at=?
             WHERE id=?
            """,
            (
                data["export_no"], data["buyer"], data["country"], data["manager"], data["expected_ship_date"],
                data["stage"], data["status"], data["invoice_no"], data["incoterms"], data["transport_mode"],
                data["port_loading"], data["final_destination"], data["memo"], now, case_id,
            ),
        )
        if old and old["stage"] != data["stage"]:
            db.add_history(case_id, "진행 단계 변경", f"{old['stage']} → {data['stage']}")
        db.add_history(case_id, "수출 건 수정", f"{data['export_no']} 정보를 수정했습니다.")
        return case_id

    new_id = db.execute(
        """
        INSERT INTO export_cases(export_no, buyer, country, manager, expected_ship_date, stage, status,
                                 invoice_no, incoterms, transport_mode, port_loading, final_destination, memo,
                                 created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["export_no"], data["buyer"], data["country"], data["manager"], data["expected_ship_date"],
            data["stage"], data["status"], data["invoice_no"], data["incoterms"], data["transport_mode"],
            data["port_loading"], data["final_destination"], data["memo"], now, now,
        ),
    )
    db.create_default_documents(new_id)
    db.add_history(new_id, "수출 건 등록", f"{data['export_no']} 수출 건을 등록했습니다.")
    return new_id


st.title("🌏 NTP Export")
st.caption("수출 건, 제품, 박스 포장, 서류, 첨부파일, 변경 이력, Packing List 엑셀 내보내기를 관리합니다.")

with st.sidebar:
    st.header("메뉴")
    menu = st.radio("이동", ["수출 건", "제품 관리", "포장 등록", "서류 체크리스트", "파일 첨부", "이력", "엑셀 내보내기"], label_visibility="collapsed")
    case_id = selected_case_id()

if menu == "수출 건":
    st.subheader("수출 건 등록·수정")
    summaries = db.case_summary()
    if summaries:
        st.dataframe(pd.DataFrame([dict(r) for r in summaries]), use_container_width=True, hide_index=True)
    else:
        st.info("아직 등록된 수출 건이 없습니다. 아래에서 첫 수출 건을 등록하세요.")

    edit_case = db.row("SELECT * FROM export_cases WHERE id = ?", (case_id,)) if case_id else None
    is_new = st.toggle("새 수출 건 등록", value=edit_case is None)
    target = None if is_new else edit_case

    with st.form("case_form"):
        c1, c2, c3 = st.columns(3)
        export_no = c1.text_input("수출관리번호", value=(db.next_export_no() if is_new else target["export_no"]))
        buyer = c2.text_input("바이어", value=("" if is_new else target["buyer"]))
        country = c3.text_input("국가", value=("" if is_new else target["country"]))
        manager = c1.text_input("담당자", value=("" if is_new else target["manager"]))
        expected_ship_date = c2.text_input("출고예정일", value=("" if is_new else target["expected_ship_date"]), placeholder="2026-07-30")
        stage = c3.selectbox("진행 단계", db.STAGES, index=db.STAGES.index(target["stage"]) if target and target["stage"] in db.STAGES else 0)
        status = c1.selectbox("상태", ["진행중", "보류", "완료", "취소"], index=0 if is_new else ["진행중", "보류", "완료", "취소"].index(target["status"]) if target["status"] in ["진행중", "보류", "완료", "취소"] else 0)
        invoice_no = c2.text_input("Invoice No.", value=("" if is_new else target["invoice_no"]))
        incoterms = c3.text_input("Incoterms", value=("" if is_new else target["incoterms"]), placeholder="CIP TOKYO")
        transport_mode = c1.text_input("운송 방식", value=("" if is_new else target["transport_mode"]), placeholder="AIR / SEA")
        port_loading = c2.text_input("선적지", value=("" if is_new else target["port_loading"]), placeholder="INCHEON, KOREA")
        final_destination = c3.text_input("최종 도착지", value=("" if is_new else target["final_destination"]))
        memo = st.text_area("메모", value=("" if is_new else target["memo"]))
        submitted = st.form_submit_button("저장")

    if submitted:
        if not export_no.strip() or not buyer.strip():
            st.error("수출관리번호와 바이어는 필수입니다.")
        else:
            new_id = save_case(None if is_new else int(target["id"]), locals())
            st.success(f"저장 완료: {export_no}")
            rerun()

elif menu == "제품 관리":
    st.subheader("제품 등록")
    products = df("SELECT * FROM products ORDER BY product_name")
    st.dataframe(products, use_container_width=True, hide_index=True)
    with st.form("product_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        product_name = c1.text_input("제품명")
        spec = c2.text_input("규격")
        unit = c3.text_input("단위", value="EA")
        hs_code = c1.text_input("HS Code")
        note = st.text_area("비고")
        submitted = st.form_submit_button("제품 추가")
    if submitted:
        if not product_name.strip():
            st.error("제품명을 입력하세요.")
        else:
            now = db.now_text()
            db.execute("INSERT INTO products(product_name, spec, unit, hs_code, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (product_name, spec, unit, hs_code, note, now, now))
            db.add_history(case_id, "제품 등록", product_name)
            st.success("제품을 추가했습니다.")
            rerun()

elif menu == "포장 등록":
    st.subheader("박스별 포장 등록")
    if not case_id:
        st.warning("먼저 수출 건을 등록하세요.")
        st.stop()
    items = df("SELECT * FROM packing_items WHERE case_id = ? ORDER BY box_no, id", (case_id,))
    st.dataframe(items, use_container_width=True, hide_index=True)
    products = db.rows("SELECT * FROM products ORDER BY product_name")
    product_options = {"직접 입력": None} | {f"{p['product_name']} / {p['spec']}": p for p in products}
    with st.form("packing_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        box_no = c1.number_input("BOX No.", min_value=1, step=1)
        marks = c2.text_input("Marks", value="NTP")
        selected = c3.selectbox("제품 선택", list(product_options.keys()))
        selected_product = product_options[selected]
        product_name = st.text_input("제품명", value="" if selected_product is None else selected_product["product_name"])
        lot_no = c1.text_input("LOT(내부관리용)")
        expiry_date = c2.text_input("유통기한(내부관리용)", placeholder="2028-07-01")
        quantity = c3.number_input("수량", min_value=0.0, step=1.0)
        unit = c4.text_input("단위", value="EA" if selected_product is None else selected_product["unit"])
        net_weight = c1.number_input("순중량 kg", min_value=0.0, step=0.1)
        gross_weight = c2.number_input("총중량 kg", min_value=0.0, step=0.1)
        length_cm = c3.number_input("가로 cm", min_value=0.0, step=1.0)
        width_cm = c4.number_input("세로 cm", min_value=0.0, step=1.0)
        height_cm = c1.number_input("높이 cm", min_value=0.0, step=1.0)
        note = st.text_area("비고")
        submitted = st.form_submit_button("포장 행 추가")
    if submitted:
        if not product_name.strip():
            st.error("제품명을 입력하세요.")
        else:
            now = db.now_text()
            db.execute(
                """
                INSERT INTO packing_items(case_id, box_no, marks, product_id, product_name, lot_no, expiry_date,
                                          quantity, unit, net_weight, gross_weight, length_cm, width_cm, height_cm,
                                          note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, box_no, marks, selected_product["id"] if selected_product else None, product_name, lot_no, expiry_date, quantity, unit, net_weight, gross_weight, length_cm, width_cm, height_cm, note, now, now),
            )
            db.add_history(case_id, "포장 등록", f"BOX {box_no} / {product_name} / {quantity:g}{unit}")
            st.success("포장 행을 추가했습니다.")
            rerun()

elif menu == "서류 체크리스트":
    st.subheader("서류 체크리스트")
    if not case_id:
        st.warning("먼저 수출 건을 등록하세요.")
        st.stop()
    docs = db.rows("SELECT * FROM documents WHERE case_id = ? ORDER BY id", (case_id,))
    for doc in docs:
        c1, c2 = st.columns([1, 3])
        done = c1.checkbox(doc["doc_name"], value=bool(doc["is_done"]), key=f"doc_{doc['id']}")
        note = c2.text_input("메모", value=doc["note"], key=f"note_{doc['id']}", label_visibility="collapsed")
        if done != bool(doc["is_done"]) or note != doc["note"]:
            db.execute("UPDATE documents SET is_done=?, note=?, updated_at=? WHERE id=?", (1 if done else 0, note, db.now_text(), doc["id"]))
            db.add_history(case_id, "서류 체크 변경", f"{doc['doc_name']}: {'완료' if done else '미완료'}")
            rerun()
    with st.form("add_doc", clear_on_submit=True):
        new_doc = st.text_input("추가 서류명")
        submitted = st.form_submit_button("서류 추가")
    if submitted and new_doc.strip():
        db.execute("INSERT OR IGNORE INTO documents(case_id, doc_name, updated_at) VALUES (?, ?, ?)", (case_id, new_doc, db.now_text()))
        db.add_history(case_id, "서류 추가", new_doc)
        rerun()

elif menu == "파일 첨부":
    st.subheader("파일 첨부")
    if not case_id:
        st.warning("먼저 수출 건을 등록하세요.")
        st.stop()
    uploaded = st.file_uploader("관련 파일 업로드", accept_multiple_files=True)
    category = st.text_input("분류", placeholder="PO, COA, Invoice, 라벨 시안 등")
    if st.button("첨부 저장") and uploaded:
        case_dir = db.UPLOAD_DIR / str(case_id)
        case_dir.mkdir(parents=True, exist_ok=True)
        for file in uploaded:
            stored = case_dir / file.name
            stored.write_bytes(file.getbuffer())
            db.execute("INSERT INTO attachments(case_id, file_name, stored_path, category, uploaded_at) VALUES (?, ?, ?, ?, ?)", (case_id, file.name, str(stored), category, db.now_text()))
            db.add_history(case_id, "파일 첨부", file.name)
        st.success("파일을 저장했습니다.")
        rerun()
    attachments = df("SELECT id, file_name, category, stored_path, uploaded_at FROM attachments WHERE case_id = ? ORDER BY uploaded_at DESC", (case_id,))
    st.dataframe(attachments, use_container_width=True, hide_index=True)

elif menu == "이력":
    st.subheader("변경 이력")
    if not case_id:
        st.warning("먼저 수출 건을 등록하세요.")
        st.stop()
    history = df("SELECT created_at, action, detail FROM history WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
    st.dataframe(history, use_container_width=True, hide_index=True)

elif menu == "엑셀 내보내기":
    st.subheader("Packing List 엑셀 내보내기")
    if not case_id:
        st.warning("먼저 수출 건을 등록하세요.")
        st.stop()
    case = db.row("SELECT * FROM export_cases WHERE id = ?", (case_id,))
    include_lot = st.checkbox("Packing List에 LOT 표시", value=False)
    include_expiry = st.checkbox("Packing List에 유통기한 표시", value=False)
    st.caption("LOT/유통기한은 내부 데이터에는 저장하지만, 회사 양식에 맞게 출력에서는 기본 숨김으로 처리했습니다.")
    data = build_packing_list(case_id, include_lot=include_lot, include_expiry=include_expiry)
    st.download_button(
        "Packing List 다운로드",
        data=data,
        file_name=f"{case['export_no']}_packing_list.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
