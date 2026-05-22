import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V2.1", layout="wide")
st.title("🛡️ AI 통합 리스크 관제 시스템 V2.1")
st.markdown("### 📊 3대 핵심 지표(기술·심리·거시) 기반 실시간 전략 엔진")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

def run_v2_engine(symbol):
    # 1. 데이터 수집 및 [핵심 수정] 주말/공휴일 빈 데이터(NaN) 즉시 제거
    df = yf.Ticker(symbol).history(period='1y')
    df = df.dropna(subset=['Close']) # 주가 데이터가 비어있는 행은 원천 차단
    
    if df.empty or len(df) < 50: 
        return None
    df = df.copy()

    # [1요소] 기술 분석: SMA20
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Score_Tech'] = np.where(df['Close'] > df['SMA20'], 40, 10)

    # [2요소] 심리 분석: 모멘텀(3일 수익률 기반)
    df['Momentum'] = df['Close'].pct_change(3)
    df['Score_Sent'] = np.where(df['Momentum'] > 0, 30, 5)

    # [3요소] 거시 변동성: 10일 표준편차 기반 리스크 측정
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df['Score_Macro'] = np.where(df['Volat'] < df['Volat'].mean(), 30, 0)

    # [최종] AI 통합 점수 (0~100점)
    df['AI_Final_Score'] = df['Score_Tech'] + df['Score_Sent'] + df['Score_Macro']
    
    # 예측 타율 계산 (점수 70점 이상일 때 다음날 상승하면 정답)
    df['Next_Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['AI_Final_Score'] >= 70, 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    # 지표 계산으로 인해 앞부분에 생긴 NaN 행 및 마지막 예측 행 제외하고 깨끗한 데이터만 추출
    df_clean = df.dropna(subset=['SMA20', 'Volat']).copy()
    df_hit = df_clean.dropna(subset=['Next_Target']).copy()
    
    if not df_hit.empty:
        hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1)
    else:
        hit_rate = 0.0
        
    return {
        'data': df_clean, 
        'hit_rate': hit_rate, 
        'price': int(df_clean['Close'].iloc[-1]) if not df_clean.empty else 0
    }

# 데이터 수집 (카카오 포함)
stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v2_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력 로직 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} AI 심층 관제")
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{res['price']:,}원" if "KS" in stocks[name] else f"${res['price']:,}")
        c2.metric("AI 예측 타율", f"{res['hit_rate']}%")
        
        last_score = res['data']['AI_Final_Score'].iloc[-1]
        c3.metric("현재 AI 위험 점수", f"{100 - last_score}점", delta="-안전" if last_score >= 70 else "+위험")

        # [최종 그래프] 주가 + AI 통합 점수 시각화
        st.subheader("🚀 3대 지표 통합 AI 의사결정 추이 (Final Graph)")
        fig = go.Figure()
        
        # 주가 라인
        fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="주가(Price)", yaxis="y1", line=dict(color="#ffffff", width=2)))
        # AI 점수 바 (배경)
        fig.add_trace(go.Bar(x=res['data'].index, y=res['data']['AI_Final_Score'], name="AI 통합 점수", yaxis="y2", opacity=0.3, 
                             marker_color=np.where(res['data']['AI_Final_Score'] >= 70, '#00CC96', '#EF553B')))
        
        fig.update_layout(
            yaxis=dict(title="주가 (Price)"),
            yaxis2=dict(title="AI Score (0-100)", overlaying="y", side="right", range=[0, 100]),
            template="plotly_dark", height=500
        )
        st.plotly_chart(fig, use_container_width=True)

with tabs[0]: # 종합 관제방
    st.subheader("🚥 실시간 4대 종목 AI 리스크 신호등")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            score = r['data']['AI_Final_Score'].iloc[-1]
            cols[j].markdown(f"#### {n}")
            if score >= 70: cols[j].success(f"🟢 매수 우세 ({score}점)")
            elif score >= 40: cols[j].warning(f"🟡 관망 필요 ({score}점)")
            else: cols[j].error(f"🔴 위험 감지 ({score}점)")
