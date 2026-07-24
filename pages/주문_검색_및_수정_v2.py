from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

import db
from components.editors import historical_box_editor, historical_order_editor, order_editor
from config import TRANSPORT_MODES
from services import export_service, folder_service, history_service, order_service
from utils.dates import now_text, parse_date


def txt(v, default=''):
    if v is None or pd.isna(v):
        return default
    s = str(v).strip()
    return default if s.casefold() in {'nan', 'none', '<na>'} else s


def num(v, default=0.0):
    if v is None or pd.isna(v) or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def integer(v, default=0):
    return int(num(v, default))


def dval(v):
    parsed = parse_date(v)
    return parsed.date() if parsed else date.today()


def historical_items(case_id):
    rows = db.rows('''SELECT o.id _order_id,s.id _shipment_id,COALESCE(s.location,'') 출고처,
        o.product_name 제품명,COALESCE(s.lot_no,'') 제조번호,COALESCE(s.expiry_date,'') 유효기간,
        o.quantity 수량,o.unit 단위,o.purchase_price 매입가,COALESCE(s.box_no,1) "CTN 번호"
        FROM order_items o LEFT JOIN shipment_items s ON s.order_item_id=o.id AND s.case_id=o.case_id
        WHERE o.case_id=? ORDER BY o.id,s.id''', (case_id,))
    if rows:
        return pd.DataFrame([dict(r) for r in rows])
    return pd.DataFrame([{'_order_id':None,'_shipment_id':None,'출고처':'','제품명':'','제조번호':'',
        '유효기간':'','수량':0.0,'단위':'EA','매입가':0.0,'CTN 번호':1}])


def box_items(case_id):
    rows = db.rows('''SELECT box_no "CTN 번호",length_cm "가로 (cm)",width_cm "세로 (cm)",
        height_cm "높이 (cm)",weight_kg "GW (kg)" FROM boxes WHERE case_id=? ORDER BY box_no''', (case_id,))
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame([
        {'CTN 번호':1,'가로 (cm)':0.0,'세로 (cm)':0.0,'높이 (cm)':0.0,'GW (kg)':0.0}])


def save_historical(case_id, edited, boxes, basic, delivery):
    items=[]
    for _,r in edited.iterrows():
        name=txt(r.get('제품명'))
        if not name: continue
        items.append({'oid':integer(r.get('_order_id')),'sid':integer(r.get('_shipment_id')),
            'loc':txt(r.get('출고처')),'name':name,'lot':txt(r.get('제조번호')),
            'exp':txt(r.get('유효기간')),'qty':num(r.get('수량')),
            'unit':txt(r.get('단위'),'EA') or 'EA','price':num(r.get('매입가')),
            'box':integer(r.get('CTN 번호'))})
    if not items: raise ValueError('제품을 한 개 이상 입력하세요.')
    if any(x['box']<=0 for x in items): raise ValueError('모든 제품에 CTN 번호를 입력하세요.')
    clean_boxes=[]
    for _,r in boxes.iterrows():
        b=integer(r.get('CTN 번호'))
        if b>0: clean_boxes.append((b,num(r.get('가로 (cm)')),num(r.get('세로 (cm)')),num(r.get('높이 (cm)')),num(r.get('GW (kg)'))))
    if not clean_boxes: raise ValueError('CTN 정보를 한 개 이상 입력하세요.')
    if not {x['box'] for x in items}.issubset({x[0] for x in clean_boxes}):
        raise ValueError('제품에 연결한 모든 CTN 번호의 규격과 GW를 입력하세요.')
    now=now_text()
    with db.connect() as c:
        old_o={int(r['id']):r for r in c.execute('SELECT id,product_name,purchase_price FROM order_items WHERE case_id=?',(case_id,))}
        old_s={int(r['id']):r for r in c.execute('SELECT id FROM shipment_items WHERE case_id=?',(case_id,))}
        keep_o=set(); keep_s=set()
        for x in items:
            oid=x['oid']
            prev=old_o.get(oid)
            if prev:
                c.execute('UPDATE order_items SET product_name=?,quantity=?,unit=?,purchase_price=? WHERE id=? AND case_id=?',
                    (x['name'],x['qty'],x['unit'],x['price'],oid,case_id))
            else:
                oid=c.execute('INSERT INTO order_items(case_id,product_name,quantity,unit,purchase_price,created_at) VALUES(?,?,?,?,?,?)',
                    (case_id,x['name'],x['qty'],x['unit'],x['price'],now)).lastrowid
            keep_o.add(int(oid))
            if not prev or num(prev['purchase_price'])!=x['price'] or prev['product_name']!=x['name']:
                c.execute('''INSERT INTO purchase_price_history(case_id,order_item_id,product_name,normalized_name,
                    purchase_price,quantity,unit,created_at) VALUES(?,?,?,?,?,?,?,?)''',
                    (case_id,oid,x['name'],order_service.normalize_product_name(x['name']),x['price'],x['qty'],x['unit'],now))
            sid=x['sid']
            if sid in old_s:
                c.execute('''UPDATE shipment_items SET order_item_id=?,location=?,product_name=?,lot_no=?,expiry_date=?,
                    requested_qty=?,box_no=?,updated_at=? WHERE id=? AND case_id=?''',
                    (oid,x['loc'],x['name'],x['lot'],x['exp'],x['qty'],x['box'],now,sid,case_id))
            else:
                sid=c.execute('''INSERT INTO shipment_items(case_id,order_item_id,business_unit,location,product_name,
                    lot_no,expiry_date,requested_qty,box_no,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (case_id,oid,'',x['loc'],x['name'],x['lot'],x['exp'],x['qty'],x['box'],now,now)).lastrowid
            keep_s.add(int(sid))
        for sid in set(old_s)-keep_s: c.execute('DELETE FROM shipment_items WHERE id=?',(sid,))
        for oid in set(old_o)-keep_o: c.execute('DELETE FROM order_items WHERE id=?',(oid,))
        c.execute('DELETE FROM boxes WHERE case_id=?',(case_id,))
        c.executemany('INSERT INTO boxes(case_id,box_no,length_cm,width_cm,height_cm,weight_kg,updated_at) VALUES(?,?,?,?,?,?,?)',
            [(case_id,*b,now) for b in clean_boxes])
        c.execute('''UPDATE export_cases SET country=?,buyer=?,transport_mode=?,note=?,actual_ship_date=?,domestic_method=?,
            tracking_no=?,driver_name=?,driver_phone=?,consignee_name=?,consignee_address=?,stage='완료',status='완료',updated_at=? WHERE id=?''',
            (*basic,*delivery,now,case_id))


st.title('주문 검색 및 수정')

if message := st.session_state.pop('order_cancel_success_message', None):
    st.success(message)

cases=order_service.list_editable_cases()
if not cases:
    st.info('수정할 수출 건이 없습니다.'); st.stop()

cols=st.columns([1.5,1.5,3,4])
years=sorted({int(txt(c['actual_ship_date'])[:4]) for c in cases if txt(c['actual_ship_date'])[:4].isdigit()},reverse=True)
year=cols[0].selectbox('연도',['전체']+years)
month=cols[1].selectbox('월',['전체']+list(range(1,13)))
country_filter=cols[2].selectbox('국가',['전체']+sorted({txt(c['country']) for c in cases if txt(c['country'])}))
query=cols[3].text_input('제품명 검색').strip().casefold()
filtered=[]
for c in cases:
    d=txt(c['actual_ship_date']); cy=int(d[:4]) if d[:4].isdigit() else None; cm=int(d[5:7]) if len(d)>=7 and d[5:7].isdigit() else None
    if year!='전체' and cy!=year: continue
    if month!='전체' and cm!=month: continue
    if country_filter!='전체' and txt(c['country'])!=country_filter: continue
    if query and query not in txt(c['product_names']).casefold(): continue
    filtered.append(c)
if not filtered:
    st.warning('조건에 맞는 수출 건이 없습니다.'); st.stop()

df=pd.DataFrame([{'_id':int(c['id']),'출고일자':txt(c['actual_ship_date'])[:10],'수출번호':c['export_no'],
    '국가':c['country'],'바이어':c['buyer'] or '','운송방식':c['transport_mode'],'단계':c['stage'],'주문제품':txt(c['product_names'])} for c in filtered])
event=st.dataframe(df,hide_index=True,use_container_width=True,on_select='rerun',selection_mode='single-row',column_config={'_id':None},key='editable_case_table_v2')
if not event.selection.rows:
    st.info('수정할 수출 건의 행을 선택하세요.'); st.stop()
idx=int(event.selection.rows[0])
if idx<0 or idx>=len(df): st.stop()
case_id=int(df.iloc[idx]['_id']); case=next(c for c in filtered if int(c['id'])==case_id); detail=export_service.get_case(case_id)
is_his=txt(case['export_no']).upper().startswith('HIS')

st.divider()
st.markdown('#### 주문 취소')
cancel_cols = st.columns([3, 2, 5])
cancel_confirm = cancel_cols[0].checkbox(
    f"{case['export_no']} 주문 취소를 확인합니다.",
    key=f'cancel_confirm_{case_id}',
)
cancel_order = cancel_cols[1].button(
    '주문 취소',
    type='secondary',
    disabled=not cancel_confirm,
    use_container_width=True,
    key=f'cancel_order_{case_id}',
)
cancel_cols[2].caption('취소하면 해당 건은 주문 검색 목록에서 제외되며, 기존 데이터는 삭제되지 않고 취소 상태로 보관됩니다.')

if cancel_order:
    export_service.cancel_case(case_id)
    history_service.add_history(case_id, '주문 취소', case['export_no'])
    try:
        folder_service.sync_case_folder(case_id)
    except OSError:
        pass
    for key in list(st.session_state):
        if key in {'editable_case_table_v2', 'order_case_id'} or key.endswith(f'_{case_id}'):
            st.session_state.pop(key, None)
    st.session_state['order_cancel_success_message'] = f"{case['export_no']} 주문을 취소했습니다."
    st.rerun()

st.divider()

if is_his:
    st.markdown('### 과거 수출 건 수정')
    ship_date=st.date_input('과거 수출일',value=dval(detail['actual_ship_date']),key=f'his_date_{case_id}')
    a=st.columns(3)
    a[0].text_input('수출번호',value=case['export_no'],disabled=True,key=f'his_no_{case_id}')
    country=a[1].text_input('국가 *',value=case['country'],key=f'his_country_{case_id}')
    buyer=a[2].text_input('바이어 (선택)',value=case['buyer'] or '',key=f'his_buyer_{case_id}')
    b=st.columns(3); ti=TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in TRANSPORT_MODES else 0
    transport=b[0].selectbox('운송방식',TRANSPORT_MODES,index=ti,key=f'his_transport_{case_id}')
    note=b[1].text_input('비고',value=case['note'] or '',key=f'his_note_{case_id}')
    st.markdown('#### 실출고 제품 및 CTN 연결')
    edited=historical_order_editor(historical_items(case_id),key=f'his_items_v2_{case_id}')
    st.markdown('#### CTN 정보'); boxes=historical_box_editor(box_items(case_id),key=f'his_boxes_v2_{case_id}')
    st.markdown('#### 국내배송 정보')
    r=st.columns([1,2]); consignee=r[0].text_input('수하인명',value=detail['consignee_name'] or '',key=f'his_consignee_{case_id}'); address=r[1].text_input('수하인주소',value=detail['consignee_address'] or '',key=f'his_address_{case_id}')
    method=st.radio('배송 방식',['로젠택배','퀵배송'],index=1 if detail['domestic_method']=='퀵배송' else 0,horizontal=True,key=f'his_method_{case_id}')
    if method=='로젠택배':
        tracking=st.text_input('송장번호',value=detail['tracking_no'] or '',key=f'his_tracking_{case_id}'); driver=phone=''
    else:
        q=st.columns(2); driver=q[0].text_input('배송기사 이름',value=detail['driver_name'] or '',key=f'his_driver_{case_id}'); phone=q[1].text_input('배송기사 연락처',value=detail['driver_phone'] or '',key=f'his_phone_{case_id}'); tracking=''
    if st.button('과거 수출 건 저장',type='primary',key=f'save_his_{case_id}'):
        if not country.strip(): st.error('국가는 필수입니다.')
        else:
            try: save_historical(case_id,edited,boxes,(country.strip(),buyer.strip(),transport,note.strip(),str(ship_date)),(method,tracking.strip(),driver.strip(),phone.strip(),consignee.strip(),address.strip()))
            except ValueError as e: st.error(str(e))
            else:
                folder_service.sync_case_folder(case_id); history_service.add_history(case_id,'과거 수출 건 전체 수정',f'{len(edited)}행'); st.success('저장했습니다.'); st.rerun()
else:
    st.markdown('### 현재 진행 건 수정')
    a=st.columns(4); country=a[0].text_input('국가 *',value=case['country']); buyer=a[1].text_input('바이어',value=case['buyer'] or ''); ti=TRANSPORT_MODES.index(case['transport_mode']) if case['transport_mode'] in TRANSPORT_MODES else 0; transport=a[2].selectbox('운송방식',TRANSPORT_MODES,index=ti); note=a[3].text_input('비고',value=case['note'] or '')
    if st.button('기본 정보 저장'):
        export_service.update_basic(case_id,country,buyer,transport,note); folder_service.sync_case_folder(case_id); st.rerun()
    existing=order_service.get_order_items_dataframe(case_id)
    if existing.empty: existing=pd.DataFrame([{'_id':None,'제품명':'','수량':0.0,'단위':'EA','매입가':0.0}])
    edited=order_editor(existing,key=f'orders_{case_id}')
    if st.button('주문 목록 저장',type='primary'):
        order_service.save_order_items(case_id,edited); folder_service.sync_case_folder(case_id); st.rerun()
