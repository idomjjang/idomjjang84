import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="AI 매집주 분석기", layout="wide")

# 1. 데이터 로드 (가나다순 정렬)
@st.cache_data(ttl=86400)
def get_all_market_list():
    kospi = fdr.StockListing('KOSPI')[['Code', 'Name']]
    kosdaq = fdr.StockListing('KOSDAQ')[['Code', 'Name']]
    return pd.concat([kospi, kosdaq]).sort_values(by='Name')

all_stocks = get_all_market_list()

# 2. 분석 핵심 로직
def get_strategy_score(df, strategy):
    vol_ratio = df['Volume'].iloc[-5:].mean() / df['Volume'].iloc[-20:].mean()
    price_low = df['Close'].iloc[0] / df['Close'].iloc[-1]
    tech_signal = df['Close'].iloc[-1] / df['Close'].rolling(20).mean().iloc[-1]
    if strategy == "수급 강세형": return vol_ratio
    elif strategy == "저평가 가치형": return price_low
    else: return tech_signal

def get_ai_recommendations(df, strategy):
    results = []
    for _, row in df.head(50).iterrows():
        try:
            df_chart = fdr.DataReader(row['Code'], start=(datetime.now() - timedelta(days=60)))
            if len(df_chart) < 20: continue
            score = get_strategy_score(df_chart, strategy)
            results.append({'Code': row['Code'], 'Name': row['Name'], 'Score': score, 'Reason': f"{strategy} 기반 분석"})
        except: continue
    return pd.DataFrame(results).sort_values(by='Score', ascending=False).head(10).reset_index(drop=True)

# 3. UI 구성 (사이드바)
st.sidebar.header("⚙️ AI 분석 설정")
strategy = st.sidebar.radio("추천 로직", ["수급 강세형", "저평가 가치형", "기술적 반등형"])

if st.sidebar.button("🚀 전체 시장 분석 실행"):
    with st.spinner('시장 분석 중...'):
        st.session_state.kospi_recs = get_ai_recommendations(fdr.StockListing('KOSPI'), strategy)
        st.session_state.kosdaq_recs = get_ai_recommendations(fdr.StockListing('KOSDAQ'), strategy)
    st.rerun()

# 📌 [대안 기능] 실시간 유튜브 내용 붙여넣기 박스
st.sidebar.markdown("---")
st.sidebar.header("📺 유튜브 당일 내용 입력")
youtube_input = st.sidebar.text_area(
    "새 채팅방에서 제미나이가 알려준 오늘 자 요약 내용을 그대로 복사(Ctrl+C)해서 여기에 붙여넣기(Ctrl+V) 하세요.",
    height=250,
    placeholder="여기에 붙여넣으면 오른쪽에 바로 나타납니다!"
)

# 🔍 상세 종목 차트 설정 구역
st.sidebar.markdown("---")
st.sidebar.header("🔍 상세 종목 차트")
selected_name = st.sidebar.selectbox("종목명 검색", all_stocks['Name'].tolist())
target_code = all_stocks[all_stocks['Name'] == selected_name]['Code'].values[0]

# [복구 확인] 차트 갱신 버튼 정상 유지
if st.sidebar.button("🔄 차트 갱신"): 
    st.rerun()

# 메인 레이아웃 분할 (좌측 2 : 우측 1)
main_col, side_col = st.columns([2, 1])

with main_col:
    def display_recommendations(recs, title):
        st.subheader(title)
        if recs is not None:
            cols = st.columns(5)
            for idx, row in recs.iterrows():
                with cols[idx % 5]:
                    st.markdown(f"**{row['Name']}**")
                    st.caption(f"Code: {row['Code']}")
                    st.warning(f"📌 {row['Reason']}")
        else: st.info("왼쪽 분석 버튼을 누르세요.")

    if 'kospi_recs' in st.session_state: display_recommendations(st.session_state.kospi_recs, "🏛️ 코스피 선정 10선")
    if 'kosdaq_recs' in st.session_state: display_recommendations(st.session_state.kosdaq_recs, "🧬 코스닥 선정 10선")

    st.markdown("---")

    # 상세 차트 메인 화면 표시
    st.header(f"📊 {selected_name} ({target_code})")

    try:
        df = fdr.DataReader(target_code, start=(datetime.now() - timedelta(days=180)))
        fig = go.Figure(data=[go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            increasing_line_color='red', decreasing_line_color='blue'
        )])
        fig.update_layout(height=400, template="plotly_white", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{int(df['Close'].iloc[-1]):,}원")
        diff = df['Close'].iloc[-1] - df['Open'].iloc[-1]
        rate = (diff / df['Open'].iloc[-1]) * 100
        c2.metric("시가 대비 등락", f"{int(diff):,}원", f"{rate:.2f}%")
        c3.metric("거래량", f"{int(df['Volume'].iloc[-1]):,}")
    except:
        st.error("차트 데이터를 불러올 수 없습니다.")

# 우측 영역: 사이드바 입력창과 실시간 연동되어 텍스트 출력
with side_col:
    st.subheader("🎯 김앤오 수익연구소 당일 매매")
    if youtube_input:
        st.info(youtube_input)
    else:
        st.write("👈 왼쪽 사이드바 입력창에 오늘 자 유튜브 요약 내용을 붙여넣으면 여기에 즉시 표시됩니다.")
