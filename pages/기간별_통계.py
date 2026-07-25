from __future__ import annotations

import calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services import statistics_service
from utils.formatters import fmt_number


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_end(value: date) -> date:
    return value.replace(day=calendar.monthrange(value.year, value.month)[1])


def previous_month_range(today: date) -> tuple[date, date]:
    end = month_start(today) - timedelta(days=1)
    return month_start(end), end


def preset_range(preset: str, today: date) -> tuple[date, date]:
    if preset == '지난 달':
        return previous_month_range(today)
    if preset == '최근 3개월':
        current_start = month_start(today)
        previous_end = current_start - timedelta(days=1)
        second_previous_end = month_start(previous_end) - timedelta(days=1)
        return month_start(second_previous_end), today
    if preset == '올해':
        return date(today.year, 1, 1), today
    return month_start(today), today


def quantity_text(frame: pd.DataFrame) -> str:
    if frame.empty:
        return '0'
    totals = frame.groupby('단위', as_index=False)['출고수량'].sum()
    return ' · '.join(
        f"{fmt_number(row['출고수량'])} {row['단위']}"
        for _, row in totals.iterrows()
    )


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode('utf-8-sig')


st.title('기간별 통계')
st.caption('실제 출고일과 실제 출고수량을 기준으로 국가별·제품별 수출 실적을 확인합니다.')

today = date.today()
filter_cols = st.columns([1.15, 1, 1, 1.5])
preset = filter_cols[0].selectbox(
    '조회 기간',
    ['이번 달', '지난 달', '최근 3개월', '올해', '직접 선택'],
    index=0,
)

if preset == '직접 선택':
    default_start, default_end = previous_month_range(today)
    start_date = filter_cols[1].date_input('시작일', value=default_start)
    end_date = filter_cols[2].date_input('종료일', value=default_end)
else:
    start_date, end_date = preset_range(preset, today)
    filter_cols[1].text_input('시작일', value=start_date.isoformat(), disabled=True)
    filter_cols[2].text_input('종료일', value=end_date.isoformat(), disabled=True)

if start_date > end_date:
    st.error('시작일은 종료일보다 늦을 수 없습니다.')
    st.stop()

all_rows = statistics_service.shipment_rows(start_date, end_date)
country_options = sorted(all_rows['국가'].dropna().unique().tolist()) if not all_rows.empty else []
selected_countries = filter_cols[3].multiselect(
    '국가',
    country_options,
    placeholder='전체 국가',
)

product_query = st.text_input(
    '제품명 검색',
    placeholder='예: 리드카인, 앰플, xx 제품명',
    help='제품명의 일부만 입력해도 검색됩니다.',
)

filtered = statistics_service.filter_rows(
    all_rows,
    countries=selected_countries,
    product_query=product_query,
)

if all_rows.empty:
    st.info(f'{start_date.isoformat()}부터 {end_date.isoformat()}까지 실제 출고일이 등록된 데이터가 없습니다.')
    st.stop()

if filtered.empty:
    st.warning('선택한 국가와 제품명 조건에 맞는 출고 데이터가 없습니다.')
    st.stop()

case_count = int(filtered['case_id'].nunique())
country_count = int(filtered['국가'].nunique())
product_count = int(filtered['제품명'].nunique())

metrics = st.columns(4)
metrics[0].metric('수출 건수', f'{case_count:,}건')
metrics[1].metric('국가 수', f'{country_count:,}개')
metrics[2].metric('제품 수', f'{product_count:,}개')
metrics[3].metric('실제 출고수량', quantity_text(filtered))

answer_parts: list[str] = []
if selected_countries:
    answer_parts.append(', '.join(selected_countries))
else:
    answer_parts.append('전체 국가')
if product_query.strip():
    answer_parts.append(f"제품명 ‘{product_query.strip()}’")
else:
    answer_parts.append('전체 제품')

st.success(
    f"{start_date.isoformat()} ~ {end_date.isoformat()} · "
    f"{' · '.join(answer_parts)}의 실제 출고량은 {quantity_text(filtered)}이며, "
    f"총 {case_count:,}건의 수출에 포함되었습니다."
)

summary_tab, country_tab, product_tab, detail_tab = st.tabs(
    ['한눈에 보기', '국가별 제품', '제품별 국가', '상세 출고내역']
)

with summary_tab:
    left, right = st.columns(2)

    country_totals = (
        filtered.groupby(['국가', '단위'], as_index=False)['출고수량']
        .sum()
        .sort_values('출고수량', ascending=False)
    )
    product_totals = (
        filtered.groupby(['제품명', '단위'], as_index=False)['출고수량']
        .sum()
        .sort_values('출고수량', ascending=False)
    )

    with left:
        st.markdown('#### 국가별 출고량')
        if country_totals['단위'].nunique() == 1:
            chart = country_totals.set_index('국가')[['출고수량']].head(15)
            st.bar_chart(chart, horizontal=True)
        st.dataframe(
            country_totals,
            hide_index=True,
            use_container_width=True,
            column_config={
                '출고수량': st.column_config.NumberColumn('출고수량', format='%.2f'),
            },
        )

    with right:
        st.markdown('#### 많이 출고된 제품')
        if product_totals['단위'].nunique() == 1:
            chart = product_totals.head(15).set_index('제품명')[['출고수량']]
            st.bar_chart(chart, horizontal=True)
        st.dataframe(
            product_totals.head(30),
            hide_index=True,
            use_container_width=True,
            column_config={
                '출고수량': st.column_config.NumberColumn('출고수량', format='%.2f'),
            },
        )

    monthly = statistics_service.monthly_summary(filtered)
    if len(monthly['월'].unique()) > 1:
        st.markdown('#### 월별 출고 추이')
        if monthly['단위'].nunique() == 1:
            st.line_chart(monthly.set_index('월')[['출고수량']])
        st.dataframe(monthly, hide_index=True, use_container_width=True)

with country_tab:
    country_summary = statistics_service.country_product_summary(filtered)
    st.caption('각 국가에서 어떤 제품이 많이 출고되었는지 출고수량 순으로 보여줍니다.')
    st.dataframe(
        country_summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            '출고수량': st.column_config.NumberColumn('출고수량', format='%.2f'),
            '출고건수': st.column_config.NumberColumn('출고건수', format='%d건'),
        },
    )
    st.download_button(
        '국가별 제품 통계 CSV 다운로드',
        data=csv_bytes(country_summary),
        file_name=f'국가별_제품_통계_{start_date}_{end_date}.csv',
        mime='text/csv',
        use_container_width=True,
    )

with product_tab:
    product_summary = statistics_service.product_country_summary(filtered)
    st.caption('각 제품이 어느 국가로 얼마나 출고되었는지 출고수량 순으로 보여줍니다.')
    st.dataframe(
        product_summary,
        hide_index=True,
        use_container_width=True,
        column_config={
            '출고수량': st.column_config.NumberColumn('출고수량', format='%.2f'),
            '출고건수': st.column_config.NumberColumn('출고건수', format='%d건'),
        },
    )
    st.download_button(
        '제품별 국가 통계 CSV 다운로드',
        data=csv_bytes(product_summary),
        file_name=f'제품별_국가_통계_{start_date}_{end_date}.csv',
        mime='text/csv',
        use_container_width=True,
    )

with detail_tab:
    detail = filtered.drop(columns=['case_id']).copy()
    st.caption('집계에 포함된 실제 출고행을 확인합니다.')
    st.dataframe(
        detail,
        hide_index=True,
        use_container_width=True,
        column_config={
            '출고수량': st.column_config.NumberColumn('출고수량', format='%.2f'),
        },
    )
    st.download_button(
        '상세 출고내역 CSV 다운로드',
        data=csv_bytes(detail),
        file_name=f'상세_출고내역_{start_date}_{end_date}.csv',
        mime='text/csv',
        use_container_width=True,
    )
