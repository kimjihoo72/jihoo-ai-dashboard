import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V5.0", layout="wide")
st.title("🛡️ AI 1주일 뒤 목표가 예측 시스템 V5.0")
st.markdown("### 📅 7일 뒤 시나리오 분석: 패턴·감성·변동성 통합 예측")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

EXCHANGE_RATE = 1350 # 엔비디아 원화 변환용

def run_v5_engine(symbol):
    df = yf.Ticker(symbol).history(period='1y')
    df = df.dropna(subset=['Close'])
    if df.empty or len(df) < 60: return None
    df = df.copy()

    if symbol == "NVDA":
        df['Close'] = df['Close'] * EXCHANGE_RATE

    # --- [1요소] 패턴인식: 1주일 뒤 예측가 (20일 선 기준 추세 확장) ---
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    # 7일 뒤의 추세를 반영하기 위해 가중치 조정
    df['Pattern_Pred'] = df['Close'] + (df['Close'] - df['SMA20']) * 0.6
    
    # --- [2요소] 감성투자: 1주일 뒤 예측가 (7일 모멘텀 가속도) ---
    # 1주일(주식 시장 기준 5~7영업일)간의 매수 심리가 다음 주까지 이어질 때의 가격
    df['Momentum_7d'] = df['Close'].pct_change(7)
    df['Sent_Pred'] = df['Close'] * (1 + df['Momentum_7d'])
    
    # --- [3요소] 변동성 방어: 1주일 뒤 하단 방어선 (주간 변동성 위험 반영) ---
    # 7일간 누적될 수 있는 최대 변동성 리스크 범위를 하단 지지선으로 계산
    df['Volat'] = df['Close'].pct_change().rolling(10).std()
    df['Macro_Pred'] = df['Close'] * (1 - (df['Volat'] * np.sqrt(7))) 

    # --- [최종] AI 1주일 뒤 통합 예측가 (가중 평균) ---
    df['Final_Pred_Price'] = (df['Pattern_Pred'] * 0.4) + (df['Sent_Pred'] * 0.3) + (df['Macro_Pred'] * 0.3)
    
    # [타율 채점 기준 수정] 오늘 주가 대비 '7일 뒤 주가'가 오를 것으로 예측했고, 실제로 7일 뒤 올랐다면 Hit!
    df['Next_Target'] = np.where(df['Close'].shift(-7) > df['Close'], 1, 0)
    df['AI_Decision'] = np.where(df['Final_Pred_Price'] > df['Close'], 1, 0)
    df['Match'] = np.where(df['AI_Decision'] == df['Next_Target'], 'Hit', 'Miss')
    
    df_clean = df.dropna(subset=['SMA20', 'Volat']).copy()
    df_hit = df_clean.dropna(subset=['Next_Target']).copy()
    hit_rate = round((len(df_hit[df_hit['Match'] == 'Hit']) / len(df_hit)) * 100, 1) if not df_hit.empty else 0.0
    
    return {'data': df_clean, 'hit_rate': hit_rate, 'price': int(df_clean['Close'].iloc[-1])}

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v2_engine(sym) if 'run_v2_engine' in globals() else run_v5_engine(sym) for name, sym in stocks.items()}
res_dict = {name: run_v5_engine(sym) for name, sym in stocks.items()} # 확실하게 오버라이딩

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} AI 1주일 뒤 가격 예측 리포트")
        
        c1, c2, c3 = st.columns(3)
        current_price = res['price']
        predicted_price = int(res['data']['Final_Pred_Price'].iloc[-1])
        
        c1.metric("현재 주가", f"{current_price:,} 원")
        c2.metric("🎯 AI 1주일 뒤 통합 예측가", f"{predicted_price:,} 원", f"{predicted_price - current_price:,} 원")
        c3.metric("🔥 1주일 예측 알고리즘 타율", f"{res['hit_rate']}%")
        st.divider()

        col_a, col_b, col_c = st.columns(3)
        df_tail = res['data'].tail(60)

        with col_a:
            st.subheader("1️⃣ 패턴인식 (1주일 추세)")
            fig1 = px.line(df_tail, y=['Close', 'Pattern_Pred'], color_discrete_map={'Close': 'white', 'Pattern_Pred': '#deff9a'})
            fig1.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig1.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig1, use_container_width=True)
            st.info(f"💡 **패턴 관점:** 다음 주 이 시간쯤 추세 확장선 상의 예상 가격은 **{int(df_tail['Pattern_Pred'].iloc[-1]):,}원**입니다.")

        with col_b:
            st.subheader("2️⃣ 감성투자 (주간 심리 모멘텀)")
            fig2 = px.line(df_tail, y=['Close', 'Sent_Pred'], color_discrete_map={'Close': 'white', 'Sent_Pred': '#00CC96'})
            fig2.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig2.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig2, use_container_width=True)
            st.info(f"💡 **심리 관점:** 현재의 시장 과열/랭각 심리가 주간 지속될 때 목표가는 **{int(df_tail['Sent_Pred'].iloc[-1]):,}원**입니다.")

        with col_c:
            st.subheader("3️⃣ 변동성 방어 (주간 최저 방어선)")
            fig3 = px.line(df_tail, y=['Close', 'Macro_Pred'], color_discrete_map={'Close': 'white', 'Macro_Pred': '#EF553B'})
            fig3.update_yaxes(title="가격 (원)", tickformat=",.0f")
            fig3.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0), height=300)
            st.plotly_chart(fig3, use_container_width=True)
            st.info(f"💡 **거시 관점:** 이번 주 시장 충격을 감안한 1주일 뒤 최후 보루 방어선은 **{int(df_tail['Macro_Pred'].iloc[-1]):,}원**입니다.")

        st.divider()

        st.subheader("🚀 1주일 뒤 AI 최종 통합 예측가 추이 (Final Synthesis)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Close'], name="실제 주가", line=dict(color="white", width=3)))
        final_fig.add_trace(go.Scatter(x=res['data'].index, y=res['data']['Final_Pred_Price'], name="AI 1주일 뒤 예측가", line=dict(color="#FFA15A", width=2, dash='dot')))
        
        final_fig.add_bar(x=res['data'].index, y=np.where(res['data']['Final_Pred_Price'] > res['data']['Close'], res['data']['Final_Pred_Price'] - res['data']['Close'], 0),
                          base=res['data']['Close'], name="1주일 뒤 상승 예측폭", marker_color='rgba(0, 204, 150, 0.3)')
                          
        final_fig.update_yaxes(title="가격 (원)", tickformat=",.0f")
        final_fig.update_layout(template="plotly_dark", height=500)
        st.plotly_chart(final_fig, use_container_width=True)
        st.success(f"최종 분석 결과: AI는 1주일 뒤 주가가 현재 대비 **{abs(predicted_price - current_price):,}원** {'상승할 것' if predicted_price > current_price else '조정받을 것'}으로 전망합니다.")

with tabs[0]: 
    st.subheader("🚥 실시간 1주일 뒤 AI 최종 목표가 브리핑")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            cur = r['price']
            pred = int(r['data']['Final_Pred_Price'].iloc[-1])
            cols[j].markdown(f"#### {n}")
            if pred > cur: cols[j].success(f"🟢 1주일 뒤 상승 우세\n\n목표가: {pred:,}원")
            else: cols[j].error(f"🔴 1주일 뒤 리스크 감지\n\n방어선: {pred:,}원")
