import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V3.0", layout="wide")
st.title("🛡️ AI 통합 리스크 관제 시스템 V3.0")
st.markdown("### 🔍 3중 필터링 시스템 (패턴·감성·변동성) 심층 분석")

# 탭 구성 (SK하이닉스, 삼성전자, 엔비디아, 카카오)
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

def run_v3_engine(symbol):
    # 데이터 수집 및 정제
    df = yf.Ticker(symbol).history(period='1y')
    df = df.dropna(subset=['Close'])
    if df.empty or len(df) < 60: return None
    df = df.copy()

    # --- [1요소] 패턴인식 (Technical: SMA20) ---
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Pattern_Score'] = np.where(df['Close'] > df['SMA20'], 1, 0)
    
    # --- [2요소] 감성투자 (Sentiment: Momentum) ---
    df['Momentum'] = df['Close'].pct_change(3)
    df['Sent_Score'] = np.where(df['Momentum'] > 0, 1, 0)
    
    # --- [3요소] 변동성 방어 (Macro: Volatility) ---
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    avg_volat = df['Volat'].mean()
    df['Macro_Score'] = np.where(df['Volat'] < avg_volat, 1, 0)

    # --- 통합 점수 및 성공 타율 계산 ---
    # 가중치: 패턴 40, 감성 30, 거시 30
    df['Final_Score'] = (df['Pattern_Score'] * 40) + (df['Sent_Score'] * 30) + (df['Macro_Score'] * 30)
    df['Next_Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Score'] >= 70, 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_clean = df.dropna(subset=['SMA20', 'Volat']).copy()
    df_hit = df_clean.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0
    
    return {'data': df_clean, 'hit_rate': hit_rate, 'price': int(df_clean['Close'].iloc[-1]), 'avg_volat': avg_volat}

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v3_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} AI 심층 관제 리포트")
        
        # 1. 상단 성공 타율 지표
        c1, c2 = st.columns(2)
        c1.metric("현재가", f"{res['price']:,}원" if "KS" in stocks[name] else f"${res['price']:,}")
        c2.metric("🎯 AI 알고리즘 성공 타율", f"{res['hit_rate']}%")
        
        st.divider()

        # 2. 개별 요소 분석 그래프 (3단 구성)
        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (추세)")
            fig1 = px.line(res['data'], y=['Close', 'SMA20'], color_discrete_map={'Close': 'white', 'SMA20': '#deff9a'})
            st.plotly_chart(fig1, use_container_width=True)
            last_p = res['data']['Pattern_Score'].iloc[-1]
            st.info(f"💡 **AI 판단:** {'주가가 이동평균선 위에 있어 상승 추세로 판단합니다.' if last_p == 1 else '추세가 꺾여 하락 압력이 강한 상태입니다.'}")

        with col_b:
            st.subheader("2️⃣ 감성투자 (심리)")
            fig2 = px.bar(res['data'].tail(30), y='Momentum', color='Sent_Score', color_continuous_scale=['#EF553B', '#00CC96'])
            st.plotly_chart(fig2, use_container_width=True)
            last_s = res['data']['Sent_Score'].iloc[-1]
            st.info(f"💡 **AI 판단:** {'시장 참여자들의 매수 심리가 회복되어 긍정적입니다.' if last_s == 1 else '과열 후 차익 실현 심리가 강해진 상태입니다.'}")

        with col_c:
            st.subheader("3️⃣ 변동성 방어 (거시)")
            fig3 = px.line(res['data'], y='Volat', line_dash_sequence=['dot'])
            fig3.add_hline(y=res['avg_volat'], line_color="red", annotation_text="위험 임계치")
            st.plotly_chart(fig3, use_container_width=True)
            last_m = res['data']['Macro_Score'].iloc[-1]
            st.info(f"💡 **AI 판단:** {'시장이 안정권에 있어 방어력이 충분합니다.' if last_m == 1 else '변동성이 급증하여 매크로 리스크 관리가 필요합니다.'}")

        st.divider()

        # 3. 최종 통합 예측 그래프
        st.subheader("🚀 최종 통합 AI 의사결정 추이 (Final Synthesis)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="주가(Price)", yaxis="y1", line=dict(color="white", width=2)))
        final_fig.add_trace(go.Bar(x=res['data'].index, y=res['data']['Final_Score'], name="AI 통합 점수", yaxis="y2", opacity=0.4, 
                                   marker_color=np.where(res['data']['Final_Score'] >= 70, '#00CC96', '#EF553B')))
        final_fig.update_layout(
            yaxis=dict(title="주가 (Price)"),
            yaxis2=dict(title="통합 점수 (0-100)", overlaying="y", side="right", range=[0, 100]),
            template="plotly_dark", height=600
        )
        st.plotly_chart(final_fig, use_container_width=True)
        st.success(f"현재 통합 AI 점수는 **{res['data']['Final_Score'].iloc[-1]}점**입니다. (70점 이상 시 매수 우세)")

with tabs[0]: # 종합 관제방
    st.subheader("🚥 실시간 종목별 AI 신호등")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            score = r['data']['Final_Score'].iloc[-1]
            cols[j].markdown(f"#### {n}")
            if score >= 70: cols[j].success(f"🟢 매수 ({score}점)")
            elif score >= 40: cols[j].warning(f"🟡 관망 ({score}점)")
            else: cols[j].error(f"🔴 대피 ({score}점)")
