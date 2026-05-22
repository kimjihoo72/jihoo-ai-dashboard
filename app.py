import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V5.9", layout="wide")
st.title("🛡️ AI 1주일 뒤 목표가 예측 시스템 V5.9")
st.markdown("### 📅 완벽한 꺾은 선 그래프 (주말/공휴일 자동 제거 기술 적용)")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

EXCHANGE_RATE = 1350 # 엔비디아 원화 변환용

def run_v59_engine(symbol):
    try:
        df = yf.Ticker(symbol).history(period='1y')
        if df.empty: return None
        df = df.dropna(subset=['Close']).copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        if len(df) < 50: return None
    except Exception as e:
        return None

    # --- 3대 기초 핵심 지표 계산 ---
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Momentum_7d'] = df['Close'].pct_change(7)
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df = df.dropna(subset=['SMA20', 'Volat']).copy()

    # --- 7일 뒤 예측 가격 산출 수식 ---
    df['Pattern_Pred'] = df['Close'] + (df['Close'] - df['SMA20']) * 0.6
    df['Sent_Pred'] = df['Close'] * (1 + df['Momentum_7d'])
    df['Macro_Pred'] = df['Close'] * (1 - (df['Volat'] * np.sqrt(7))) 
    df['Final_Pred_Price'] = (df['Pattern_Pred'] * 0.4) + (df['Sent_Pred'] * 0.3) + (df['Macro_Pred'] * 0.3)

    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE
        df['Pattern_Pred'] = df['Pattern_Pred'] * EXCHANGE_RATE
        df['Sent_Pred'] = df['Sent_Pred'] * EXCHANGE_RATE
        df['Macro_Pred'] = df['Macro_Pred'] * EXCHANGE_RATE
        df['Final_Pred_Price'] = df['Final_Pred_Price'] * EXCHANGE_RATE

    df['Next_Target'] = np.where(df['Close'].shift(-7) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Pred_Price'] > df['Close'], 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_hit = df.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0

    # --- 이번주 데이터 추출 (5/18 ~ 5/22) ---
    this_week_df = df[(df.index >= '2026-05-18') & (df.index <= '2026-05-22')].copy()
    if this_week_df.empty: 
        this_week_df = df.tail(5).copy()

    last_date = this_week_df.index[-1]
    current_price = this_week_df['Close'].iloc[-1]
    target_date = pd.Timestamp('2026-05-29') # 다음주 마감일 고정

    # 예측선 렌더링용 X, Y 좌표 (단 2개의 점으로 완벽한 직선 형성)
    pred_x = [last_date, target_date]

    return {
        'this_week_df': this_week_df,
        'pred_x': pred_x,
        'target_date': target_date,
        'hit_rate': hit_rate,
        'price': int(current_price),
        'pred_price': int(df['Final_Pred_Price'].iloc[-1]),
        'p_pred': int(df['Pattern_Pred'].iloc[-1]),
        's_pred': int(df['Sent_Pred'].iloc[-1]),
        'm_pred': int(df['Macro_Pred'].iloc[-1])
    }

# 주말(토, 일)을 차트에서 삭제하는 공통 레이아웃 함수
def apply_weekend_break(fig):
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])], # 토요일~월요일 사이의 공백을 시각적으로 삭제
        tickformat="%m-%d"
    )
    fig.update_layout(template="plotly_dark", showlegend=False, margin=dict(l=10,r=10,t=10,b=10))
    return fig

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v59_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} 이번주 분석 및 다음주 예측 타임라인")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("이번주 종가 (05-22)", f"{res['price']:,} 원")
        c2.metric("🎯 다음주 최종 목표가 (05-29)", f"{res['pred_price']:,} 원", f"{res['pred_price'] - res['price']:,} 원")
        c3.metric("🔥 알고리즘 타율", f"{res['hit_rate']}%")
        st.divider()

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (추세 연장)")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=res['this_week_df'].index, y=res['this_week_df']['Close'], name="실제 주가", mode='lines', line=dict(color="white", width=3)))
            fig1.add_trace(go.Scatter(x=res['pred_x'], y=[res['price'], res['p_pred']], name="예측선", mode='lines', line=dict(color="#deff9a", width=2, dash="dash")))
            fig1 = apply_weekend_break(fig1)
            fig1.update_layout(height=280)
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            st.subheader("2️⃣ 감성투자 (모멘텀)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=res['this_week_df'].index, y=res['this_week_df']['Close'], name="실제 주가", mode='lines', line=dict(color="white", width=3)))
            fig2.add_trace(go.Scatter(x=res['pred_x'], y=[res['price'], res['s_pred']], name="예측선", mode='lines', line=dict(color="#00CC96", width=2, dash="dash")))
            fig2 = apply_weekend_break(fig2)
            fig2.update_layout(height=280)
            st.plotly_chart(fig2, use_container_width=True)

        with col_c:
            st.subheader("3️⃣ 변동성 방어 (하단 보루)")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=res['this_week_df'].index, y=res['this_week_df']['Close'], name="실제 주가", mode='lines', line=dict(color="white", width=3)))
            fig3.add_trace(go.Scatter(x=res['pred_x'], y=[res['price'], res['m_pred']], name="방어선", mode='lines', line=dict(color="#EF553B", width=2, dash="dash")))
            fig3 = apply_weekend_break(fig3)
            fig3.update_layout(height=280)
            st.plotly_chart(fig3, use_container_width=True)

        st.divider()

        st.subheader("🚀 AI 최종 통합 시나리오 (5/18 ~ 5/29)")
        final_fig = go.Figure()
        
        # 1. 실제 주가 꺾은 선
        final_fig.add_trace(go.Scatter(x=res['this_week_df'].index, y=res['this_week_df']['Close'], name="이번주 실제 주가", mode='lines', line=dict(color="white", width=4)))
        
        # 2. 다음주 예측 점선
        final_fig.add_trace(go.Scatter(x=res['pred_x'], y=[res['price'], res['pred_price']], name="AI 최종 시나리오", mode='lines', line=dict(color="#FFA15A", width=3, dash='dot')))
        
        # 3. 목표가 마커 핀
        final_fig.add_trace(go.Scatter(
            x=[res['target_date']], 
            y=[res['pred_price']], 
            mode='markers+text',
            name='최종 목표가',
            text=[f"  {res['pred_price']:,}원 마감 예정"],
            textposition="top center",
            marker=dict(color='#FFA15A', size=12, symbol='star')
        ))
        
        final_fig = apply_weekend_break(final_fig)
        final_fig.update_yaxes(title="가격 (원)", tickformat=",.0f")
        final_fig.update_layout(height=450)
        st.plotly_chart(final_fig, use_container_width=True)

with tabs[0]: 
    st.subheader("🚥 다음주(05-29) AI 최종 목표가 브리핑")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            cols[j].markdown(f"#### {n}")
            if r['pred_price'] > r['price']: 
                cols[j].success(f"🟢 다음주 상승 전망\n\n목표가: {r['pred_price']:,}원")
            else: 
                cols[j].error(f"🔴 다음주 조정 리스크\n\n방어선: {r['pred_price']:,}원")
