import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime

# --- 1. CONFIGURATION ---
BOT_TOKEN = "8648160911:AAHidzCyvcksTRAiPEvb0kNVonYRQCYjR3s" 
CHAT_ID = "977055722"

if "alert_memory" not in st.session_state:
    st.session_state.alert_memory = {}

# --- 2. LOGIN SYSTEM LOGIC ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def check_login(username, password):
    if username == "admin" and password == "trade2026":
        st.session_state.logged_in = True
        st.success("🔓 Login Successful!")
        st.rerun()
    else:
        st.error("❌ Invalid Login ID or Password")

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.set_page_config(page_title="Bot Login", layout="centered")
    st.title("🔒 DIY Strategy Bot - Secure Login")
    
    with st.form("login_form"):
        user_input = st.text_input("Login ID (Username)")
        pass_input = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Log In")
        
        if submit_button:
            check_login(user_input, pass_input)
            
    st.stop()

# --- 3. DYNAMIC WATCHLIST (NIFTY 200 AUTO-FETCH) ---
@st.cache_data(ttl=86400) # रोज़ केवल एक बार डाउनलोड करेगा ताकि ऐप स्लो न हो
def get_nifty_200_watchlist():
    try:
        # NSE India की ऑफिशियल Nifty 200 लिस्ट का URL
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        df_nse = pd.read_csv(url)
        
        # Yahoo Finance के फॉर्मेट में बदलने के लिए पीछे '.NS' जोड़ना
        tickers = [f"{sym}.NS" for sym in df_nse['Symbol'].tolist()]
        return tickers
    except Exception as e:
        # अगर कभी इंटरनेट या NSE की वेबसाइट डाउन हो, तो ये बैकअप लिस्ट काम आएगी
        st.error(f"NSE से लिस्ट लोड नहीं हो पाई, बैकअप लिस्ट यूज़ कर रहे हैं। Error: {e}")
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

# लाइव 200 स्टॉक्स की लिस्ट जनरेट करें
nifty_watchlist = get_nifty_200_watchlist()

# --- MAIN APP UI ---
st.set_page_config(page_title="DIY Institutional Bot", layout="wide")

if st.sidebar.button("🔒 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

st.title("🏹 DIY Institutional Grade Alert Bot")
st.subheader(f"📊 Tracking Total Stocks: {len(nifty_watchlist)} (Nifty 200)")

def send_telegram_with_button(msg, ticker_clean):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        tv_url = f"https://in.tradingview.com/chart/?symbol=NSE:{ticker_clean}"
        inline_keyboard = {"inline_keyboard": [[{"text": "📊 Open TradingView Chart", "url": tv_url}]]}
        
        params = {
            "chat_id": CHAT_ID, 
            "text": msg, 
            "parse_mode": "Markdown",
            "reply_markup": __import__('json').dumps(inline_keyboard)
        }
        r = requests.post(url, json=params)
        return r.json()
    except Exception as e:
        return str(e)

def calculate_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_diy_zones(df, left=10, right=10):
    levels = []
    if len(df) < (left + right + 1): return []
    for i in range(left, len(df) - right):
        if all(df['High'].iloc[i] >= df['High'].iloc[i-j] for j in range(1, left+1)) and \
           all(df['High'].iloc[i] >= df['High'].iloc[i+j] for j in range(1, right+1)):
            levels.append({'type': 'DIY_SUPPLY', 'price': round(float(df['High'].iloc[i]), 2)})
        if all(df['Low'].iloc[i] <= df['Low'].iloc[i-j] for j in range(1, left+1)) and \
           all(df['Low'].iloc[i] <= df['Low'].iloc[i+j] for j in range(1, right+1)):
            levels.append({'type': 'DIY_DEMAND', 'price': round(float(df['Low'].iloc[i]), 2)})
    return levels

auto_mode = st.sidebar.checkbox("🚀 START MASTER SCAN")
pivot_len = st.sidebar.slider("DIY Strength (Left/Right)", 5, 20, 10)
proximity = st.sidebar.slider("Alert Proximity %", 0.01, 1.0, 0.10)
vol_multiplier = st.sidebar.slider("Volume Multiplier (X)", 1.0, 3.0, 1.5, step=0.1)
rsi_filter_on = st.sidebar.checkbox("🔥 Enable RSI Exhaustion Filter (30/70)", value=True)

if st.sidebar.button("Clear Alert History"):
    st.session_state.alert_memory = {}
    st.sidebar.success("Memory Cleared!")

if auto_mode:
    st.success(f"Bot is LIVE! Scanning {len(nifty_watchlist)} Stocks in background...")
    placeholder = st.empty()
    
    while auto_mode:
        curr_time = datetime.now().strftime("%H:%M:%S")
        today_date = datetime.now().strftime("%Y-%m-%d")
        found_alerts = []
        
        for ticker in nifty_watchlist:
            try:
                df = yf.download(ticker, period="20d", interval="30m", auto_adjust=True, progress=False)
                if df.empty or len(df) < 30: continue
                    
                if isinstance(df.columns, pd.MultiIndex): 
                    df.columns = df.columns.get_level_values(0)
                
                df['RSI'] = calculate_rsi(df, period=14)
                
                curr_p = float(df['Close'].iloc[-2])
                curr_v = float(df['Volume'].iloc[-2])
                curr_rsi = float(df['RSI'].iloc[-2]) if not pd.isna(df['RSI'].iloc[-2]) else 50
                avg_volume = float(df['Volume'].iloc[-22:-2].mean())
                
                zones = get_diy_zones(df, pivot_len, pivot_len)
                
                if zones:
                    l_sup = next((z for z in reversed(zones) if z['type'] == 'DIY_SUPPLY'), None)
                    l_dem = next((z for z in reversed(zones) if z['type'] == 'DIY_DEMAND'), None)
                    
                    for target in [l_sup, l_dem]:
                        if target:
                            dist = abs(curr_p - target['price']) / target['price'] * 100
                            
                            if dist <= proximity and curr_v >= (avg_volume * vol_multiplier):
                                if rsi_filter_on:
                                    if target['type'] == 'DIY_SUPPLY' and curr_rsi < 65: continue
                                    if target['type'] == 'DIY_DEMAND' and curr_rsi > 35: continue
                                
                                ticker_clean = ticker.replace(".NS", "")
                                vol_status = f"{curr_v/avg_volume:.1f}x Spike"
                                
                                memory_key = f"{ticker_clean}_{target['type']}_{today_date}"
                                if memory_key in st.session_state.alert_memory:
                                    found_alerts.append({
                                        "Stock": ticker_clean, "Type": target['type'], "Level": target['price'], "LTP": round(curr_p, 2), "RSI": round(curr_rsi,1), "Volume": f"{vol_status} (Sent)"
                                    })
                                    continue
                                
                                st.session_state.alert_memory[memory_key] = True
                                
                                msg = (
                                    f"🚨 *DIY INSTITUTIONAL ALERT: {ticker_clean}*\n\n"
                                    f"🔹 *Type:* {target['type']}\n"
                                    f"🎯 *Zone Level:* ₹{target['price']}\n"
                                    f"💰 *Confirmed Close:* ₹{curr_p:.2f}\n"
                                    f"🔥 *Volume Surge:* {vol_status}\n"
                                    f"📈 *30-Min RSI:* {curr_rsi:.1f} {'⚠️ EXHAUSTION' if (curr_rsi>65 or curr_rsi<35) else ''}\n"
                                    f"⏰ *Time:* {curr_time}"
                                )
                                
                                send_telegram_with_button(msg, ticker_clean)
                                
                                found_alerts.append({
                                    "Stock": ticker_clean, "Type": target['type'], "Level": target['price'], "LTP": round(curr_p, 2), "RSI": round(curr_rsi,1), "Volume": f"{vol_status} (NEW)"
                                })
            except Exception as e:
                continue # बैकग्राउंड एरर को इग्नोर करके अगला स्टॉक स्कैन करेगा
        
        with placeholder.container():
            st.write(f"### 🕒 Last Scan completed at: {curr_time}")
            if found_alerts:
                st.table(pd.DataFrame(found_alerts))
            else:
                st.info("Scanning all Nifty 200 stocks... No strong high-volume setups at the moment.")
        
        for _ in range(900):
            time.sleep(1)
            if not auto_mode: break
else:
    st.info("Sidebar से 'START MASTER SCAN' ऑन करें।")