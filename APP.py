import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# 스트림릿 클라우드 서버 환경에서 패키지 강제 로드 안전장치
try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf

st.set_page_config(page_title="AI 매집주 분석기", layout="wide")

# 1. 데이터 로드 (가나다순 정렬 및 캐싱)
@st.cache_data(ttl=86400)
def get_all_market_list():
    kospi = fdr.StockListing('KOSPI')[['Code', 'Name']].copy()
    kosdaq = fdr.StockListing('KOSDAQ')[['Code', 'Name']].copy()
    return pd.concat([kospi, kosdaq]).sort_values(by='Name')

all_stocks = get_all_market_list()

# 2. 점수 계산 및 상세한 매집 이유 생성
def get_total_strategy_score(df):
    if len(df) < 15: return 0, "데이터 부족"
    
    vol_ratio = df['Volume'].iloc[-3:].mean() / df['Volume'].iloc[-15:].mean()
    highest = df['High'].iloc[-15:].max()
    value_ratio = highest / df['Close'].iloc[-1] if df['Close'].iloc[-1] > 0 else 0
    ma15 = df['Close'].rolling(15).mean().iloc[-1]
    rebound_ratio = ma15 / df['Close'].iloc[-1] if df['Close'].iloc[-1] > 0 else 0
    
    total_score = vol_ratio * value_ratio * rebound_ratio
    
    reason_list = []
    if vol_ratio > 1.5:
        reason_list.append(f"🔥 평소 대비 거래량 {vol_ratio:.1f}배 폭발")
    if value_ratio > 1.1:
        reason_list.append("📉 단기 과매도 바닥권")
    if rebound_ratio >= 0.95 and rebound_ratio <= 1.05:
        reason_list.append("📈 15일 이평선 안착")
        
    if len(reason_list) == 0:
        comment = "⚙️ 3대 조건 완만하게 상승 전환 중"
    else:
        comment = " / ".join(reason_list) + " (매집 유력)"
    
    return total_score, comment

# 3. 추천 종목 산출
def get_ai_recommendations(df):
    results = []
    for _, row in df.head(20).iterrows():
        try:
            df_chart = fdr.DataReader(row['Code'], start=(datetime.now() - timedelta(days=25)))
            score, comment = get_total_strategy_score(df_chart)
            if score > 0:
                results.append({
                    'Code': row['Code'], 
                    'Name': row['Name'], 
                    'Score': score, 
                    'Reason': comment
                })
        except:
            continue
            
    if not results:
        return pd.DataFrame(columns=['Code', 'Name', 'Score', 'Reason'])
        
    return pd.DataFrame(results).sort_values(by='Score', ascending=False).head(5).reset_index(drop=True)

# 4. UI 구성 (사이드바)
st.sidebar.header("⚙️ AI 분석 설정")
st.sidebar.info("💡 수급, 낙폭과대, 이평선 안착을 동시에 만족하는 종목을 찾고 구체적인 이유를 분석합니다.")

if st.sidebar.button("🚀 3대 조건 통합 매집주 분석 실행"):
    with st.spinner('3대 알고리즘 돌리며 상세 분석 생성 중...'):
        st.session_state.kospi_recs = get_ai_recommendations(fdr.StockListing('KOSPI'))
        st.session_state.kosdaq_recs = get_ai_recommendations(fdr.StockListing('KOSDAQ'))
    st.rerun()

# 📌 유튜브 요약본 입력창 구역
st.sidebar.markdown("---")
st.sidebar.header("📺 유튜브 당일 내용 입력")
youtube_input = st.sidebar.text_area(
    "제미나이가 알려준 오늘 자 요약 내용을 그대로 복사(Ctrl+C)해서 여기에 붙여넣기(Ctrl+V) 하세요.",
    height=150,
    placeholder="여기에 붙여넣으면 오른쪽에 바로 나타납니다!"
)

# 🔍 상세 종목 차트 설정 구역
st.sidebar.markdown("---")
st.sidebar.header("🔍 상세 차트 시간 설정")
selected_name = st.sidebar.selectbox("종목명 검색", all_stocks['Name'].tolist())
target_code = all_stocks[all_stocks['Name'] == selected_name].iloc[0]['Code']

chart_interval = st.sidebar.selectbox(
    "차트 시간 단위 선택",
    ["1분봉 보기", "5분봉 보기", "15분봉 보기", "30분봉 보기", "1시간봉 보기", "일봉 보기"]
)

interval_map = {
    "1분봉 보기": ("1m", "1d"),
    "5분봉 보기": ("5m", "1d"),
    "15분봉 보기": ("15m", "1d"),
    "30분봉 보기": ("30m", "2d"),
    "1시간봉 보기": ("60m", "7d"),
    "일봉 보기": ("1d", "3mo")
}
yf_interval, yf_period = interval_map[chart_interval]

# 메인 레이아웃 분할 (좌측 2 : 우측 1)
main_col, side_col = st.columns([2, 1])

with main_col:
    def display_recommendations(recs, title):
        st.subheader(title)
        if recs is not None and not recs.empty:
            for idx, row in recs.iterrows():
                with st.expander(f"👑 TOP {idx+1} : {row['Name']} ({row['Code']})", expanded=True):
                    st.info(f"**분석 결과:** {row['Reason']}")
        else:
            st.info("왼쪽 [분석 실행] 버튼을 누르면 상세한 분석 이유와 함께 추천 종목이 산출됩니다.")

    # 원래 코드에 있던 매집주 TOP 5 추천 리스트 정상 출력 구역
    if 'kospi_recs' in st.session_state: display_recommendations(st.session_state.kospi_recs, "🏛️ 코스피 상세 분석 베스트 5")
    if 'kosdaq_recs' in st.session_state: display_recommendations(st.session_state.kosdaq_recs, "🧬 코스닥 상세 분석 베스트 5")

    st.markdown("---")

    # 📊 상세 차트 구역
    st.header(f"📊 {selected_name} ({target_code}) - {chart_interval}")
    
    # 📈 [신규 보강] 현재가, 등락률, 시가총액 실시간 카드 배치 구역
    try:
        is_kospi = target_code in fdr.StockListing('KOSPI')['Code'].values
        yf_symbol = f"{target_code}.KS" if is_kospi else f"{target_code}.KQ"
        
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        
        price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        prev_close = info.get('previousClose', 0)
        diff = price - prev_close
        diff_rate = (diff / prev_close) * 100 if prev_close != 0 else 0
        
        # 3열 구조로 깔끔하게 숫자 카드 표시
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{price:,}원", f"{diff:,.0f}원")
        c2.metric("등락률", f"{diff_rate:.2f}%", f"{'▲' if diff > 0 else '▼'}")
        c3.metric("시가총액", f"{info.get('marketCap', 0) / 100000000:.0f}억원")
        st.markdown("---")
    except Exception as e:
        st.info("💡 실시간 상세 지표를 동기화하고 있습니다...")

    # 네이버 주가 다이렉트 새 창 연결 링크 버튼
    naver_pop_url = f"https://m.stock.naver.com/domestic/stock/{target_code}/total"
    st.link_button(f"🔗 {selected_name} 네이버 증권 실시간 호가/차트 새 창으로 열기", naver_pop_url, use_container_width=True)
    
    # 📈 내부 분봉 생성
    with st.spinner('실시간 분봉 데이터를 가공하고 있습니다...'):
        try:
            df_mini = ticker.history(period=yf_period, interval=yf_interval)
            
            if not df_mini.empty:
                # 마우스 전용 한글 툴팁 가이드 생성
                hover_texts = []
                for idx, row in df_mini.iterrows():
                    time_str = idx.strftime('%Y-%m-%d %H:%M') if yf_interval != "1d" else idx.strftime('%Y-%m-%d')
                    
                    text = (
                        f"<b>⏰ 일시:</b> {time_str}<br>"
                        f"<b>📈 시가:</b> {int(row['Open']):,}원<br>"
                        f"<b>🔥 고가:</b> {int(row['High']):,}원<br>"
                        f"<b>📉 저가:</b> {int(row['Low']):,}원<br>"
                        f"<b>💎 종가:</b> {int(row['Close']):,}원<br>"
                        f"<b>📊 거래량:</b> {int(row['Volume']):,}주"
                    )
                    hover_texts.append(text)

                # 캔들스틱 차트 생성
                fig = go.Figure(data=[go.Candlestick(
                    x=df_mini.index,
                    open=df_mini['Open'],
                    high=df_mini['High'],
                    low=df_mini['Low'],
                    close=df_mini['Close'],
                    increasing_line_color='red',   # 한국식 빨간양봉
                    decreasing_line_color='blue',  # 한국식 파란음봉
                    text=hover_texts,              
                    hoverinfo="text"               
                )])
                
                # Y축 원화 포맷팅 및 한글 패치 완료
                fig.update_layout(
                    height=450, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_rangeslider_visible=False,
                    yaxis=dict(
                        tickformat=",.0f",         
                        ticksuffix="원",            
                        side="right"               
                    ),
                    hoverlabel=dict(
                        bgcolor="white",           
                        font_size=13,              
                        font_family="Malgun Gothic" 
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ 주말이거나 장 개시 전이라 실시간 분봉 데이터가 일시적으로 비어있습니다.")
        except Exception as e:
            st.error("🚨 글로벌 금융 통신 지연이 발생했습니다. 위의 [네이버 증권 열기] 버튼을 이용해 실시간 대응해 주세요.")

# 우측 영역: 메모장 텍스트 즉시 출력
with side_col:
    st.subheader("🎯 김앤오 수익연구소 당일 매매")
    if youtube_input:
        st.info(youtube_input)
    else:
        st.write("👈 왼쪽 사이드바 입력창에 오늘 자 유튜브 요약 내용을 붙여넣으면 여기에 즉시 표시됩니다.")