import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

# 페이지 기본 설정
st.set_page_config(page_title="지후의 AI 관제 대시보드", layout="wide")
st.title("🛡️ 4대 테크 연동형 AI 리스크 관제 대시보드")

# 5개의 웅장한 방 탭 생성
tabs = st.tabs(["🏠 종합 관제방", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🍎 애플"])

# --- 핵심 공통 엔진 (백테스팅 + 비용/수익 계산) ---
def run_advanced_engine(ticker_symbol, name):
    # 1. 데이터 수引き
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(period='1y')
    
    if df.empty or len(df) < 50:
        return None
        
    df = df.copy()
    
    # 2. 이동평균선 및 정답지(Next_Target) 생성
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Next_Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    df = df.dropna()
    
    if df.empty:
        return None

    # 3. AI 예측 및 채점
    df['AI_Prediction'] = np.where(df['Close'] > df['SMA20'], 1, 0)
    df['Match'] = np.where(df['AI_Prediction'] == df['Next_Target'], '정답 (Hit)', '오답 (Miss)')
    
    # 4. [복구] 비용 및 누적 수익률 계산 로직
    # 예측이 '상승(1)'일 때 매수했다고 가정하여 수익률 계산 (거래비용 0.1% 반영)
    df['Daily_Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = np.where(df['AI_Prediction'] == 1, df['Daily_Return'], 0)
    
    # 매수 신호가 바뀔 때 거래 비용 차감
    df['Signal_Change'] = df['AI_Prediction'].diff().abs()
    df.loc[df['Signal_Change'] > 0, 'Strategy_Return'] -= 0.001 
    
    # 누적 자산 지수 계산 (시작점 1.0)
    df['Cum_Hold_Return'] = (1 + df['Daily_Return'].fillna(0)).cumprod()
    df['Cum_Strategy_Return'] = (1 + df['Strategy_Return'].fillna(0)).cumprod()
    
    hit_rate = (len(df[df['Match'] == '정답 (Hit)']) / len(df)) * 100
    
    return {
        'hit_rate': round(hit_rate, 1),
        'current_price': int(df['Close'].iloc[-1]),
        'data': df
    }

# --- 데이터 연동 시작 ---
stocks = {
    "SK하이닉스": {"symbol": "000660.KS", "tab_idx": 1},
    "삼성전자": {"symbol": "005930.KS", "tab_idx": 2},
    "엔비디아": {"symbol": "NVDA", "tab_idx": 3},
    "애플": {"symbol": "AAPL", "tab_idx": 4}
}

results = {}
for name, info in stocks.items():
    results[name] = run_advanced_engine(info['symbol'], name)

# --- 종합 관제방 (첫 번째 탭) ---
with tabs[0]:
    st.header("🏠 4大 테크 실시간 모니터링 현황")
    col1, col2, col3, col4 = st.columns(4)
    
    for i, (name, res) in enumerate(results.items()):
        if res:
            with [col1, col2, col3, col4][i]:
                st.metric(label=f"{name} 현재가", value=f"{res['current_price']:,} 원" if "KS" in stocks[name]['symbol'] else f"${res['current_price']:,}")
                st.subheader(f"🎯 AI 타율: {res['hit_rate']}%")

# --- 개별 종목 방 채우기 (2~5번째 탭) ---
for name, info in stocks.items():
    res = results[name]
    if res:
        with tabs[info['tab_idx']]:
            st.header(f"📈 {name} AI 상세 분석 리포트")
            
            # 대시보드 상단 스코어보드
            c1, c2 = st.columns(2)
            c1.metric(label="현재 주가", value=f"{res['current_price']:,} 원" if "KS" in info['symbol'] else f"${res['current_price']:,}")
            c2.metric(label="🎯 AI 알고리즘 최종 예측 타율", value=f"{res['hit_rate']} %")
            
            # 그래프 1: AI 예측 성공 여부 산점도
            st.subheader("📊 최근 90일 AI 예측 히트맵")
            fig_scatter = px.scatter(res['data'].tail(90), x=res['data'].tail(90).index, y='Close', color='Match',
                                     color_discrete_map={'정답 (Hit)': '#00CC96', '오답 (Miss)': '#EF553B'})
            st.plotly_chart(fig_scatter, use_container_width=True)
            
            # [복구] 그래프 2: 누적 자산 평가액 추이 그래프 (단순 보유 vs AI 전략)
            st.subheader("💰 거래 비용을 반영한 누적 자산 평가 추이")
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Cum_Hold_Return'], name='순수 보유 (Buy & Hold)', line=dict(color='#AB63FA')))
            fig_line.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Cum_Strategy_Return'], name='AI 리스크 관리 전략', line=dict(color='#FFA15A')))
            fig_line.update_layout(xaxis_title="날짜", yaxis_title="자산 가치 (배수)")
            st.plotly_chart(fig_line, use_container_width=True)
