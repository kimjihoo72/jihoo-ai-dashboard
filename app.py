import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="지후의 AI 관제 V5.8", layout="wide")
st.title("🛡️ AI 1주일 뒤 목표가 예측 시스템 V5.8")
st.markdown("### 📅 이번주 실거래 및 다음주 예측 타임라인 (주말/공휴일 공백 제거)")

# 탭 구성
tabs = st.tabs(["🏠 종합 관제실", "🐻 SK하이닉스", "⚡ 삼성전자", "🟢 엔비디아", "🟡 카카오"])

EXCHANGE_RATE = 1350 # 엔비디아 원화 변환용

def run_v58_engine(symbol):
    try:
        # 보조지표 계산을 위해 1년치 넉넉하게 추출
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

    # 엔비디아인 경우 환율 보정 반영
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

    # --- [핵심] 5월 18일 주간 실제 데이터만 필터링 ---
    this_week_df = df[(df.index >= '2026-05-18') & (df.index <= '2026-05-22')].copy()
    if this_week_df.empty:
        this_week_df = df.tail(5).copy() # 예외 방어

    # 날짜를 문자열 포맷으로 추출 (주말 자동 생성을 막기 위함)
    this_week_dates = [d.strftime('%m-%d') for d in this_week_df.index]
    
    # 다음주 영업일 고정 명단 (주말 제외 5일)
    next_week_dates = ['05-25', '05-26', '05-27', '05-28', '05-29']
    
    # 전체 X축 결합 (순수 10 영업일 카테고리 매핑)
    all_dates = this_week_dates + next_week_dates

    # 선 연결의 시작점이 될 이번주 금요일 정보
    last_date_str = this_week_dates[-1]
    current_price = this_week_df['Close'].iloc[-1]
    
    # 예측선 작성을 위한 X축 경로 (이번주 금요일부터 시작해서 다음주 전체를 커버)
    pred_x = [last_date_str] + next_week_dates

    return {
        'this_week_df': this_week_df,
        'this_week_dates': this_week_dates,
        'next_week_dates': next_week_dates,
        'all_dates': all_dates,
        'pred_x': pred_x,
        'hit_rate': hit_rate,
        'price': int(current_price),
        'pred_price': int(df['Final_Pred_Price'].iloc[-1]),
        'p_pred': int(df['Pattern_Pred'].iloc[-1]),
        's_pred': int(df['Sent_Pred'].iloc[-1]),
        'm_pred': int(df['Macro_Pred'].iloc[-1])
    }

stocks = {"SK하이닉스": "000660.KS", "삼성전자": "005930.KS", "엔비디아": "NVDA", "카카오": "035720.KS"}
res_dict = {name: run_v58_engine(sym) for name, sym in stocks.items()}

# --- 화면 출력부 ---
for i, (name, res) in enumerate(res_dict.items()):
    if not res: continue
    with tabs[i+1]:
        st.header(f"📈 {name} 이번주 분석 및 다음주 예측 타임라인")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("이번주 종가", f"{res['price']:,} 원")
        c2.metric("🎯 다음주 최종 목표가 (05-29)", f"{res['pred_price']:,} 원", f"{res['pred_price'] - res['price']:,} 원")
        c3.metric("🔥 7일 예측 알고리즘 타율", f"{res['hit_rate']}%")
        st.divider()

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.subheader("1️⃣ 패턴인식 예측 타임라인")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=res['this_week_dates'], y=res['this_week_df']['Close'], name="실제 주가", line=dict(color="white", width=2.5)))
            pred_y_p = np.linspace(res['price'], res['p_pred'], 6)
            fig1.add_trace(go.Scatter(x=res['pred_x'], y=pred_y_p, name="예측 연장선", line=dict(color="#deff9a", width=2, dash="dash")))
            
            fig1.update_xaxes(type='category', categoryorder='array', categoryarray=res['all_dates'])
            fig1.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig1, use_container_width=True)
            st.info(f"💡 **패턴 예측:** 다음주 금요일 **{res['p_pred']:,}원** 목표")

        with col_b:
            st.subheader("2️⃣ 감성투자 예측 타임라인")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=res['this_week_dates'], y=res['this_week_df']['Close'], name="실제 주가", line=dict(color="white", width=2.5)))
            pred_y_s = np.linspace(res['price'], res['s_pred'], 6)
            fig2.add_trace(go.Scatter(x=res['pred_x'], y=pred_y_s, name="예측 연장선", line=dict(color="#00CC96", width=2, dash="dash")))
            
            fig2.update_xaxes(type='category', categoryorder='array', categoryarray=res['all_dates'])
            fig2.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig2, use_container_width=True)
            st.info(f"💡 **심리 예측:** 다음주 금요일 **{res['s_pred']:,}원** 목표")

        with col_c:
            st.subheader("3️⃣ 변동성 방어 예측 타임라인")
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(x=res['this_week_dates'], y=res['this_week_df']['Close'], name="실제 주가", line=dict(color="white", width=2.5)))
            pred_y_m = np.linspace(res['price'], res['m_pred'], 6)
            fig3.add_trace(go.Scatter(x=res['pred_x'], y=pred_y_m, name="방어 연장선", line=dict(color="#EF553B", width=2, dash="dash")))
            
            fig3.update_xaxes(type='category', categoryorder='array', categoryarray=res['all_dates'])
            fig3.update_layout(template="plotly_dark", showlegend=False, height=280, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig3, use_container_width=True)
            st.info(f"💡 **거시 방어:** 다음주 금요일 최저 **{res['m_pred']:,}원** 지지")

        st.divider()

        st.subheader("🚀 AI 최종 통합 시나리오 타임라인 (5/18 ~ 5/29)")
        final_fig = go.Figure()
        final_fig.add_trace(go.Scatter(x=res['this_week_dates'], y=res['this_week_df']['Close'], name="실제 주가 역사", line=dict(color="white", width=3.5)))
        
        pred_y_f = np.linspace(res['price'], res['pred_price'], 6)
        final_fig.add_trace(go.Scatter(x=res['pred_x'], y=pred_y_f, name="AI 최종 시나리오", line=dict(color="#FFA15A", width=3, dash='dot')))
        
        # 다음주 금요일 최종 목표 지점에 앵커 핀 설정
        final_fig.add_trace(go.Scatter(
            x=[res['next_week_dates'][-1]], 
            y=[res['pred_price']], 
            mode='markers+text',
            name='최종 목표가',
            text=[f"  {res['pred_price']:,}원 마감 예정"],
            textposition="top center",
            marker=dict(color='#FFA15A', size=12, symbol='star')
        ))
                          
        final_fig.update_xaxes(type='category', categoryorder='array', categoryarray=res['all_dates'])
        final_fig.update_yaxes(title="가격 (원)", tickformat=",.0f")
        final_fig.update_layout(template="plotly_dark", height=450)
        st.plotly_chart(final_fig, use_container_width=True)

with tabs[0]: 
    st.subheader("🚥 실시간 다음주 금요일(05-29) AI 최종 목표가 브리핑")
    cols = st.columns(4)
    for j, (n, r) in enumerate(res_dict.items()):
        if r:
            cols[j].markdown(f"#### {n}")
            if r['pred_price'] > r['price']: 
                cols[j].success(f"🟢 다음주 상승 전망\n\n목표가: {r['pred_price']:,}원")
            else: 
                cols[j].error(f"🔴 다음주 조정 리스크\n\n방어선: {r['pred_price']:,}원")
