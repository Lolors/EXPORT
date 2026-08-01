from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from services.dashboard_view_service import plotly_selected_case_id, timeline_bounds


def render_order_timeline(rows: list[dict]) -> int | None:
    """Render a clickable Gantt chart and return the selected export case id."""
    if not rows:
        return None

    today = date.today()
    axis_start, axis_end = timeline_bounds(rows, today=today)
    figure = go.Figure()

    # One trace per row keeps every order independently clickable, including
    # orders with identical party, products, dates, and stage.
    for index, row in enumerate(rows):
        start_date = date.fromisoformat(str(row['start_date'])[:10])
        end_date = date.fromisoformat(str(row.get('end_date') or today)[:10])
        end_date = max(start_date, end_date)
        duration_ms = max(1, (end_date - start_date).days + 1) * 86_400_000
        case_id = int(row.get('case_id') or 0)
        export_no = str(row.get('export_no') or '수출번호 미입력')
        stage = str(row.get('stage') or '단계 미입력')
        label = str(row.get('bar_label') or '')
        products = str(row.get('products') or '-')
        product_summary = str(row.get('product_summary') or '주문목록 없음')
        hover = (
            f'<b>{export_no}</b><br>'
            f'{start_date.isoformat()} ~ {end_date.isoformat()}<br>'
            f'{stage}<br><br><b>주문목록</b><br>{products.replace(chr(10), "<br>")}'
            '<extra></extra>'
        )
        figure.add_trace(go.Bar(
            x=[duration_ms],
            y=[str(index)],
            base=[start_date.isoformat()],
            orientation='h',
            width=0.62,
            marker={
                'color': str(row.get('bar_background') or '#94a3b8'),
                'line': {'color': str(row.get('bar_accent') or '#64748b'), 'width': 2},
            },
            text=[f'<b>{label}</b><br>{product_summary}'],
            textposition='outside',
            textfont={'color': str(row.get('bar_text') or '#1f2937'), 'size': 11},
            cliponaxis=False,
            customdata=[[case_id]],
            hovertemplate=hover,
            showlegend=False,
            name=export_no,
        ))

    figure.add_vline(x=today.isoformat(), line_width=2, line_color='#3b82f6')
    figure.update_layout(
        barmode='overlay',
        height=min(820, max(350, 145 + len(rows) * 62)),
        margin={'l': 12, 'r': 240, 't': 42, 'b': 35},
        paper_bgcolor='white',
        plot_bgcolor='white',
        hoverlabel={'align': 'left'},
        dragmode='select',
        clickmode='event+select',
        xaxis={
            'type': 'date',
            'range': [axis_start.isoformat(), axis_end.isoformat()],
            'side': 'top',
            'dtick': 86_400_000,
            'tickformat': '%m/%d',
            'showgrid': True,
            'gridcolor': '#edf0f3',
            'fixedrange': False,
            'rangeslider': {'visible': False},
            'rangeselector': {
                'buttons': [
                    {'count': 7, 'label': '주', 'step': 'day', 'stepmode': 'backward'},
                    {'count': 1, 'label': '개월', 'step': 'month', 'stepmode': 'backward'},
                    {'count': 3, 'label': '분기', 'step': 'month', 'stepmode': 'backward'},
                    {'label': '전체', 'step': 'all'},
                ]
            },
        },
        yaxis={
            'showticklabels': False,
            'showgrid': True,
            'gridcolor': '#edf0f3',
            'autorange': 'reversed',
            'fixedrange': True,
        },
        selections=[],
    )
    event = st.plotly_chart(
        figure,
        use_container_width=True,
        key='dashboard_order_timeline',
        on_select='rerun',
        selection_mode='points',
        config={'displayModeBar': False, 'scrollZoom': True},
    )
    return plotly_selected_case_id(event)
