import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import re # 新增正規表達式套件，用來解析網頁

# --- 頁面設定 ---
st.set_page_config(page_title="全球股市與籌碼推斷系統", layout="wide")
st.title("📈 股市資金流向與專業推斷系統")

if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = "3259, 6233, 3041, 8024, 5244, 2409, 2329, 2401, 8150"
if 'diag_ticker' not in st.session_state:
    st.session_state['diag_ticker'] = "3041"

option = st.sidebar.selectbox(
    "請選擇功能",
    (
        "1. 美股動向與國際局勢 (台股風向球)", 
        "2. 自選股雷達掃描 (現沖與波段尋寶)", 
        "3. 台股三大法人資金流向", 
        "4. 個股技術面與籌碼綜合診斷"
    )
)

# ================= 核心快取與工具函式 =================
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

@st.cache_data(ttl=900)
def fetch_us_macro():
    tickers_list = ["TSM", "NVDA", "AAPL", "AMD", "SOXX"]
    results = {}
    sentiment_score = 0
    try:
        for t in tickers_list:
            ticker = yf.Ticker(t)
            df = ticker.history(period="5d")
            if len(df) >= 2:
                prev_close = float(df['Close'].iloc[-2])
                curr_close = float(df['Close'].iloc[-1])
                pct_change = ((curr_close - prev_close) / prev_close) * 100
                results[t] = {"price": curr_close, "pct": pct_change}
                if t in ["TSM", "NVDA", "SOXX"]:
                    sentiment_score += pct_change
    except:
        pass
    return results, sentiment_score

@st.cache_data(ttl=600)
def get_stock_data(stock_id):
    t = yf.Ticker(f"{stock_id}.TW")
    df = t.history(period="6mo")
    if df.empty:
        t = yf.Ticker(f"{stock_id}.TWO")
        df = t.history(period="6mo")
    
    if not df.empty:
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.dropna(subset=['Close'], inplace=True)
        df['Volume'] = df['Volume'].fillna(0)
    return df

# 【全新加入】台灣 Yahoo 股市即時爬蟲引擎 (每 60 秒快取一次，保證盤中即時)
@st.cache_data(ttl=60)
def get_realtime_quote(stock_id):
    try:
        url = f"https://tw.stock.yahoo.com/quote/{stock_id}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        res = requests.get(url, headers=headers, timeout=3)
        # 爬取網頁標題中的即時價格，格式如: "旺玖 (6233) 30.50 漲幅 1.50% - Yahoo奇摩股市"
        match = re.search(rf'\({stock_id}\)\s+([0-9,.]+)\s+[^0-9+-]*([+-]?[0-9,.]+)%', res.text)
        if match:
            price = float(match.group(1).replace(',', ''))
            pct = float(match.group(2).replace(',', ''))
            return price, pct
    except:
        pass
    return None, None

# ==========================================
# 功能一：美股動向與國際局勢
# ==========================================
if option == "1. 美股動向與國際局勢 (台股風向球)":
    st.header("🌎 國際局勢與關鍵美股")
    with st.spinner('連線華爾街抓取最新報價...'):
        us_data, global_sentiment = fetch_us_macro()
        if us_data:
            cols = st.columns(5)
            labels = {"TSM": "台積電 ADR", "NVDA": "輝達 (NVIDIA)", "AAPL": "蘋果 (Apple)", "AMD": "超微 (AMD)", "SOXX": "半導體 ETF"}
            for i, (ticker, info) in enumerate(us_data.items()):
                with cols[i]:
                    st.metric(label=labels[ticker], value=f"${info['price']:.2f}", delta=f"{info['pct']:.2f}%")
            
            st.markdown("---")
            st.subheader("📊 關鍵指標 K 線圖")
            selected_ticker = st.selectbox("選擇要查看技術線圖的指標", ["TSM", "NVDA", "AAPL", "AMD", "SOXX"])
            
            t_chart = yf.Ticker(selected_ticker)
            data = t_chart.history(period="6mo")
            if not data.empty:
                if data.index.tz is not None:
                    data.index = data.index.tz_localize(None)
                data.dropna(subset=['Close'], inplace=True)
                
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
# 功能二：自選股雷達掃描
# ==========================================
elif option == "2. 自選股雷達掃描 (現沖與波段尋寶)":
    st.header("🎯 自選股雷達掃描 (盤中即時戰情室)")
    st.write("掃描預設口袋名單，結合 **Yahoo 奇摩股市即時報價**，找出今日波動最大的標的。")
    
    user_input = st.text_input("您可以修改或新增追蹤代號 (以逗號分隔)：", st.session_state['watchlist'])
    st.session_state['watchlist'] = user_input
    
    if st.button("啟動雷達掃描"):
        stocks = [s.strip() for s in user_input.split(',')]
        scan_results = []
        
        with st.spinner("啟動即時爬蟲，抓取最新股價中..."):
            for sid in stocks:
                df = get_stock_data(sid)
                if not df.empty and len(df) > 20:
                    prev = df.iloc[-2]
                    
                    # 啟動新引擎：嘗試抓取盤中即時報價
                    rt_price, rt_pct = get_realtime_quote(sid)
                    
                    # 如果成功抓到即時報價，就用即時的；如果抓不到(例如斷線)，就退回使用美國歷史庫的資料
                    if rt_price is not None and rt_pct is not None:
                        current_px = rt_price
                        pct_change = rt_pct
                        amplitude = ((df['High'].iloc[-1] - df['Low'].iloc[-1]) / prev['Close']) * 100 
                    else:
                        current_px = df['Close'].iloc[-1]
                        pct_change = ((current_px - prev['Close']) / prev['Close']) * 100
                        amplitude = ((df['High'].iloc[-1] - df['Low'].iloc[-1]) / prev['Close']) * 100
                    
                    if pd.isna(amplitude) or np.isinf(amplitude):
                        amplitude = 0.0
                        
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    vol_5ma = df['Volume'].rolling(5).mean().iloc[-1]
                    vol_ratio = (df['Volume'].iloc[-1] / vol_5ma) if (pd.notna(vol_5ma) and vol_5ma > 0) else 0.0
                    
                    trend = "🟢 偏多" if current_px > ma20 else "🔴 偏空"
                    day_trade = "🔥 極佳" if amplitude >= 4.0 and vol_ratio >= 1.2 else "💤 沉悶"
                    
                    scan_results.append({
                        "股票代號": sid,
                        "即時報價": f"{current_px:.2f}",
                        "漲跌幅 (%)": pct_change,
                        "今日振幅 (%)": amplitude,
                        "成交量爆發比": f"{vol_ratio:.1f}倍",
                        "月線趨勢": trend,
                        "現沖/當沖推薦": day_trade
                    })
        
        if scan_results:
            res_df = pd.DataFrame(scan_results)
            st.dataframe(
                res_df,
                use_container_width=True,
                column_config={
                    "漲跌幅 (%)": st.column_config.NumberColumn("漲跌幅 (%)", format="%+.2f"),
                    "今日振幅 (%)": st.column_config.NumberColumn("今日振幅 (%)", format="%.2f")
                }
            )
            st.caption("💡 提示：此頁面已掛載 Yahoo 奇摩股市即時爬蟲，盤中報價每 60 秒更新一次。")

# ==========================================
# 功能三：台股三大法人資金流向
# ==========================================
elif option == "3. 台股三大法人資金流向":
    st.header("🇹🇼 台股三大法人資金流向")
    st.write("抓取證交所籌碼資料，並連動 **盤中即時報價** 判斷強弱。")
    
    with st.spinner('連線證交所與即時報價伺服器...'):
        data = fetch_twse_data()
        if data and data.get('stat') == 'OK' and 'fields' in data and 'data' in data:
            fields = data['fields']
            raw_data = data['data']
            idx_code = next((i for i, f in enumerate(fields) if "代號" in f), 0)
            idx_name = next((i for i, f in enumerate(fields) if "名稱" in f), 1)
            idx_foreign = next((i for i, f in enumerate(fields) if "外資及陸資買賣超" in f or ("外" in f and "買賣超" in f and "自營" not in f)), -1)
            idx_trust = next((i for i, f in enumerate(fields) if "投信" in f and "買賣超" in f), -1)
            idx_dealer = next((i for i, f in enumerate(fields) if "自營商買賣超" in f and "外資" not in f), -1)
            
            if -1 not in [idx_foreign, idx_trust, idx_dealer]:
                df = pd.DataFrame(raw_data)
                df_clean = pd.DataFrame({
                    '股票代號': df[idx_code].astype(str),
                    '股票名稱': df[idx_name].astype(str),
                    '外資買賣超(張)': pd.to_numeric(df[idx_foreign].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000,
                    '投信買賣超(張)': pd.to_numeric(df[idx_trust].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000,
                    '自營商買賣超(張)': pd.to_numeric(df[idx_dealer].astype(str).str.replace(',', ''), errors='coerce').fillna(0) / 1000
                })
                df_clean['三大法人合計(張)'] = df_clean['外資買賣超(張)'] + df_clean['投信買賣超(張)'] + df_clean['自營商買賣超(張)']
                
                df_filtered = df_clean.sort_values(by='三大法人合計(張)', ascending=False).head(15).copy()
                
                # 使用新引擎取得前 15 名的即時股價
                prices, pcts = [], []
                for code in df_filtered['股票代號']:
                    rt_price, rt_pct = get_realtime_quote(code)
                    if rt_price is not None:
                        prices.append(rt_price)
                        pcts.append(rt_pct)
                    else:
                        prices.append(np.nan)
                        pcts.append(np.nan)
                
                df_filtered['即時報價'] = prices
                df_filtered['漲跌幅 (%)'] = pcts
                
                cols = df_filtered.columns.tolist()
                cols = cols[:2] + ['即時報價', '漲跌幅 (%)'] + cols[2:-2]
                df_filtered = df_filtered[cols]
                
                st.dataframe(
                    df_filtered,
                    use_container_width=True,
                    column_config={
                        "即時報價": st.column_config.NumberColumn("即時報價", format="$%.2f"),
                        "漲跌幅 (%)": st.column_config.NumberColumn("漲跌幅 (%)", format="%+.2f"),
                        "外資買賣超(張)": st.column_config.NumberColumn(format="%.0f"),
                        "投信買賣超(張)": st.column_config.NumberColumn(format="%.0f"),
                        "自營商買賣超(張)": st.column_config.NumberColumn(format="%.0f"),
                        "三大法人合計(張)": st.column_config.NumberColumn(format="%.0f")
                    }
                )
        else:
            st.error("⚠️ 無法取得證交所資料。")

# ==========================================
# 功能四：個股技術面與籌碼綜合診斷
# ==========================================
elif option == "4. 個股技術面與籌碼綜合診斷":
    st.header("🎯 個股技術面與籌碼深潛診斷")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        stock_id = st.text_input("輸入台股代號 (如: 3041, 2409)", st.session_state['diag_ticker']).strip()
        st.session_state['diag_ticker'] = stock_id
        analyze_btn = st.button("開始深度診斷")
    
    if analyze_btn:
        with st.spinner("計算技術指標與連線即時報價中..."):
            _, global_sentiment = fetch_us_macro()
            df = get_stock_data(stock_id)

            if df.empty:
                st.error(f"找不到代號 {stock_id} 的股價資料。")
            else:
                stock_name = stock_id
                # 啟動新引擎獲取真正即時的價格
                rt_price, rt_pct = get_realtime_quote(stock_id)
                
                if rt_price is not None and rt_pct is not None:
                    latest_px = rt_price
                    pct_change = rt_pct
                    tag = "⚡ 盤中即時"
                else:
                    latest_px = df['Close'].iloc[-1]
                    prev_px = df['Close'].iloc[-2]
                    pct_change = ((latest_px - prev_px) / prev_px) * 100
                    tag = "📅 歷史收盤"
                
                try:
                    info = yf.Ticker(f"{stock_id}.TW").info
                    stock_name = info.get('shortName', stock_id)
                except:
                    pass
                
                st.markdown("---")
                st.metric(label=f"📊 {stock_id} {stock_name} 最新報價 ({tag})", 
                          value=f"${latest_px:.2f}", 
                          delta=f"{pct_change:+.2f}%")
                
                foreign_buy, trust_buy, dealer_buy = 0, 0, 0
                has_t86_data = False
                
                t86_data = fetch_twse_data()
                if t86_data and t86_data.get('stat') == 'OK' and 'fields' in t86_data:
                    f_idx = next((i for i, f in enumerate(t86_data['fields']) if "代號" in f), -1)
                    idx_f = next((i for i, f in enumerate(t86_data['fields']) if "外資及陸資買賣超" in f or ("外" in f and "買賣超" in f and "自營" not in f)), -1)
                    idx_t = next((i for i, f in enumerate(t86_data['fields']) if "投信" in f and "買賣超" in f), -1)
                    
                    if -1 not in [f_idx, idx_f, idx_t]:
                        for row in t86_data['data']:
                            if row[f_idx] == stock_id:
                                foreign_buy = float(row[idx_f].replace(',', '')) / 1000
                                trust_buy = float(row[idx_t].replace(',', '')) / 1000
                                has_t86_data = True
                                break

                df['5MA'] = df['Close'].rolling(window=5).mean()
                df['20MA'] = df['Close'].rolling(window=20).mean()
                df['60MA'] = df['Close'].rolling(window=60).mean()
                df['Pre_Close'] = df['Close'].shift(1)
                df['Amplitude'] = ((df['High'] - df['Low']) / df['Pre_Close']) * 100
                df['Vol_5MA'] = df['Volume'].rolling(window=5).mean()
                
                recent_res = df['High'].rolling(20).max().iloc[-1]
                recent_sup = df['Low'].rolling(20).min().iloc[-1]
                
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
                                    subplot_titles=("股價與支撐壓力", "成交量", "MACD", "KD", "RSI"))
                
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
                                             name='K線', increasing_line_color='red', increasing_fillcolor='red',
                                             decreasing_line_color='green', decreasing_fillcolor='green'), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['20MA'], line=dict(color='orange', width=2), name='20MA (月線)'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['60MA'], line=dict(color='blue', width=2, dash='dash'), name='60MA (季線)'), row=1, col=1)
                
                fig.add_hline(y=recent_res, line_dash="dash", line_color="red", annotation_text="壓力線", row=1, col=1)
                fig.add_hline(y=recent_sup, line_dash="dash", line_color="lightgreen", annotation_text="支撐線", row=1, col=1)
                
                vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name='成交量'), row=2, col=1)
                
                macd_colors = ['red' if val >= 0 else 'green' for val in df['MACD_Hist']]
                fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color=macd_colors, name='MACD 柱狀圖'), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue'), name='MACD'), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], line=dict(color='orange'), name='Signal'), row=3, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='blue'), name='K值'), row=4, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='orange'), name='D值'), row=4, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='purple'), name='RSI'), row=5, col=1)
                fig.add_hline(y=70, line_dash="dot", row=5, col=1, annotation_text="過熱(70)")
                fig.add_hline(y=30, line_dash="dot", row=5, col=1, annotation_text="超賣(30)")

                fig.update_layout(height=1000, xaxis_rangeslider_visible=False, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("---")
                st.subheader("🤖 系統綜合診斷報告")
                
                latest = df.iloc[-1]
                score = 0
                
                st.markdown("#### ⚡ 短線沖銷與做空專屬雷達")
                amp = latest['Amplitude']
                
                if pd.isna(amp) or np.isinf(amp):
                    st.warning("**【當沖/現沖建議】**：今日振幅資料暫無法運算。")
                elif amp >= 4.0:
                    st.success(f"**【當沖/現沖建議】**：今日振幅達 {amp:.1f}%，波動活躍，極適合現沖操作。")
                else:
                    st.warning(f"**【當沖/現沖建議】**：今日振幅僅 {amp:.1f}%，股價沉悶，當沖獲利空間小。")
                
                if latest_px < latest['20MA'] and latest_px < latest['60MA']:
                    st.error("**【做空/借券警示】**：最新股價已跌破月線與季線，趨勢走空。可留意借券賣出或放空建倉機會。")
                else:
                    st.info("**【做空/借券警示】**：目前股價仍具備均線支撐，做空風險較高，建議觀望為主。")
                
                st.markdown("#### 🧭 多空趨勢總體檢")
                bullish_reasons = []
                bearish_reasons = []
                
                if global_sentiment > 1.5:
                    bullish_reasons.append("🌎 國際局勢：美股半導體強勢，【大環境順風】。")
                    score += 1
                elif global_sentiment < -1.5:
                    bearish_reasons.append("🌎 國際局勢：美股半導體弱勢，【大環境逆風】。")
                    score -= 1
                
                if has_t86_data:
                    if foreign_buy > 0 and trust_buy > 0:
                        bullish_reasons.append(f"大戶動向：外資與投信【同步大買】 (外資 {foreign_buy:.0f}張, 投信 {trust_buy:.0f}張)。")
                        score += 2
                    elif foreign_buy < 0 and trust_buy < 0:
                        bearish_reasons.append(f"大戶動向：外資與投信【同步大賣】。")
                        score -= 2

                if latest['MACD_Hist'] > 0 and df.iloc[-2]['MACD_Hist'] <= 0:
                    bullish_reasons.append("MACD指標：出現【黃金交叉】，剛開始起漲。")
                    score += 2
                elif latest['MACD_Hist'] < 0 and df.iloc[-2]['MACD_Hist'] >= 0:
                    bearish_reasons.append("MACD指標：出現【死亡交叉】，剛開始起跌。")
                    score -= 2

                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.success("🟢 看漲訊號 (有利上漲)\n\n" + "\n\n".join([f"- {r}" for r in bullish_reasons]) if bullish_reasons else "無明顯看漲訊號")
                with col_res2:
                    st.error("🔴 看跌訊號 (容易下跌)\n\n" + "\n\n".join([f"- {r}" for r in bearish_reasons]) if bearish_reasons else "無明顯看跌訊號")
