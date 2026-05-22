import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf

# 페이지 기본 설정
st.set_page_config(page_title="지후의 AI 관제 대시보드", layout="wide")
st.title("🛡️ 4대 테크 연동형 AI 리스크 관제 대시보드")

# 5개의 방 탭 생성 (지후님의 원래 디자인 복구!)
tabs = st.tabs(["🏠 종합 관제방", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🍎 애플"])

# --- SK하이닉스 방 (두 번째 탭) ---
with tabs[1]:
    st.header("🐻 SK하이닉스 AI 타율 검증소")
    
    # 1. 데이터 수집
    @st.cache_data(ttl=60)
    def load_hynix_data():
        ticker = yf.Ticker("000660.KS")
        history = ticker.history(period='1y')
        return history

    hynix_history = load_hynix_data()

    # 2. 방어형 백테스팅 엔진 (에러 방지용 안전장치 추가)
    def run_backtest_engine(df):
        # 데이터가 덜 불러와졌으면 계산 멈춤
        if df.empty or len(df) < 50:
            return 0.0, pd.DataFrame()
            
        df = df.copy()
        # 20일 이동평균선 및 내일 주가 상승/하락 정답지 만들기
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['Next_Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
        df = df.dropna()

        if df.empty:
            return 0.0, pd.DataFrame()

        # AI 예측 및 정답 채점
        df['AI_Prediction'] = np.where(df['Close'] > df['SMA20'], 1, 0)
        df['Match'] = np.where(df['AI_Prediction'] == df['Next_Target'], '정답 (Hit)', '오답 (Miss)')

        hit_rate = (len(df[df['Match'] == '정답 (Hit)']) / len(df)) * 100
        return round(hit_rate, 1), df

    hit_rate, backtest_data = run_backtest_engine(hynix_history)

    # 3. 화면에 출력
    st.metric(label="🎯 알고리즘 최종 예측 성공 타율", value=f"{hit_rate} %")

    # 데이터가 완벽하게 준비되었을 때만 그래프 그리기 (KeyError 원천 차단)
    if not backtest_data.empty and 'Match' in backtest_data.columns:
        fig = px.scatter(backtest_data.tail(90), x=backtest_data.tail(90).index, y='Close', color='Match')
        st.plotly_chart(fig)
    else:
        st.warning("데이터를 불러오고 계산하는 중입니다. 잠시 후 키보드 F5를 눌러 새로고침 해주세요!")

# 나머지 방들은 일단 빈 방으로 유지
with tabs[0]:
    st.write("여기는 모든 종목을 한눈에 보는 종합 관제방이 될 예정입니다.")
with tabs[2]:
    st.write("삼성전자 데이터 준비 중...")
