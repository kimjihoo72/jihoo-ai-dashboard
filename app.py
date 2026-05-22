import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import timedelta

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V5.6", layout="wide")
st.title("🛡️ AI 1주일 뒤 목표가 예측 시스템 V5.6")
st.markdown("### 📅 전 그래프 미래 확장: 7일 뒤 시나리오 입체 분석 (오류 복구 완료)")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

EXCHANGE_RATE = 1350 # 엔비디아 원화 변환용

def run_v56_engine(symbol):
    df = yf.Ticker(symbol).history(period='1y')
    df = df.dropna(subset=['Close'])
    if df.empty or len(df) < 60: return None
    df = df.copy()

    # [핵심 수정 1] 미국 주식과 한국 주식의 타임존 격차로 인한 결합 오류 원천 차단
    df.index = pd.to_datetime(df.index).tz_localize(None)

    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE

    # --- 기초 지표 계산 ---
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Momentum_7d'] = df['Close'].pct_change(7)
    df['Volat'] = df['Close'].pct_change().rolling(10).std()

    # --- 7일 뒤 예측가 수식 ---
    df['Pattern_Pred'] = df['Close'] + (df['Close'] - df['SMA20']) * 0.6
    df['Sent_Pred'] = df['Close'] * (1 + df['Momentum_7d'])
    df['Macro_Pred'] = df['Close'] * (1 - (df['Volat'] * np.sqrt(7))) 
    df['Final_Pred_Price'] = (df['Pattern_Pred'] * 0.4) + (df['Sent_Pred'] * 0.3) + (df['Macro_Pred'] * 0.3)
    
    # 타율 채점
    df['Next_Target'] = np.where(df['Close'].shift(-7) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Pred_Price'] > df['Close'], 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_clean = df.dropna(subset=['SMA20', 'Volat']).copy()
    df_hit = df_clean.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0
    
    # --- [핵심 수정 2] 미래 7일 타임라인 결합 안정화 ---
    last_date = df_clean.index[-1]
    future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
    
    future_df = pd.DataFrame(index=future_dates, columns=df_clean.columns)
    
    # 데이터 연결선 부드럽게 잇기
    future_df.loc[last_date] = df_clean.iloc[-1] 
    future_df.loc[future_dates[-1], 'Pattern_Pred'] = df_clean['Pattern_Pred'].iloc[-1]
    future_df.loc[future_dates[-1], 'Sent_Pred'] = df_clean['Sent_Pred'].iloc[-1]
    future_df.loc[future_dates[-1], 'Macro_Pred'] = df_clean['Macro_Pred'].iloc[-1]
    future_df.loc[future_dates[-1], 'Final_Pred_Price'] = df_clean['Final_Pred_Price'].iloc[-1]
    future_df = future_df.sort_index()

    return {
        'data': df_clean, 
        'future_data': future_df, 
        'hit_rate': hit_rate, 
        'price': int(df_clean['Close'].iloc[-1]),
        'pred_price': int(df_clean['Final_Pred_Price'].iloc[-1]),
        'p_pred': int(df_clean['Pattern_Pred'].iloc[-1]),
        's_pred': int(df_clean['Sent_Pred'].iloc[-1]),
        'm_pred': int(df_clean['Macro_Pred'].iloc[-1])
    }

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v56_engine(sym) for name, sym in stocks.items()}

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
        f_df = res['future_data']

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (7일 추세 연장)")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig1.add_trace(go.Scatter(x=f_df.index, y=f_df['Pattern_Pred'], name="예측선", line=dict(color="#deff9a", width=2, dash="dash")))
            fig1.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig1, use_container_width=True)
            st.info(f"💡 **패턴 예측:** 1주 뒤 **{res['p_pred']:,}원** 목표")

        with col_b:
            st.subheader("2️⃣ 감성투자 (주간 심리 모멘텀)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig2.add_trace(go.Scatter(x=f_df.index, y=f_df['Sent_Pred'], name="예측선", line=dict(color="#00CC96", width=2, dash="dash")))
            fig2.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig2, use_container_width=True)
            st.info(f"💡 **심리 예측:** 1주 뒤 **{res['s_pred']:,}원** 목표")

        with col_c:
            st.subheader("3️⃣ 변동성 방어 (주간 최저 보루)")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=df_tail.index, y=df_tail['Close'], name="주가", line=dict(color="white", width=2)))
            fig3.add_trace(go.Scatter(x=f_df.index, y=f_df['Macro_Pred'], name="방어선", line=dict(color="#EF553B", width=2, dash="dash")))
            fig3.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig3, use_container_width=True)
            st.info(f"💡 **거시 방어:** 1주 뒤 최저 **{res['m_pred']:,}원** 지지")

        st.divider()

        st.subheader("🚀 1주일 뒤 AI 최종 통합 시나리오 (Final Synthesis)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="실제 주가 역사", line=dict(color="white", width=3)))
        final_fig.add_trace(go.Scatter(x=f_df.index, y=f_df['Final_Pred_Price'], name="AI 최종 시나리오선", line=dict(color="#FFA15A", width=3, dash='dot')))
        
        final_fig.add_bar(x=[f_df.index[-1]], y=[abs(res['pred_price'] - res['price'])], base=[min(res['price'], res['pred_price'])],
                          name="예측 변동폭", marker_color='rgba(255, 161, 90, 0.4)', width=1000*60*60*24*3)
                          
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
