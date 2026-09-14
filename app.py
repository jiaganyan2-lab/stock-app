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
    ("美股動向與國際局勢 (台股風向球)", "台股三大法人資金流向與推斷", "個股技術面與籌碼綜合診斷")
)

# 【快取機制】台股法人資料
@st.cache_data(ttl=3600)
def fetch_twse_data():
    url = "https://www.twse.com.tw/fund/T86?response=json"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

# 【新增快取機制】美股關鍵指標與新聞
@st.cache_data(ttl=900) # 每15分鐘更新一次
def fetch_us_macro():
    tickers_list = ["TSM", "NVDA", "AAPL", "AMD", "SOXX"]
    results = {}
    sentiment_score = 0 # 用來計算國際局勢氣氛
    
    try:
        df = yf.download(tickers_list, period="5d")
        for t in tickers_list:
            # 處理 yfinance 雙層欄位格式
            if isinstance(df.columns, pd.MultiIndex):
                prev_close = df['Close'][t].iloc[-2]
                curr_close = df['Close'][t].iloc[-1]
            else:
                prev_close = df['Close'].iloc[-2]
                curr_close = df['Close'].iloc[-1]
                
            pct_change = ((curr_close - prev_close) / prev_close) * 100
            results[t] = {"price": curr_close, "pct": pct_change}
            
            # 台積電ADR、輝達、半導體ETF 對台股影響最大，加總計算氣氛
            if t in ["TSM", "NVDA", "SOXX"]:
                sentiment_score += pct_change
    except Exception:
        pass
        
    news = []
    try:
        # 抓取 SPY (標普500) 的最新市場新聞
        spy = yf.Ticker("SPY")
        raw_news = spy.news
        for n in raw_news[:5]:
            news.append({"title": n['title'], "link": n['link']})
    except:
        pass
        
    return results, news, sentiment_score

# ==========================================
# 功能一：美股動向與國際局勢 (台股風向球)
# ==========================================
if option == "美股動向與國際局勢 (台股風向球)":
    st.header("🌎 國際局勢與關鍵美股 (台股風向球)")
    st.write("直接列出最影響台股表現的美股科技巨頭與半導體指標。")
    
    with st.spinner('連線華爾街抓取最新報價與新聞...'):
        us_data, us_news, global_sentiment = fetch_us_macro()
        
        if us_data:
            # 使用 st.metric 建立漂亮的即時數據儀表板
            cols = st.columns(5)
            labels = {"TSM": "台積電 ADR", "NVDA": "輝達 (NVIDIA)", "AAPL": "蘋果 (Apple)", "AMD": "超微 (AMD)", "SOXX": "半導體 ETF"}
            
            for i, (ticker, info) in enumerate(us_data.items()):
                with cols[i]:
                    st.metric(label=labels[ticker], 
                              value=f"${info['price']:.2f}", 
                              delta=f"{info['pct']:.2f}%")
            
            st.markdown("---")
            
            # 國際局勢新聞區
            st.subheader("📰 國際金融大事件與頭條")
            if us_news:
                for n in us_news:
                    st.markdown(f"🔹 [{n['title']}]({n['link']})")
            else:
                st.write("目前無最新重大新聞。")
                
            st.markdown("---")
            
            # 保留 K 線圖功能，改用下拉選單讓使用者切換查看
            st.subheader("📊 關鍵指標 K 線圖")
            selected_ticker = st.selectbox("選擇要查看技術線圖的指標", ["TSM", "NVDA", "AAPL", "AMD", "SOXX"])
            
            data = yf.download(selected_ticker, period="6mo")
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

                fig.update_layout(title=f"{selected_ticker} ({labels[selected_ticker]}) 歷史 K 線圖", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

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
                st.warning("⚠️ 目前無資料。可能是假日、盤後資料尚未更新，或者是「雲端主機 IP」被證交所暫時限制連線。")

# ==========================================
# 功能三：個股技術面與籌碼綜合診斷
# ==========================================
elif option == "個股技術面與籌碼綜合診斷":
    st.header("🎯 個股技術面、籌碼與量能綜合診斷")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        stock_id = st.text_input("輸入台股代號 (如: 2409, 3041, 6233)", "2409").strip()
        analyze_btn = st.button("開始綜合診斷")
    
    if analyze_btn:
        with st.spinner("計算技術指標、量能與比對國際局勢中..."):
            
            # 【新增】抓取國際局勢氣氛
            _, _, global_sentiment = fetch_us_macro()
            
            yf_ticker = f"{stock_id}.TW"
            df = yf.download(yf_ticker, period="6mo")
            
            if df.empty:
                yf_ticker = f"{stock_id}.TWO" 
                df = yf.download(yf_ticker, period="6mo")

            if df.empty:
                st.error(f"找不到代號 {stock_id} 的股價資料，請確認是否輸入正確。")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df['Volume'] = df['Volume'].fillna(0)
                stock_name = stock_id
                foreign_buy, trust_buy, dealer_buy = 0, 0, 0
                has_t86_data = False
                
                t86_data = fetch_twse_data()
                if t86_data and t86_data.get('stat') == 'OK' and 'fields' in t86_data:
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

                df['5MA'] = df['Close'].rolling(window=5).mean()
                df['20MA'] = df['Close'].rolling(window=20).mean()
                df['60MA'] = df['Close'].rolling(window=60).mean()
                
                df['Pre_Close'] = df['Close'].shift(1)
                df['Amplitude'] = ((df['High'] - df['Low']) / df['Pre_Close']) * 100
                
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
                                    subplot_titles=(f"{stock_id} {stock_name} - 股價與均線系統", "成交量 (Volume)", "MACD", "KD", "RSI"))
                
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                                             name='K線', increasing_line_color='red', increasing_fillcolor='red',
                                             decreasing_line_color='green', decreasing_fillcolor='green'), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['5MA'], line=dict(color='fuchsia', width=1), name='5MA (週線)'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['20MA'], line=dict(color='orange', width=2), name='20MA (月線)'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['60MA'], line=dict(color='blue', width=2, dash='dash'), name='60MA (季線)'), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(169, 169, 169, 0.5)', width=1), name='布林上軌'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(169, 169, 169, 0.5)', width=1), name='布林下軌'), row=1, col=1)
                
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
                
                # 【新增】國際局勢大環境判斷
                if global_sentiment > 1.5:
                    bullish_reasons.append("🌎 國際局勢：美股半導體與科技巨頭表現強勢，【大環境順風】，有利台股上漲。")
                    score += 1
                elif global_sentiment < -1.5:
                    bearish_reasons.append("🌎 國際局勢：美股半導體與科技巨頭表現弱勢，【大環境逆風】，容易拖累台股表現。")
                    score -= 1
                
                if has_t86_data:
                    if foreign_buy > 0 and trust_buy > 0:
                        bullish_reasons.append(f"大戶動向：外資與投信【同步大買】 (外資 {foreign_buy:.0f}張, 投信 {trust_buy:.0f}張)。")
                        score += 2
                    elif foreign_buy < 0 and trust_buy < 0:
                        bearish_reasons.append(f"大戶動向：外資與投信【同步大賣】 (外資 {foreign_buy:.0f}張, 投信 {trust_buy:.0f}張)。")
                        score -= 2
                    elif trust_buy > 0:
                        bullish_reasons.append(f"大戶動向：投信【買進護盤】 ({trust_buy:.0f}張)。")
                        score += 1
                    elif foreign_buy < 0:
                        bearish_reasons.append(f"大戶動向：外資【賣出提款】 ({foreign_buy:.0f}張)。")
                        score -= 1
                else:
                    bullish_reasons.append("大戶動向：今日無明顯進出，或遭雲端阻擋 (若為上櫃股票請參考櫃買中心)。")

                amp = latest['Amplitude']
                if pd.notna(amp):
                    if amp >= 4.0:
                        bullish_reasons.append(f"⚡ 短線動能：今日振幅達 {amp:.1f}%，【波動活躍】，極適合現沖或當沖操作。")
                        score += 1
                    elif amp < 2.0:
                        bearish_reasons.append(f"💤 短線動能：今日振幅僅 {amp:.1f}%，【股價沉悶】，短線操作獲利空間較小。")

                if latest['Volume'] > latest['Vol_5MA'] * 1.5 and latest['Close'] > latest['Open']:
                    bullish_reasons.append("成交量：今日【出量上漲】 (比平常多1.5倍)，市場搶買意願高。")
                    score += 1
                elif latest['Volume'] > latest['Vol_5MA'] * 1.5 and latest['Close'] < latest['Open']:
                    bearish_reasons.append("成交量：今日【出量下跌】 (比平常多1.5倍)，賣壓沉重。")
                    score -= 1

                if latest['Close'] > latest['20MA'] and latest['Close'] > latest['60MA']:
                    bullish_reasons.append("均線趨勢：股價站上月線與季線，屬於強勢【多頭格局】。")
                    score += 1
                elif latest['Close'] < latest['20MA'] and latest['Close'] < latest['60MA']:
                    bearish_reasons.append("均線趨勢：股價跌破月線與季線，【趨勢轉弱】，需留意做空或借券賣出之壓力。")
                    score -= 1

                if latest['MACD_Hist'] > 0 and df.iloc[-2]['MACD_Hist'] <= 0:
                    bullish_reasons.append("MACD指標：出現【黃金交叉】，是剛開始起漲的訊號。")
                    score += 2
                elif latest['MACD_Hist'] > 0:
                    bullish_reasons.append("MACD指標：維持【上漲趨勢】。")
                    score += 1
                elif latest['MACD_Hist'] < 0 and df.iloc[-2]['MACD_Hist'] >= 0:
                    bearish_reasons.append("MACD指標：出現【死亡交叉】，是剛開始起跌的訊號。")
                    score -= 2
                else:
                    bearish_reasons.append("MACD指標：維持【下跌趨勢】。")
                    score -= 1

                if latest['K'] > latest['D']:
                    bullish_reasons.append("KD指標：K值大於D值，【短期動能向上】。")
                    score += 1
                else:
                    bearish_reasons.append("KD指標：K值小於D值，【短期動能向下】。")
                    score -= 1

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.success("🟢 看漲訊號 (有利上漲)\n\n" + "\n\n".join([f"- {r}" for r in bullish_reasons]) if bullish_reasons else "無明顯看漲訊號")
                with col_res2:
                    st.error("🔴 看跌訊號 (容易下跌)\n\n" + "\n\n".join([f"- {r}" for r in bearish_reasons]) if bearish_reasons else "無明顯看跌訊號")

                st.markdown("### 📊 最終推斷結論")
                if score >= 4:
                    st.info("**⭐ 適合尋找買點 (強勢看漲)**：大環境順風、技術面與大戶動向皆強，可考慮順勢進場買進。")
                elif 0 <= score < 4:
                    st.warning("**👀 建議暫時觀望 (持平整理)**：多空訊號分歧，未見明顯表態。建議利用布林通道上下軌做區間操作，或等待帶量突破。")
                else:
                    st.error("**⚠️ 建議避開或逢高賣出 (弱勢看跌)**：大環境不佳且各項指標轉弱，籌碼渙散。若手上有持股建議減碼；空手者可觀察跌破支撐後的放空機會。")
