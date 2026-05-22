import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V4.0", layout="wide")
st.title("🛡️ AI 통합 목표가 예측 시스템 V4.0")
st.markdown("### 🎯 3대 엔진(패턴·감성·변동성) 기반 실시간 예측 가격(KRW) 산출")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

# 고정 환율 (엔비디아 원화 변환용)
EXCHANGE_RATE = 1350 

def run_v4_engine(symbol):
    df = yf.Ticker(symbol).history(period='1y')
    df = df.dropna(subset=['Close'])
    if df.empty or len(df) < 60: return None
    df = df.copy()

    # 엔비디아(USD)인 경우 원화(KRW)로 변환
    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE

    # --- [1요소] 패턴인식 예측가 (추세 연장선) ---
    # 20일 이평선을 기준으로, 현재 주가가 이평선을 뚫고 올라가는 추세를 반영한 내일의 목표가
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['Pattern_Pred'] = df['Close'] + (df['Close'] - df['SMA20']) * 0.2
    
    # --- [2요소] 감성투자 예측가 (모멘텀 가속도) ---
    # 최근 3일간의 수익률(심리)을 기반으로 하루 더 지속된다고 가정한 목표가
    df['Momentum'] = df['Close'].pct_change(3)
    df['Sent_Pred'] = df['Close'] * (1 + (df['Momentum'] / 3))
    
    # --- [3요소] 변동성 방어 예측가 (하단 지지선) ---
    # 최근 10일간의 흔들림(표준편차)을 계산해, "최악의 경우 여기까지 빠질 수 있다"는 방어선 가격
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df['Macro_Pred'] = df['Close'] * (1 - df['Volat']) 

    # --- [최종] AI 통합 목표 예측가 (가중 평균) ---
    # 가중치: 패턴 40%, 감성 30%, 방어 30%
    df['Final_Pred_Price'] = (df['Pattern_Pred'] * 0.4) + (df['Sent_Pred'] * 0.3) + (df['Macro_Pred'] * 0.3)
    
    # 타율 채점: AI가 내일 주가가 오늘보다 오를 것(통합예측가 > 현재가)으로 예상했고, 실제로 올랐다면 Hit
    df['Next_Target'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Pred_Price'] > df['Close'], 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_clean = df.dropna(subset=['SMA20', 'Volat']).copy()
    df_hit = df_clean.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0
    
    return {'data': df_clean, 'hit_rate': hit_rate, 'price': int(df_clean['Close'].iloc[-1])}

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v4_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} AI 가격 예측 리포트")
        
        # 1. 상단 핵심 지표
        c1, c2, c3 = st.columns(3)
        current_price = res['price']
        predicted_price = int(res['data']['Final_Pred_Price'].iloc[-1])
        
        c1.metric("현재 종가", f"{current_price:,} 원")
        c2.metric("🎯 AI 내일 통합 목표가", f"{predicted_price:,} 원", f"{predicted_price - current_price:,} 원")
        c3.metric("🔥 알고리즘 성공 타율", f"{res['hit_rate']}%")
        st.divider()

        # 2. 3대 개별 요소 예측 가격 그래프
        col_a, col_b, col_c = st.columns(3)
        df_tail = res['data'].tail(60) # 최근 60일만 보여줘서 렌즈를 확대함

        with col_a:
            st.subheader("1️⃣ 패턴 추세 예측가")
            fig1 = px.line(df_tail, y=['Close', 'Pattern_Pred'], color_discrete_map={'Close': 'white', 'Pattern_Pred': '#deff9a'})
            fig1.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig1.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig1, use_container_width=True)
            pred1 = int(df_tail['Pattern_Pred'].iloc[-1])
            st.info(f"💡 **패턴 관점:** 이평선 추세를 연장했을 때 예상되는 내일 가격은 **{pred1:,}원**입니다.")

        with col_b:
            st.subheader("2️⃣ 감성 모멘텀 예측가")
            fig2 = px.line(df_tail, y=['Close', 'Sent_Pred'], color_discrete_map={'Close': 'white', 'Sent_Pred': '#00CC96'})
            fig2.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig2.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig2, use_container_width=True)
            pred2 = int(df_tail['Sent_Pred'].iloc[-1])
            st.info(f"💡 **심리 관점:** 최근 3일의 매수세가 이어진다면 도달 가능한 가격은 **{pred2:,}원**입니다.")

        with col_c:
            st.subheader("3️⃣ 변동성 하단 방어선")
            fig3 = px.line(df_tail, y=['Close', 'Macro_Pred'], color_discrete_map={'Close': 'white', 'Macro_Pred': '#EF553B'})
            fig3.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig3.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig3, use_container_width=True)
            pred3 = int(df_tail['Macro_Pred'].iloc[-1])
            st.info(f"💡 **거시 관점:** 시장이 흔들릴 때 버텨주어야 하는 최후 지지선은 **{pred3:,}원**입니다.")

        st.divider()

        # 3. 최종 통합 목표가 그래프
        st.subheader("🚀 AI 최종 통합 예측가 추이 (Final Synthesis)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="실제 주가", line=dict(color="white", width=3)))
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Final_Pred_Price'], name="AI 통합 예측가", line=dict(color="#FFA15A", width=2, dash='dot')))
        
        # 상승/하락 예측 구간 배경색 칠하기
        final_fig.add_bar(x=res['data'].index, y=np.where(res['data']['Final_Pred_Price'] > res['data']['Close'], res['data']['Final_Pred_Price'] - res['data']['Close'], 0),
                          base=res['data']['Close'], name="상승 예측 폭", marker_color='rgba(0, 204, 150, 0.3)')
                          
        final_fig.update_yaxes(title="가격 (원)", tickformat=",.0f")
        final_fig.update_layout(template="plotly_dark", height=500)
        st.plotly_chart(final_fig, use_container_width=True)
        st.success(f"최종 분석 결과: AI는 내일 주가가 **{current_price:,}원**에서 **{predicted_price:,}원**으로 {'상승' if predicted_price > current_price else '하락'}할 것으로 예측합니다.")

with tabs[0]: 
    st.subheader("🚥 실시간 AI 최종 목표가 브리핑")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            cur = r['price']
            pred = int(r['data']['Final_Pred_Price'].iloc[-1])
            cols[j].markdown(f"#### {n}")
            if pred > cur: cols[j].success(f"🟢 상승 예측\n\n목표가: {pred:,}원")
            else: cols[j].error(f"🔴 하락/조정 예상\n\n방어선: {pred:,}원")
