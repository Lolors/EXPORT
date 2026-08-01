from __future__ import annotations

from calendar import month_abbr
from datetime import date, timedelta
from html import escape
import json

import streamlit.components.v1 as components

from services.dashboard_view_service import timeline_bounds


DAY_WIDTH = 44
LABEL_WIDTH = 300


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or '').strip()[:10])
    except ValueError:
        return None


def _month_segments(start: date, end: date) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = []
    cursor = start
    while cursor <= end:
        month_start = cursor
        while cursor <= end and cursor.month == month_start.month:
            cursor += timedelta(days=1)
        label = f'{month_abbr[month_start.month]} {month_start.year}'
        segments.append((label, (cursor - month_start).days))
    return segments


def render_order_timeline(rows: list[dict]) -> None:
    if not rows:
        return

    today = date.today()
    start, end = timeline_bounds(rows, today=today)
    dates: list[date] = []
    cursor = start
    while cursor <= end:
        dates.append(cursor)
        cursor += timedelta(days=1)

    day_headers = ''.join(
        f'<div class="day {"weekend" if value.weekday() >= 5 else ""} '
        f'{"today-day" if value == today else ""}" data-date="{value.isoformat()}">'
        f'<span>{value.day}</span></div>'
        for value in dates
    )
    month_headers = ''.join(
        f'<div class="month" style="width:{count * DAY_WIDTH}px">{escape(label)}</div>'
        for label, count in _month_segments(start, end)
    )
    grid_columns = ''.join(
        f'<div class="grid-day {"weekend" if value.weekday() >= 5 else ""} '
        f'{"today-grid" if value == today else ""}"></div>'
        for value in dates
    )

    body_rows: list[str] = []
    for row in rows:
        start_date = _parse_date(row.get('start_date')) or start
        requested_end = _parse_date(row.get('end_date'))
        end_date = max(start_date, requested_end or today)
        offset = (start_date - start).days * DAY_WIDTH + 4
        width = max(DAY_WIDTH - 8, ((end_date - start_date).days + 1) * DAY_WIDTH - 8)
        export_no = escape(str(row.get('export_no') or '수출번호 미입력'))
        party = escape(str(row.get('party') or '국가·바이어 미입력'))
        stage = escape(str(row.get('stage') or '단계 미입력'))
        bar_label = escape(str(row.get('bar_label') or party))
        product_summary = escape(str(row.get('product_summary') or '주문목록 없음'))
        products = escape(str(row.get('products') or '-'), quote=True).replace('\n', '&#10;')
        period = f'{start_date.isoformat()} ~ {end_date.isoformat()}'
        tooltip = escape(f'{export_no}\n{period}\n{stage}\n주문목록:\n', quote=True) + products
        body_rows.append(
            '<div class="order-row">'
            f'<div class="order-label"><strong>{export_no}</strong>'
            f'<span>{party}</span><span class="label-products">{product_summary}</span></div>'
            f'<div class="row-track">{grid_columns}'
            f'<div class="order-bar" data-start="{start_date.isoformat()}" '
            f'data-end="{end_date.isoformat()}" style="left:{offset}px;width:{width}px" '
            f'title="{tooltip}"><span class="bar-party">{bar_label}</span>'
            f'<span class="bar-products">{product_summary}</span></div></div></div>'
        )

    payload = json.dumps({
        'todayOffset': max(0, (today - start).days * DAY_WIDTH),
        'dayWidth': DAY_WIDTH,
    })
    height = min(820, max(350, 150 + len(rows) * 76))
    document = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #2d333b; font-family: Arial, "Noto Sans KR", sans-serif; }}
.toolbar {{ display:flex; justify-content:flex-end; gap:5px; margin:0 2px 9px; }}
.toolbar button {{ border:1px solid #d7dce3; border-radius:7px; background:#fff; color:#505864; padding:6px 11px; cursor:pointer; }}
.toolbar button:hover,.toolbar button.active {{ border-color:#3b82f6; background:#eef5ff; color:#1769d2; }}
.shell {{ border:1px solid #d9dde3; border-radius:10px; overflow:hidden; background:#fff; }}
.timeline {{ overflow:auto; max-height:{height - 50}px; position:relative; }}
.canvas {{ min-width:{LABEL_WIDTH + len(dates) * DAY_WIDTH}px; }}
.month-row,.day-row,.order-row {{ display:flex; min-width:max-content; }}
.corner {{ position:sticky; left:0; z-index:8; width:{LABEL_WIDTH}px; flex:0 0 {LABEL_WIDTH}px; padding:9px 14px; border-right:1px solid #d5d9df; background:#f8f9fb; font-weight:700; }}
.month-row {{ position:sticky; top:0; z-index:7; height:34px; border-bottom:1px solid #d5d9df; }}
.month {{ flex:0 0 auto; padding:8px 12px; border-right:1px solid #d5d9df; background:#f1f2f4; font-weight:700; color:#5d6570; }}
.day-row {{ position:sticky; top:34px; z-index:7; height:35px; border-bottom:1px solid #cfd4da; background:#fff; }}
.day {{ width:{DAY_WIDTH}px; flex:0 0 {DAY_WIDTH}px; text-align:center; padding-top:8px; border-right:1px solid #edf0f3; color:#656d78; }}
.day.weekend,.grid-day.weekend {{ background:#f7f8fa; }}
.day.today-day span {{ padding:3px 7px; border-radius:8px; background:#3b82f6; color:#fff; font-weight:800; }}
.order-row {{ height:76px; border-bottom:1px solid #edf0f3; }}
.order-row:last-child {{ border-bottom:0; }}
.order-label {{ position:sticky; left:0; z-index:5; width:{LABEL_WIDTH}px; flex:0 0 {LABEL_WIDTH}px; display:flex; flex-direction:column; justify-content:center; gap:3px; padding:8px 14px; border-right:1px solid #d5d9df; background:#fff; }}
.order-label strong {{ color:#293b55; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.order-label span {{ color:#737b87; font-size:11px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.order-label .label-products {{ color:#3f536e; font-size:11px; font-weight:700; }}
.row-track {{ position:relative; width:{len(dates) * DAY_WIDTH}px; flex:0 0 {len(dates) * DAY_WIDTH}px; }}
.grid-day {{ display:inline-block; width:{DAY_WIDTH}px; height:100%; border-right:1px solid #edf0f3; }}
.grid-day.today-grid {{ border-left:2px solid #3b82f6; }}
.order-bar {{ position:absolute; top:14px; height:48px; padding:6px 10px 5px 12px; border-radius:7px; background:#92c943; color:#29420a; font-size:11px; font-weight:800; box-shadow:0 2px 5px rgba(71,111,17,.16); overflow:hidden; cursor:help; display:flex; flex-direction:column; justify-content:center; gap:2px; }}
.order-bar::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:#6da727; }}
.order-bar span {{ display:block; margin-left:3px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }}
.order-bar .bar-products {{ color:#35570d; font-size:10px; font-weight:700; opacity:.9; }}
@media(max-width:700px) {{ .corner,.order-label {{ width:190px; flex-basis:190px; }} .canvas {{ min-width:{190 + len(dates) * DAY_WIDTH}px; }} }}
</style></head><body>
<div class="toolbar"><button data-view="today">오늘</button><button data-view="week">주</button><button data-view="month" class="active">개월</button><button data-view="quarter">분기</button></div>
<div class="shell"><div class="timeline" id="timeline"><div class="canvas">
<div class="month-row"><div class="corner">수출 주문</div>{month_headers}</div>
<div class="day-row"><div class="corner"></div>{day_headers}</div>
{''.join(body_rows)}
</div></div></div>
<script>
const config={payload}; const timeline=document.getElementById('timeline');
const labelWidth={LABEL_WIDTH};
function centerToday() {{ timeline.scrollLeft=Math.max(0,labelWidth+config.todayOffset-timeline.clientWidth/2); }}
function setZoom(days) {{
  const available=Math.max(360,timeline.clientWidth-labelWidth); const width=Math.max(24,Math.min(88,available/days));
  document.documentElement.style.setProperty('--unused',width+'px');
  document.querySelectorAll('.day,.grid-day').forEach(el=>{{el.style.width=width+'px';el.style.flexBasis=width+'px';}});
  document.querySelectorAll('.month').forEach(el=>{{const count=Math.round(parseFloat(el.style.width)/config.dayWidth);el.style.width=(count*width)+'px';}});
  document.querySelectorAll('.row-track').forEach(el=>{{el.style.width=({len(dates)}*width)+'px';el.style.flexBasis=({len(dates)}*width)+'px';}});
  document.querySelectorAll('.order-bar').forEach(el=>{{
    const axisStart=new Date('{start.isoformat()}');
    const barStart=new Date(el.dataset.start); const barEnd=new Date(el.dataset.end);
    const offset=Math.round((barStart-axisStart)/86400000);
    const duration=Math.max(1,Math.round((barEnd-barStart)/86400000)+1);
    el.style.left=(offset*width+4)+'px'; el.style.width=Math.max(width-8,duration*width-8)+'px';
  }});
  config.dayWidth=width; config.todayOffset={(today-start).days}*width; centerToday();
}}
document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>{{
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.remove('active'));btn.classList.add('active');
  const views={{today:3,week:7,month:31,quarter:92}};setZoom(views[btn.dataset.view]);
}}));
requestAnimationFrame(()=>{{setZoom(31);}});
</script></body></html>'''
    components.html(document, height=height, scrolling=False)
