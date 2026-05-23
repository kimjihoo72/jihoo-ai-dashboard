import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
import requests

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V8.0", layout="wide")
st.title("🛡️ AI 자율 관제 및 과거 검증(Backtesting) 시스템 V8.0")
st.markdown("### 📊 가속도 예측 알고리즘 + 5영업일 전 예측력 실시간 검증 룸")

# --- 텔레그램 알림 설정 사이드바 ---
st.sidebar.header("🚨 조기 경보 시스템 설정")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
chat_id = st.sidebar.text_input("Telegram Chat ID")
alert_enabled = st.sidebar.checkbox("실시간 알림 활성화", value=False)

def send_telegram_message(token, chat_id, text):
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": text})
    except: pass

# 멀티 섹터 포트폴리오
stocks = {
    "🐻 SK하이닉스": "000660.KS", 
    "⚡ 삼성전자": "005930.KS", 
    "🟢 엔비디아": "NVDA", 
    "🟡 카카오": "035720.KS",
    "🚢 HMM (해운주)": "011200.KS"
}

tabs = st.tabs(list(stocks.keys()))
EXCHANGE_RATE = 1350

def run_v80_core_engine(symbol, name):
    try:
        df = yf.Ticker(symbol).history(period='1y')
        if df.empty: return None
        df = df.dropna(subset=['Close']).copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
    except:
        return None

    # 기초 지표 및 가속도 계산
    df['Velocity'] = df['Close'].diff()
    df['Acceleration'] = df['Velocity'].diff()
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Momentum_7d'] = df['Close'].pct_change(7)
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df = df.dropna(subset=['SMA20', 'Volat', 'Acceleration']).copy()

    if symbol == "NVDA":
        for col in ['Close', 'SMA20', 'Velocity', 'Acceleration']:
            df[col] = df[col] * EXCHANGE_RATE

    # ==========================================
    # 🎯 [신규] 5영업일 전 시점으로 백테스팅 계산
    # ==========================================
    backtest_error_pct = 0.0
    bt_x_timeline = []
    bt_actual_y = []
    bt_pred_y = []

    if len(df) > 35:
        # 5영업일 전까지의 데이터만 있는 '과거 타임머신 데이터프레임' 생성
        past_df = df.iloc[:-5].copy()
        # 실제 검증 대상이 될 최근 5영업일 데이터
        real_last_5 = df.tail(5).copy()
        
        past_last_price = past_df['Close'].iloc[-1]
        past_recent_acc = past_df['Acceleration'].tail(5).mean()
        
        # 5일 전 시점에서 계산한 미래 5일 예측 타깃값
        bt_p = past_last_price + (past_last_price - past_df['SMA20'].iloc[-1]) * 0.6 + (past_recent_acc * 1.5)
        bt_s = past_last_price * (1 + past_df['Momentum_7d'].iloc[-1]) + (past_recent_acc * 0.5)
        bt_m = past_last_price * (1 - (past_df['Volat'].iloc[-1] * np.sqrt(7))) + (past_recent_acc * 0.2)
        bt_f_target = (bt_p * 0.4) + (bt_s * 0.3) + (bt_m * 0.3)
        
        # 백테스팅용 X축 및 Y축 데이터 정렬
        bt_x_timeline = [past_df.index[-1].strftime('%m-%d')] + real_last_5.index.strftime('%m-%d').tolist()
        bt_actual_y = [past_last_price] + real_last_5['Close'].tolist()
        bt_pred_y = np.linspace(past_last_price, bt_f_target, 6).tolist()
        
        # 오차율 계산: |실제값 - 예측값| / 실제값 * 100
        real_final_price = real_last_5['Close'].iloc[-1]
        backtest_error_pct = abs(real_final_price - bt_f_target) / real_final_price * 100

    # ==========================================
    # 🔮 현재 시점 기준 미래 5일 예측 실시간 계산 (기존 로직)
    # ==========================================
    actual_df = df.tail(25).copy()
    last_date = actual_df.index[-1]
    last_price = actual_df['Close'].iloc[-1]
    recent_acc = actual_df['Acceleration'].tail(5).mean()

    future_dates = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=5)
    
    p_target = last_price + (last_price - actual_df['SMA20'].iloc[-1]) * 0.6 + (recent_acc * 1.5)
    s_target = last_price * (1 + actual_df['Momentum_7d'].iloc[-1]) + (recent_acc * 0.5)
    m_target = last_price * (1 - (actual_df['Volat'].iloc[-1] * np.sqrt(7))) + (recent_acc * 0.2)
    f_target = (p_target * 0.4) + (s_target * 0.3) + (m_target * 0.3)

    x_actual_str = actual_df.index.strftime('%m-%d').tolist()
    x_future_str = future_dates.strftime('%m-%d').tolist()
    x_pred_timeline = [x_actual_str[-1]] + x_future_str

    # 실시간 알림 기능
    if alert_enabled and telegram_token and chat_id:
        if f_target < last_price * 0.95:
            send_telegram_message(telegram_token, chat_id, f"🚨 [위험] {name} 5% 이상 하락 예측!")
        elif f_target > last_price * 1.05:
            send_telegram_message(telegram_token, chat_id, f"🚀 [호재] {name} 5% 이상 상승 포착!")

    return {
        'actual_df': actual_df, 'x_actual': x_actual_str, 'x_pred_timeline': x_pred_timeline, 'future_dates_str': x_future_str,
        'price': int(last_price), 'pred_price': int(f_target),
        'f_trend': np.linspace(last_price, f_target, 6), 'p_trend': np.linspace(last_price, p_target, 6),
        's_trend': np.linspace(last_price, s_target, 6), 'm_trend': np.linspace(last_price, m_target, 6),
        # 백테스팅 결과 데이터 반환
        'bt_x': bt_x_timeline, 'bt_actual': bt_actual_y, 'bt_pred': bt_pred_y, 'bt_error': round(backtest_error_pct, 2)
    }

def style_explorer_chart(fig, x_combined_range):
    fig.update_xaxes(type='category', categoryorder='array', categoryarray=x_combined_range, gridcolor='#F3F4F6')
    fig.update_yaxes(gridcolor='#F3F4F6', tickformat=",.0f")
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=20, r=20, t=15, b=20), showlegend=False)
    return fig

# --- 렌더링 시스템 ---
for idx, (name, sym) in enumerate(stocks.items()):
    res = run_v80_core_engine(sym, name)
    if not res: continue
    
    with tabs[idx]:
        st.header(f"{name} 자율 관제실")
        
        # 상단 대시보드 스코어보드 (백테스팅 점수 추가)
        c1, c2, c3 = st.columns(3)
        c1.metric("현재 실제 주가", f"{res['price']:,} 원")
        c2.metric("🎯 5일 뒤 최종 예측가", f"{res['pred_price']:,} 원", f"{res['pred_price'] - res['price']:,} 원")
        c3.metric("🔍 최근 5일 예측 오차율", f"{res['bt_error']}%", help="0%에 가까울수록 과거 예측이 정확했다는 뜻입니다.")
        st.divider()

        full_timeline = res['x_actual'] + res['future_dates_str']
        
        # 3대 서브 모듈 레이아웃 정상화 및 '변동성 방어' 이름 수정 완료
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.subheader("1️⃣ 패턴인식 (가속도 보정)")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig1.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['p_trend'], mode='lines', line=dict(color="#A3E635", width=2, dash="dash")))
            st.plotly_chart(style_explorer_chart(fig1, full_timeline), use_container_width=True)

        with col_b:
            st.subheader("2️⃣ 감성투자 (모멘텀)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig2.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['s_trend'], mode='lines', line=dict(color="#059669", width=2, dash="dash")))
            st.plotly_chart(style_explorer_chart(fig2, full_timeline), use_container_width=True)

        with col_c:
            st.subheader("3️⃣ 변동성 방어")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0284C7", width=2.5)))
            fig3.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['m_trend'], mode='lines', line=dict(color="#DC2626", width=2, dash="dash")))
            st.plotly_chart(style_explorer_chart(fig3, full_timeline), use_container_width=True)

        st.divider()

        # 실시간 예측 차트와 백테스팅 차트를 좌우로 배치하여 시각적 분석 극대화
        main_col1, main_col2 = st.columns(2)
        
        with main_col1:
            st.subheader("🚀 AI 실시간 통합 가속도 예측선")
            final_fig = go.Figure()
            final_fig.add_trace(go.Scatter(x=res['x_actual'], y=res['actual_df']['Close'], mode='lines', line=dict(color="#0EA5E9", width=3.5)))
            final_fig.add_trace(go.Scatter(x=res['x_pred_timeline'], y=res['f_trend'], mode='lines', line=dict(color="#F97316", width=3, dash='dashdot')))
            style_explorer_chart(final_fig, full_timeline)
            st.plotly_chart(final_fig, use_container_width=True)

        with main_col2:
            st.subheader("🔍 과거 예측력 검증 (지난 5일간의 성적)")
            bt_fig = go.Figure()
            # 실제 지난 5일간 일어난 주가 (검은색 실선)
            bt_fig.add_trace(go.Scatter(x=res['bt_x'], y=res['bt_actual'], name="실제 경로", mode='lines+markers', line=dict(color="#1F2937", width=3)))
            # 5일 전에 AI가 예상했던 주가 (주황색 점선)
            bt_fig.add_trace(go.Scatter(x=res['bt_x'], y=res['bt_pred'], name="AI 과거 예측", mode='lines+markers', line=dict(color="#F97316", width=2, dash="dash")))
            style_explorer_chart(bt_fig, res['bt_x'])
            st.plotly_chart(bt_fig, use_container_width=True)
