import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import requests

# 페이지 설정 (라이트 테마 매칭 및 와이드 레이아웃)
st.set_page_config(page_title="지후의 AI 관제 V7.0", layout="wide")
st.title("🛡️ AI 자율 관제 및 조기 경보 시스템 V7.0")
st.markdown("### 📊 가속도 예측 알고리즘 + 섹터 확장 + 텔레그램 경보 통합본")

# --- [기능 3] 텔레그램 알림 설정 사이드바 ---
st.sidebar.header("🚨 조기 경보 시스템 설정")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password", help="봇파더에게 받은 토큰을 입력하세요.")
chat_id = st.sidebar.text_input("Telegram Chat ID", help="사용자의 텔레그램 ID를 입력하세요.")
alert_enabled = st.sidebar.checkbox("실시간 알림 활성화", value=False)

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        pass

# --- [기능 2] 포트폴리오 확장 (해운주 HMM 전격 추가) ---
stocks = {
    "🐻 SK하이닉스": "000660.KS", 
    "⚡ 삼성전자": "005930.KS", 
    "🟢 엔비디아": "NVDA", 
    "🟡 카카오": "035720.KS",
    "🚢 HMM (해운주)": "011200.KS"  # 새 섹터 확장 종목
}

tabs = st.tabs(list(stocks.keys()))
EXCHANGE_RATE = 1350

def run_v70_integrated_engine(symbol, name):
    try:
        # 데이터 자동 슬라이딩 (항상 최신 날짜 기준)
        df = yf.Ticker(symbol).history(period='1y')
        if df.empty: return None
        df = df.dropna(subset=['Close']).copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
    except Exception as e:
        return None

    # --- [기능 1] 수학적 엔진 고도화: 미분 및 가속도(Jerk) 개념 도입 ---
    # 1차 도함수(변화율) 및 2차 도함수(가속도) 계산
    df['Velocity'] = df['Close'].diff()
    df['Acceleration'] = df['Velocity'].diff()
    
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Momentum_7d'] = df['Close'].pct_change(7)
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df = df.dropna(subset=['SMA20', 'Volat', 'Acceleration']).copy()

    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE
        df['SMA20'] = df['SMA20'] * EXCHANGE_RATE
        df['Velocity'] = df['Velocity'] * EXCHANGE_RATE
        df['Acceleration'] = df['Acceleration'] * EXCHANGE_RATE

    # 최근 25영업일 실제 데이터 바인딩 (롤링 윈도우)
    actual_df = df.tail(25).copy()
    last_date = actual_df.index[-1]
    last_price = actual_df['Close'].iloc[-1]
    
    # 가속도 보정값 산출 (최근 5일간의 가속도 가중 평균)
    recent_acc = actual_df['Acceleration'].tail(5).mean()

    # 미래 5영업일 자동 생성
    future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=5)
    
    # 가속도가 반영된 3대 고도화 수식
    p_target = last_price + (last_price - actual_df['SMA20'].iloc[-1]) * 0.6 + (recent_acc * 1.5)
    s_target = last_price * (1 + actual_df['Momentum_7d'].iloc[-1]) + (recent_acc * 0.5)
    m_target = last_price * (1 - (actual_df['Volat'].iloc[-1] * np.sqrt(7))) + (recent_acc * 0.2)
    f_target = (p_target * 0.4) + (s_target * 0.3) + (m_target * 0.3)

    # 꺾은선 연장용 트렌드 생성 함수
    def generate_trend_line(start, end, steps=5):
        return np.linspace(start, end, steps + 1)

    # X축 건너뛰기 방지 카테고리 문자열 처리
    x_actual_str = actual_df.index.strftime('%m-%d').tolist()
    x_future_str = future_dates.strftime('%m-%d').tolist()
    x_pred_timeline = [x_actual_str[-1]] + x_future_str

    # --- [알림 조건 체크] 위험 및 돌파 감지 ---
    if alert_enabled and telegram_token and chat_id:
        # 가속도가 비정상적으로 급락하거나 하단 방어선 예측이 너무 낮을 때 경고
        if f_target < last_price * 0.95:
            send_telegram_message(telegram_token, chat_id, f"🚨 [AI 위험 경보] {name}의 5일 뒤 예측가가 현재가 대비 5% 이상 하락할 것으로 예측됩니다! 현재가: {int(last_price):,}원 / 예측가: {int(f_target):,}원")
        elif f_target > last_price * 1.05:
            send_telegram_message(telegram_token, chat_id, f"🚀 [AI 돌파 호재] {name} 강력 상승 랠리 포착! 현재가: {int(last_price):,}원 / 목표가: {int(f_target):,}원")

    return {
        'actual_df': actual_df,
        'x_actual': x_actual_str,
        'x_pred_timeline': x_pred_timeline,
        'future_dates_str': x_future_str,
        'price': int(last_price),
        'pred_price': int(f_target),
        'f_trend': generate_trend_line(last_price, f_target),
        'p_trend': generate_trend_line(last_price, p_target),
        's_trend': generate_trend_line(last_price, s_target),
        'm_trend': generate_trend_line(last_price, m_target),
    }

def style_explorer_chart(fig, x_combined_range):
    fig.update_xaxes(
        type='category', 
        categoryorder='array',
        categoryarray=x_combined_range,
        gridcolor='#F3F4F6'
    )
    fig.update_yaxes(gridcolor='#F3F4F6', tickformat=",.0f")
    fig.update_layout(
        plot_bgcolor='white', 
        paper_bgcolor='white',
        margin=dict(l=20, r=20, t=15, b=20),
        showlegend=False
    )
    return fig

# --- 메인 렌더링 루프 ---
for idx, (name, sym) in enumerate(stocks.items()):
    res = run_v70_integrated_engine(sym, name)
    if not res: continue
    
    with tabs[idx]:
        st.header(f"{name} 실시간 V7.0 자율 관제 상태")
        
        c1, c2 = st.columns(2)
        c2.metric("🎯 가속도 반영 5일 뒤 최종 예측가", f"{res['pred_price']:,} 원", f"{res['pred_price'] - res['price']:,} 원")
        c1.metric("현재 실제 주가", f"{res['price']:,} 원")
        st.divider()

        full_timeline = res['x_actual'] + res['future_dates_str']
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (가속도 보정)")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig1.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['p_trend'], mode='lines', line=dict(color="#A3E635", width=2, dash="dash")))
            fig1 = style_explorer_chart(fig1, full_timeline)
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            st.subheader("2️⃣ 감성투자 (모멘텀)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig2.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['s_trend'], mode='lines', line=dict(color="#059669", width=2, dash="dash")))
            fig2 = style_explorer_chart(fig2, full_timeline)
            st.plotly_chart(fig2, use_container_width=True)

        with col_b:
            pass # 불필요 컬럼 가독성 정렬용 방치
            
        with col_c:
            st.subheader("3️⃣ 변동성 방어 (하단 보루)")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig3.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['m_trend'], mode='lines', line=dict(color="#DC2626", width=2, dash="dash")))
            fig3 = style_explorer_chart(fig3, full_timeline)
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()

        st.subheader("🚀 AI 최종 통합 가속도 예측 추이")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], name="실제 주가", mode='lines', line=dict(color="#0EA5E9", width=3.5)))
        final_fig.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['f_trend'], name="AI 예측", mode='lines', line=dict(color="#F97316", width=3, dash='dashdot')))
        final_fig.add_trace(go.Scatter(
            x=[res['future_dates_str'][-1]], y=[res['pred_price']], 
            mode='markers+text', text=[f" 🎯 {res['pred_price']:,}원 마감 예상"],
            textposition="top center", marker=dict(color='#F97316', size=10)
        ))
        final_fig = style_explorer_chart(final_fig, full_timeline)
        st.plotly_chart(final_fig, use_container_width=True)
