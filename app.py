from __future__ import annotations
from pathlib import Path
import time
import pandas as pd
import streamlit as st
import db
from export_excel import build_packing_export

st.set_page_config(page_title='수출관리', page_icon='🌏', layout='wide')
db.init_db()

def dataframe(query, params=()): return pd.DataFrame([dict(r) for r in db.rows(query,params)])
def rerun(): st.rerun()
def case_label(r): return f"{r['export_no']} | {r['country']} | {r['buyer'] or '바이어 미입력'} | {r['stage']}"
def choose_active_case(key, country=None):
    cases=db.active_cases(country)
    if not cases: return None
    options={case_label(r):int(r['id']) for r in cases}
    return options[st.selectbox('진행 중 수출 건',list(options),key=key)]

def replace_order_items(case_id, edited):
    db.execute('DELETE FROM order_items WHERE case_id=?',(case_id,))
    vals=[]
    for _,r in edited.iterrows():
        name=str(r.get('제품명','')).strip()
        if name:
            vals.append((case_id,name,float(r.get('수량',0) or 0),str(r.get('단위','EA') or 'EA'),db.now_text()))
    if vals: db.executemany('INSERT INTO order_items(case_id,product_name,quantity,unit,created_at) VALUES (?,?,?,?,?)',vals)

def save_shipment_editor(case_id, edited):
    db.execute('DELETE FROM shipment_items WHERE case_id=?',(case_id,))
    vals=[]
    for _,r in edited.iterrows():
        name=str(r.get('제품명','')).strip()
        if name:
            vals.append((case_id,str(r.get('사업장','')),str(r.get('로케이션','')),name,str(r.get('LOT','')),str(r.get('유통기한','')),float(r.get('요청수량',0) or 0),None,db.now_text(),db.now_text()))
    if vals: db.executemany('''INSERT INTO shipment_items(case_id,business_unit,location,product_name,lot_no,expiry_date,requested_qty,box_no,created_at,updated_at)
                              VALUES (?,?,?,?,?,?,?,?,?,?)''',vals)

st.title('수출관리')
st.caption('Export Management System')
menu=st.sidebar.radio('메뉴',['오버뷰','수출 주문 입력','실출고 입력','박스 패킹','패킹 결과·배송·엑셀','출고 사진'],label_visibility='collapsed')

if menu=='오버뷰':
    st.subheader('진행 중 수출 오버뷰')
    cases=db.active_cases()
    if not cases: st.info('현재 진행 중인 수출 건이 없습니다.')
    for c in cases:
        orders=db.rows('SELECT product_name,quantity,unit FROM order_items WHERE case_id=? ORDER BY id',(c['id'],))
        title=f"{c['export_no']} · {c['country']} · {c['stage']}"+(f" · {c['buyer']}" if c['buyer'] else '')
        with st.expander(title):
            if orders:
                st.dataframe(pd.DataFrame([{'제품명':o['product_name'],'수량':o['quantity'],'단위':o['unit']} for o in orders]),hide_index=True,use_container_width=True)
            else: st.caption('주문 제품이 아직 입력되지 않았습니다.')
            cols=st.columns(4); cols[0].metric('국가',c['country']); cols[1].metric('운송',c['transport_mode']); cols[2].metric('예상 출고일',c['expected_ship_date'] or '-'); cols[3].metric('단계',c['stage'])

elif menu=='수출 주문 입력':
    st.subheader('수출 주문 등록')
    with st.form('new_case'):
        st.text_input('수출번호',value=db.next_export_no(),disabled=True)
        c1,c2,c3=st.columns(3)
        country=c1.text_input('국가 *'); buyer=c2.text_input('바이어 (선택)'); expected=c3.date_input('예상출고일')
        transport=c1.selectbox('운송방식',db.TRANSPORT_MODES); stage=c2.selectbox('현재 진행 단계',db.STAGES[:5]); submitted=st.form_submit_button('수출 건 생성')
    if submitted:
        if not country.strip(): st.error('국가는 필수입니다.')
        else:
            no=db.next_export_no(); now=db.now_text(); cid=db.execute('''INSERT INTO export_cases(export_no,buyer,country,expected_ship_date,transport_mode,stage,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)''',(no,buyer,country,str(expected),transport,stage,'진행중',now,now)); db.add_history(cid,'수출 건 생성',no); st.session_state['order_case']=cid; st.success(f'{no} 생성 완료')
    cid=st.session_state.get('order_case')
    active=db.active_cases(); opts={case_label(r):int(r['id']) for r in active}
    if opts:
        cid=opts[st.selectbox('주문 목록을 입력할 수출 건',list(opts),index=list(opts.values()).index(cid) if cid in opts.values() else 0)]
        old=dataframe('SELECT product_name AS 제품명, quantity AS 수량, unit AS 단위 FROM order_items WHERE case_id=?',(cid,))
        if old.empty: old=pd.DataFrame([{'제품명':'','수량':0,'단위':'EA'}])
        edited=st.data_editor(old,num_rows='dynamic',use_container_width=True,key=f'orders_{cid}')
        if st.button('주문 목록 저장'):
            replace_order_items(cid,edited); db.add_history(cid,'주문 목록 저장',f'{len(edited)}행'); st.success('저장했습니다.'); rerun()

elif menu=='실출고 입력':
    st.subheader('실제 출고 제품 입력')
    countries=[r['country'] for r in db.rows("SELECT DISTINCT country FROM export_cases WHERE status='진행중' AND stage NOT IN ('완료','취소') ORDER BY country")]
    if not countries: st.info('진행 중 수출 건이 없습니다.'); st.stop()
    country=st.selectbox('국가',countries); cid=choose_active_case('ship_case',country)
    if not cid: st.stop()
    st.markdown('#### 주문 목록')
    st.dataframe(dataframe('SELECT product_name AS 제품명, quantity AS 수량, unit AS 단위 FROM order_items WHERE case_id=?',(cid,)),hide_index=True,use_container_width=True)
    st.markdown('#### 실제 출고 목록')
    st.caption('WMS에서 사업장, 로케이션, 제품명, LOT, 유통기한, 요청수량 6개 열을 복사해 첫 셀에 붙여넣으세요. 행 추가도 가능합니다.')
    old=dataframe('''SELECT business_unit AS 사업장, location AS 로케이션, product_name AS 제품명, lot_no AS LOT, expiry_date AS 유통기한, requested_qty AS 요청수량 FROM shipment_items WHERE case_id=? ORDER BY id''',(cid,))
    if old.empty: old=pd.DataFrame([{'사업장':'','로케이션':'','제품명':'','LOT':'','유통기한':'','요청수량':0}])
    edited=st.data_editor(old,num_rows='dynamic',use_container_width=True,key=f'ship_{cid}')
    if st.button('실출고 목록 저장'):
        save_shipment_editor(cid,edited); db.execute("UPDATE export_cases SET stage='실출고 입력',updated_at=? WHERE id=?",(db.now_text(),cid)); db.add_history(cid,'실출고 목록 저장',f'{len(edited)}행'); st.success('저장했습니다.'); rerun()

elif menu=='박스 패킹':
    st.subheader('박스 패킹')
    cid=choose_active_case('pack_case')
    if not cid: st.info('진행 중 수출 건이 없습니다.'); st.stop()
    items=db.rows('SELECT * FROM shipment_items WHERE case_id=? ORDER BY id',(cid,))
    if not items: st.warning('먼저 실출고 목록을 입력하세요.'); st.stop()
    selected=[]
    for item in items:
        c1,c2,c3=st.columns([6,2,2])
        label=f"{item['product_name']} · {item['lot_no']} · {item['requested_qty']:g}"
        if c1.checkbox(label,key=f"sel_{item['id']}"): selected.append(item['id'])
        c2.write(item['location'])
        c3.write(f"BOX {item['box_no']}" if item['box_no'] else '미패킹')
    next_box=db.row('SELECT COALESCE(MAX(box_no),0)+1 AS n FROM boxes WHERE case_id=?',(cid,))['n']
    box_no=st.number_input('배정할 박스번호',min_value=1,value=int(next_box),step=1)
    if st.button('선택 제품 패킹'):
        if not selected: st.error('제품을 선택하세요.')
        else:
            for iid in selected: db.execute('UPDATE shipment_items SET box_no=?,updated_at=? WHERE id=?',(box_no,db.now_text(),iid))
            db.execute('INSERT OR IGNORE INTO boxes(case_id,box_no,updated_at) VALUES (?,?,?)',(cid,box_no,db.now_text())); db.add_history(cid,'박스 패킹',f'{len(selected)}개 행 → BOX {box_no}'); rerun()
    st.markdown('#### 박스 정보')
    boxes=db.rows('SELECT * FROM boxes WHERE case_id=? ORDER BY box_no',(cid,))
    for b in boxes:
        with st.form(f"box_{b['id']}"):
            st.write(f"**BOX {b['box_no']}**")
            c1,c2,c3,c4=st.columns(4)
            l=c1.number_input('가로(cm)',0.0,value=float(b['length_cm']),key=f"l{b['id']}")
            w=c2.number_input('세로(cm)',0.0,value=float(b['width_cm']),key=f"w{b['id']}")
            h=c3.number_input('높이(cm)',0.0,value=float(b['height_cm']),key=f"h{b['id']}")
            kg=c4.number_input('무게(kg)',0.0,value=float(b['weight_kg']),key=f"kg{b['id']}")
            saved=st.form_submit_button('박스 정보 저장')
        if saved:
            db.execute('UPDATE boxes SET length_cm=?,width_cm=?,height_cm=?,weight_kg=?,updated_at=? WHERE id=?',(l,w,h,kg,db.now_text(),b['id']))
            db.add_history(cid,'박스 정보 수정',f"BOX {b['box_no']}")
            message=st.empty(); message.success('저장되었습니다.'); time.sleep(3); message.empty()

elif menu=='패킹 결과·배송·엑셀':
    st.subheader('패킹 결과 및 국내배송')
    cid=choose_active_case('result_case')
    if not cid: st.stop()
    case=db.row('SELECT * FROM export_cases WHERE id=?',(cid,))
    st.info(f"국가: {case['country']}  |  바이어: {case['buyer'] or '-'}  |  운송방식: {case['transport_mode']}")
    preview=dataframe('''SELECT s.box_no AS 박스번호,s.business_unit AS 사업장,s.location AS 로케이션,s.product_name AS 제품명,s.lot_no AS LOT,s.expiry_date AS 유통기한,s.requested_qty AS 수량,b.weight_kg AS 무게,
        printf('%g x %g x %g',b.length_cm,b.width_cm,b.height_cm) AS 박스사이즈
        FROM shipment_items s LEFT JOIN boxes b ON b.case_id=s.case_id AND b.box_no=s.box_no
        WHERE s.case_id=? AND s.box_no IS NOT NULL ORDER BY s.box_no,s.id''',(cid,))
    if not preview.empty:
        preview['무게']=preview['무게'].apply(lambda value: f'{float(value):g} kg' if pd.notna(value) else '')
        preview['박스사이즈']=preview['박스사이즈'].apply(lambda value: f'{value} cm' if value else '')
    st.dataframe(preview,hide_index=True,use_container_width=True)
    with st.form('delivery'):
        method=st.radio('국내배송',['로젠택배','퀵배송'],index=0 if case['domestic_method']!='퀵배송' else 1,horizontal=True)
        tracking=''; driver=''; phone=''
        if method=='로젠택배':
            tracking=st.text_input('송장번호',value=case['tracking_no'])
        else:
            c1,c2=st.columns(2)
            driver=c1.text_input('배송기사 이름',value=case['driver_name'])
            phone=c2.text_input('연락처',value=case['driver_phone'])
        if st.form_submit_button('배송정보 저장'):
            db.execute("UPDATE export_cases SET domestic_method=?,tracking_no=?,driver_name=?,driver_phone=?,stage='국내배송',status='완료',updated_at=? WHERE id=?",(method,tracking,driver,phone,db.now_text(),cid))
            db.add_history(cid,'국내배송 완료',method)
            st.success('국내배송 정보가 저장되어 수출 건이 완료 처리되었습니다.')
            time.sleep(1)
            rerun()
    st.download_button('전체 화면 엑셀로 내보내기',build_packing_export(cid),file_name=f"{case['export_no']}_packing.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

elif menu=='출고 사진':
    st.subheader('출고 증빙 사진')
    cid=choose_active_case('photo_case')
    if not cid: st.stop()
    files=st.file_uploader('사진 업로드',type=['jpg','jpeg','png','heic','webp'],accept_multiple_files=True)
    if st.button('사진 저장') and files:
        folder=db.UPLOAD_DIR/str(cid)/'photos'; folder.mkdir(parents=True,exist_ok=True)
        for f in files:
            path=folder/f.name; path.write_bytes(f.getbuffer()); db.execute('INSERT INTO attachments(case_id,file_name,stored_path,category,uploaded_at) VALUES (?,?,?,?,?)',(cid,f.name,str(path),'출고사진',db.now_text()))
        db.add_history(cid,'출고 사진 업로드',f'{len(files)}장'); rerun()
    photos=db.rows("SELECT * FROM attachments WHERE case_id=? AND category='출고사진' ORDER BY uploaded_at DESC",(cid,))
    if photos:
        cols=st.columns(4)
        for i,p in enumerate(photos):
            path=Path(p['stored_path'])
            if path.exists(): cols[i%4].image(str(path),caption=p['file_name'],use_container_width=True)
