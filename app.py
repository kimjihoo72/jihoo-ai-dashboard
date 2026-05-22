import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import timedelta

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V5.7", layout="wide")
st.title("🛡️ AI 1주일 뒤 목표가 예측 시스템 V5.7")
st.markdown("### 📅 전 그래프 미래 확장: 시각화 오류 완전 박멸 버전")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

EXCHANGE_RATE = 1350 # 엔비디아 원화 변환용

def run_v57_engine(symbol):
    try:
        df = yf.Ticker(symbol).history(period='1y')
        if df.empty: return None
        df = df.dropna(subset=['Close']).copy()
        
        # 타임존 통일 및 데이터 보정
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

    # 엔비디아인 경우 환율 계산 가동
    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE
        df['Pattern_Pred'] = df['Pattern_Pred'] * EXCHANGE_RATE
        df['Sent_Pred'] = df['Sent_Pred'] * EXCHANGE_RATE
        df['Macro_Pred'] = df['Macro_Pred'] * EXCHANGE_RATE
        df['Final_Pred_Price'] = df['Final_Pred_Price'] * EXCHANGE_RATE

    # 알고리즘 자체 타율 채점
    df['Next_Target'] = np.where(df['Close'].shift(-7) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Pred_Price'] > df['Close'], 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_hit = df.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0

    # --- [핵심 복구 포인트] 2점 벡터 매핑 데이터 빌드 ---
    last_date = df.index[-1]
    target_date = last_date + timedelta(days=7)
    current_price = df['Close'].iloc[-1]
    
    # 딕셔너리 리스트 구조로 Plotly에 직접 주입하여 판다스 인덱스 충돌 원천 차단
    future_data = {
        'dates': [last_date, target_date],
        'Pattern_Pred': [current_price, df['Pattern_Pred'].iloc[-1]],
        'Sent_Pred': [current_price, df['Sent_Pred'].iloc[-1]],
        'Macro_Pred': [current_price, df['Macro_Pred'].iloc[-1]],
        'Final_Pred_Price': [current_price, df['Final_Pred_Price'].iloc[-1]]
    }

    return {
        'data': df, 
        'future': future_data, 
        'hit_rate': hit_rate, 
        'price': int(current_price),
        'pred_price': int(df['Final_Pred_Price'].iloc[-1]),
        'p_pred': int(df['Pattern_Pred'].iloc[-1]),
        's_pred': int(df['Sent_Pred'].iloc[-1]),
        'm_pred': int(df['Macro_Pred'].iloc[-1])
    }

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v57_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} AI 1주일 미래 예측 통합 대시보드")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("현재 주가", f"{res['price']:,} 원")
        c2.metric("🎯 AI 1주일 뒤 최종 예측가", f"{res['pred_price']:,} 원", f"{res['pred_price'] - res['price']:,} 원")
        c3.metric("🔥 7일 예측 알고리즘 타율", f"{res['hit_rate']}%")
        st.divider()

        df_tail = res['data'].tail(45)
        f = res['future']

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (7일 추세 연장)")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig1.add_trace(go.Scatter(x=f['dates'], y=f['Pattern_Pred'], name="예측선", line=dict(color="#deff9a", width=2, dash="dash")))
            fig1.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=30,b=10))
            st.plotly_chart(fig1, use_container_width=True)
            st.info(f"💡 **패턴 예측:** 1주 뒤 **{res['p_pred']:,}원** 목표")

        with col_b:
            st.subheader("2️⃣ 감성투자 (주간 심리 모멘텀)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig2.add_trace(go.Scatter(x=f['dates'], y=f['Sent_Pred'], name="예측선", line=dict(color="#00CC96", width=2, dash="dash")))
            fig2.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=30,b=10))
            st.plotly_chart(fig2, use_container_width=True)
            st.info(f"💡 **심리 예측:** 1주 뒤 **{res['s_pred']:,}원** 목표")

        with col_c:
            st.subheader("3️⃣ 변동성 방어 (주간 최저 보루)")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig3.add_trace(go.Scatter(x=f['dates'], y=f['Macro_Pred'], name="방어선", line=dict(color="#EF553B", width=2, dash="dash")))
            fig3.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=30,b=10))
            st.plotly_chart(fig3, use_container_width=True)
            st.info(f"💡 **거시 방어:** 1주 뒤 최저 **{res['m_pred']:,}원** 지지")

        st.divider()

        st.subheader("🚀 1주일 뒤 AI 최종 통합 시나리오 (Final Synthesis)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="실제 주가 역사", line=dict(color="white", width=3)))
        final_fig.add_trace(go.Scatter(x=f['dates'], y=f['Final_Pred_Price'], name="AI 최종 시나리오선", line=dict(color="#FFA15A", width=3, dash='dot')))
        
        # 가독성을 위해 미래 최종 예측 점에 선명한 마커 지표 추가
        final_fig.add_trace(go.Scatter(
            x=[f['dates'][-1]], 
            y=[f['Final_Pred_Price'][-1]], 
            mode='markers+text',
            name='목표가',
            text=[f"  {res['pred_price']:,}원"],
            textposition="top right",
            marker=dict(color='#FFA15A', size=10)
        ))
                          
        final_fig.update_yaxes(title="가격 (원)", tickformat=",.0f")
        final_fig.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(final_fig, use_container_width=True)

with tabs[0]: 
    st.subheader("🚥 실시간 1주일 뒤 AI 최종 목표가 브리핑")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            cols[j].markdown(f"#### {n}")
            if r['pred_price'] > r['price']: 
                cols[j].success(f"🟢 1주일 뒤 상승 우세\n\n목표가: {r['pred_price']:,}원")
            else: 
                cols[j].error(f"🔴 1주일 뒤 리스크 감지\n\n방어선: {r['pred_price']:,}원")
