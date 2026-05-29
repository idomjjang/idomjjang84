import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="AI 매집주 분석기", layout="wide")

# 1. 데이터 로드 (가나다순 정렬 및 캐싱)
@st.cache_data(ttl=86400)
def get_all_market_list():
    kospi = fdr.StockListing('KOSPI')[['Code', 'Name']]
    kosdaq = fdr.StockListing('KOSDAQ')[['Code', 'Name']]
    return pd.concat([kospi, kosdaq]).sort_values(by='Name')

all_stocks = get_all_market_list()

# ⚡ [로직 업그레이드] 점수 계산 및 상세한 매집 이유 생성
def get_total_strategy_score(df):
    if len(df) < 15: return 0, "데이터 부족"
    
    # ① 수급 점수 (최근 거래량 폭발 여부)
    vol_ratio = df['Volume'].iloc[-3:].mean() / df['Volume'].iloc[-15:].mean()
    
    # ② 저평가 점수 (최근 15일 고점 대비 얼마나 바닥인지)
    highest = df['High'].iloc[-15:].max()
    value_ratio = highest / df['Close'].iloc[-1] if df['Close'].iloc[-1] > 0 else 0
    
    # ③ 기술적 반등 점수 (15일 이평선 돌파 및 안착 여부)
    ma15 = df['Close'].rolling(15).mean().iloc[-1]
    rebound_ratio = ma15 / df['Close'].iloc[-1] if df['Close'].iloc[-1] > 0 else 0
    
    # 종합 점수 산출
    total_score = vol_ratio * value_ratio * rebound_ratio
    
    # 📝 [핵심 추가] 조건별 수치를 해석해서 상세한 리포트 문장 작성
    reason_list = []
    if vol_ratio > 1.5:
        reason_list.append(f"🔥 평소 대비 거래량 {vol_ratio:.1f}배 폭발")
    if value_ratio > 1.1:
        reason_list.append("📉 단기 과매도 바닥권")
    if rebound_ratio >= 0.95 and rebound_ratio <= 1.05:
        reason_list.append("📈 15일 이평선 안착")
        
    # 만약 특별한 징후가 평범하다면 종합 코멘트 처리
    if len(reason_list) == 0:
        comment = "⚙️ 3대 조건 완만하게 상승 전환 중"
    else:
        comment = " / ".join(reason_list) + " (매집 유력)"
    
    return total_score, comment

# ⚡ 각 시장의 상위 종목 고속 스캔
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

# 3. UI 구성 (사이드바)
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
    height=250,
    placeholder="여기에 붙여넣으면 오른쪽에 바로 나타납니다!"
)

# 🔍 상세 종목 차트 설정 구역
st.sidebar.markdown("---")
st.sidebar.header("🔍 상세 종목 차트")
selected_name = st.sidebar.selectbox("종목명 검색", all_stocks['Name'].tolist())
target_code = all_stocks[all_stocks['Name'] == selected_name]['Code'].values[0]

if st.sidebar.button("🔄 차트 갱신"): 
    st.rerun()

# 메인 레이아웃 분할 (좌측 2 : 우측 1)
main_col, side_col = st.columns([2, 1])

with main_col:
    def display_recommendations(recs, title):
        st.subheader(title)
        if recs is not None and not recs.empty:
            # 5선 서식이 깨지지 않도록 세로로 깔끔하게 리포트 형식 출력
            for idx, row in recs.iterrows():
                with st.expander(f"👑 TOP {idx+1} : {row['Name']} ({row['Code']})", expanded=True):
                    st.info(f"**분석 결과:** {row['Reason']}")
        else:
            st.info("왼쪽 [분석 실행] 버튼을 누르면 상세한 분석 이유와 함께 추천 종목이 산출됩니다.")

    if 'kospi_recs' in st.session_state: display_recommendations(st.session_state.kospi_recs, "🏛️ 코스피 상세 분석 베스트 5")
    if 'kosdaq_recs' in st.session_state: display_recommendations(st.session_state.kosdaq_recs, "🧬 코스닥 상세 분석 베스트 5")

    st.markdown("---")

    # 상세 차트 화면 표시
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

# 우측 영역: 메모장 텍스트 즉시 출력
with side_col:
    st.subheader("🎯 김앤오 수익연구소 당일 매매")
    if youtube_input:
        st.info(youtube_input)
    else:
        st.write("👈 왼쪽 사이드바 입력창에 오늘 자 유튜브 요약 내용을 붙여넣으면 여기에 즉시 표시됩니다.")