import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

# --- 頁面設定 ---
st.set_page_config(page_title="全球股市與籌碼推斷系統", layout="wide")
st.title("📈 股市資金流向與策略推斷系統")

option = st.sidebar.selectbox(
    "請選擇功能",
    ("美股動向與 K 線分析", "台股三大法人資金流向與推斷", "個股技術面與籌碼綜合診斷")
)

# 【快取機制】每天只抓一次資料，避免被證交所封鎖
@st.cache_data(ttl=3600)
def fetch_twse_data():
    url = "https://www.twse.com.tw/fund/T86?response=json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

# ==========================================
# 功能一：美股動向與 K 線分析
# ==========================================
if option == "美股動向與 K 線分析":
    st.header("🇺🇸 美股動向與 K 線分析")
    ticker = st.text_input("請輸入美股代號 (例如: AAPL, TSLA, NVDA)", "NVDA")
    
    if st.button("載入資料"):
        with st.spinner('抓取資料中...'):
            data = yf.download(ticker, period="6mo")
            if not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                    
                fig = go.Figure(data=[go.Candlestick(x=data.index,
                                open=data['Open'], high=data['High'],
                                low=data['Low'], close=data['Close'], name="K線",
                                increasing_line_color='red', increasing_fillcolor='red',
                                decreasing_line_color='green', decreasing_fillcolor='green')])
                
                latest_price = data['Close'].iloc[-1]
                fig.add_annotation(x=data.index[-1], y=latest_price,
                                   text=f"<b>${latest_price:.2f}</b>",
                                   showarrow=True, arrowhead=1, ax=40, ay=0,
                                   bgcolor="yellow", font=dict(color="black", size=12))

                fig.update_layout(title=f"{ticker} 歷史 K 線圖", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
                recent_close = data['Close'].iloc[-1]
                ma_20 = data['Close'].rolling(window=20).mean().iloc[-1]
                
                st.subheader("💡 系統推斷 (基於技術面)")
                if recent_close > ma_20:
                    st.success(f"**強勢格局**：{ticker} 目前收盤價高於 20 日均線，短期動能偏多。")
                else:
                    st.warning(f"**弱勢整理**：{ticker} 目前收盤價低於 20 日均線，短期動能偏弱。")
            else:
                st.error("找不到該股票代號的資料。")

# ==========================================
# 功能二：台股三大法人資金流向與推斷
# ==========================================
elif option == "台股三大法人資金流向與推斷":
    st.header("🇹🇼 台股三大法人資金流向與推斷")
    st.write("自動抓取台灣證券交易所（TWSE）最新公告的三大法人買賣超資料。")
    
    if st.button("獲取最新法人動向"):
        with st.spinner('從資料庫抓取最新法人動向中...'):
            data = fetch_twse_data()
            
            if data and data.get('stat') == 'OK' and 'fields' in data and 'data' in data:
                fields = data['fields']
                raw_data = data['data']
                
                idx_code = next((i for i, f in enumerate(fields) if "代號" in f), 0)
                idx_name = next((i for i, f in enumerate(fields) if "名稱" in f), 1)
                idx_foreign = next((i for i, f in enumerate(fields) if "外資及陸資買賣超" in f or ("外" in f and "買賣超" in f and "自營" not in f)), -1)
                idx_trust = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), -1)
                idx_dealer = next((i for i, f in enumerate(fields) if "自營商買賣超" in f and "外資" not in f), -1)
                
                if -1 in [idx_foreign, idx_trust, idx_dealer]:
                    st.error("證交所的資料欄位名稱有變動，系統無法自動對應。")
                else:
                    df = pd.DataFrame(raw_data)
                    df_clean = pd.DataFrame({
                        '股票代號': df[idx_code].astype(str),
                        '股票名稱': df[idx_name].astype(str),
                        '外資買賣超(張)': pd.to_numeric(df[idx_foreign].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000,
                        '投信買賣超(張)': pd.to_numeric(df[idx_trust].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000,
                        '自營商買賣超(張)': pd.to_numeric(df[idx_dealer].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000
                    })
                    df_clean['三大法人合計(張)'] = df_clean['外資買賣超(張)'] + df_clean['投信買賣超(張)'] + df_clean['自營商買賣超(張)']
                    df_filtered = df_clean.sort_values(by='三大法人合計(張)', ascending=False).head(15)
                    
                    st.dataframe(df_filtered.style.format({
                        '外資買賣超(張)': '{:,.0f}', '投信買賣超(張)': '{:,.0f}',
                        '自營商買賣超(張)': '{:,.0f}', '三大法人合計(張)': '{:,.0f}'
                    }), use_container_width=True)
            else:
                st.error("目前無資料，可能是假日、盤後資料尚未更新，或已被證交所暫時限制連線。")

# ==========================================
# 功能三：個股技術面與籌碼綜合診斷
# ==========================================
elif option == "個股技術面與籌碼綜合診斷":
    st.header("🎯 個股技術面、籌碼與量能綜合診斷")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        stock_id = st.text_input("輸入台股代號 (如: 2330)", "2330")
        analyze_btn = st.button("開始綜合診斷")
    
    if analyze_btn:
        with st.spinner("計算技術指標、量能與比對籌碼中..."):
            yf_ticker = f"{stock_id}.TW"
            df = yf.download(yf_ticker, period="6mo")
            
            # 如果 .TW 找不到，試著找找看 .TWO (上櫃)
            if df.empty:
                yf_ticker = f"{stock_id}.TWO"
                df = yf.download(yf_ticker, period="6mo")

            if df.empty:
                st.error(f"找不到代號 {stock_id} 的股價資料，請確認是否輸入正確。")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                stock_name = stock_id
                foreign_buy, trust_buy, dealer_buy = 0, 0, 0
                has_t86_data = False
                
                t86_data = fetch_twse_data()
                if t86_data and t86_data.get('stat') == 'OK' and 'fields' in t86_data:
                    # 【修正處】這裡加入了防呆機制 (-1)，找不到就不會當機
                    f_idx = next((i for i, f in enumerate(t86_data['fields']) if "代號" in f), -1)
                    n_idx = next((i for i, f in enumerate(t86_data['fields']) if "名稱" in f), -1)
                    idx_f = next((i for i, f in enumerate(t86_data['fields']) if "外資及陸資買賣超" in f or ("外" in f and "買賣超" in f and "自營" not in f)), -1)
                    idx_t = next((i for i, f in enumerate(t86_data['fields']) if "投信" in f and "買賣超" in f), -1)
                    
                    if -1 not in [f_idx, n_idx, idx_f, idx_t]:
                        for row in t86_data['data']:
                            if row[f_idx] == stock_id:
                                stock_name = row[n_idx]
                                foreign_buy = float(row[idx_f].replace(',', '')) / 1000
                                trust_buy = float(row[idx_t].replace(',', '')) / 1000
                                has_t86_data = True
                                break
                
                if stock_name == stock_id:
                    try:
                        info = yf.Ticker(yf_ticker).info
                        stock_name = info.get('shortName', stock_id)
                    except:
                        pass

                df['20MA'] = df['Close'].rolling(window=20).mean()
                df['STD'] = df['Close'].rolling(window=20).std()
                df['BB_Upper'] = df['20MA'] + (2 * df['STD'])
                df['BB_Lower'] = df['20MA'] - (2 * df['STD'])
                df['Vol_5MA'] = df['Volume'].rolling(window=5).mean()
                
                exp1 = df['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = exp1 - exp2
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                df['MACD_Hist'] = df['MACD'] - df['Signal']
                
                delta = df['Close'].diff()
                gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
                loss = (-1 * delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))
                
                low_9 = df['Low'].rolling(window=9).min()
                high_9 = df['High'].rolling(window=9).max()
                df['RSV'] = 100 * (df['Close'] - low_9) / (high_9 - low_9)
                df['K'] = df['RSV'].ewm(com=2, adjust=False).mean()
                df['D'] = df['K'].ewm(com=2, adjust=False).mean()

                fig = make_subplots(rows=5, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.02, row_heights=[0.4, 0.15, 0.15, 0.15, 0.15],
                                    subplot_titles=(f"{stock_id} {stock_name} - 股價與布林通道", "成交量 (Volume)", "MACD", "KD", "RSI"))
                
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                                             name='K線', increasing_line_color='red', increasing_fillcolor='red',
                                             decreasing_line_color='green', decreasing_fillcolor='green'), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(255, 0, 0, 0.3)'), name='上軌'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['20MA'], line=dict(color='orange', dash='dash'), name='月線(20MA)'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(0, 255, 0, 0.3)'), name='下軌'), row=1, col=1)
                
                latest_close = df['Close'].iloc[-1]
                fig.add_annotation(x=df.index[-1], y=latest_close,
                                   text=f"<b>{latest_close:.2f}</b>",
                                   showarrow=True, arrowhead=2, ax=40, ay=0,
                                   bgcolor="gold", font=dict(color="black", size=13), row=1, col=1)
                
                vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Vol_5MA'], line=dict(color='blue'), name='5日均量'), row=2, col=1)
                
                macd_colors = ['red' if val >= 0 else 'green' for val in df['MACD_Hist']]
                fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=macd_colors, name='MACD 柱狀圖'), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue'), name='MACD'), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange'), name='Signal'), row=3, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='blue'), name='K值'), row=4, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='orange'), name='D值'), row=4, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=5, col=1)
                fig.add_hline(y=70, line_dash="dot", row=5, col=1, annotation_text="過熱(70)", annotation_position="bottom right")
                fig.add_hline(y=30, line_dash="dot", row=5, col=1, annotation_text="超賣(30)", annotation_position="top right")

                fig.update_layout(height=1000, xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                st.subheader(f"🤖 {stock_id} {stock_name} - 綜合診斷報告")
                
                latest = df.iloc[-1]
                score = 0
                bullish_reasons = []
                bearish_reasons = []
                
                if has_t86_data:
                    if foreign_buy > 0 and trust_buy > 0:
                        bullish_reasons.append(f"籌碼：土洋同步買超 (外資 {foreign_buy:.0f}張, 投信 {trust_buy:.0f}張)。")
                        score += 2
                    elif foreign_buy < 0 and trust_buy < 0:
                        bearish_reasons.append(f"籌碼：土洋同步賣超 (外資 {foreign_buy:.0f}張, 投信 {trust_buy:.0f}張)。")
                        score -= 2
                    elif trust_buy > 0:
                        bullish_reasons.append(f"籌碼：投信買超護盤 ({trust_buy:.0f}張)。")
                        score += 1
                    elif foreign_buy < 0:
                        bearish_reasons.append(f"籌碼：外資提款賣超 ({foreign_buy:.0f}張)。")
                        score -= 1
                else:
                    bullish_reasons.append("籌碼：今日無上市法人明顯進出 (或該檔為上櫃股票)。")

                if latest['Volume'] > latest['Vol_5MA'] * 1.5 and latest['Close'] > latest['Open']:
                    bullish_reasons.append("量能：今日出量上漲 (大於5日均量1.5倍)，具攻擊企圖。")
                    score += 1
                elif latest['Volume'] > latest['Vol_5MA'] * 1.5 and latest['Close'] < latest['Open']:
                    bearish_reasons.append("量能：今日出量下跌 (大於5日均量1.5倍)，賣壓較重。")
                    score -= 1

                if latest['MACD_Hist'] > 0 and df.iloc[-2]['MACD_Hist'] <= 0:
                    bullish_reasons.append("MACD：柱狀圖翻紅，呈現黃金交叉。")
                    score += 2
                elif latest['MACD_Hist'] > 0:
                    bullish_reasons.append("MACD：維持多頭格局。")
                    score += 1
                elif latest['MACD_Hist'] < 0 and df.iloc[-2]['MACD_Hist'] >= 0:
                    bearish_reasons.append("MACD：柱狀圖翻綠，呈現死亡交叉。")
                    score -= 2
                else:
                    bearish_reasons.append("MACD：維持空頭格局。")
                    score -= 1

                if latest['K'] > latest['D']:
                    bullish_reasons.append("KD：K值大於D值，動能向上。")
                    score += 1
                else:
                    bearish_reasons.append("KD：K值小於D值，動能向下。")
                    score -= 1

                if latest['RSI'] > 70:
                    bearish_reasons.append(f"RSI：數值為 {latest['RSI']:.1f}，進入超買區，短線有回檔風險。")
                    score -= 1
                elif latest['RSI'] < 30:
                    bullish_reasons.append(f"RSI：數值為 {latest['RSI']:.1f}，進入超賣區，醞釀反彈契機。")
                    score += 1

                if latest['Close'] > latest['BB_Upper']:
                    bearish_reasons.append("布林：股價突破上軌，乖離過大易拉回。")
                    score -= 1
                elif latest['Close'] < latest['BB_Lower']:
                    bullish_reasons.append("布林：股價跌破下軌，可能出現跌深反彈。")
                    score += 1

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.success("🟢 偏多訊號\n\n" + "\n\n".join([f"- {r}" for r in bullish_reasons]) if bullish_reasons else "無明顯偏多訊號")
                with col_res2:
                    st.error("🔴 偏空訊號\n\n" + "\n\n".join([f"- {r}" for r in bearish_reasons]) if bearish_reasons else "無明顯偏空訊號")

                st.markdown("### 📊 最終推斷結論")
                if score >= 3:
                    st.info("**強烈建議偏多看待 (Buy)**：技術面與籌碼面產生共鳴，多方勝率較高，可尋找突破點進場。")
                elif 0 <= score < 3:
                    st.warning("**建議觀望或區間操作 (Hold)**：多空力道拉扯，無絕對方向，可利用布林通道上下軌做短線低買高賣。")
                else:
                    st.error("**建議偏空看待或避開 (Sell/Short)**：技術指標轉弱且法人未見支持，若持有多單建議分批減碼。")