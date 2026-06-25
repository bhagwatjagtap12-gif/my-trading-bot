import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime
import pytz

# --- 1. DIRECT CREDENTIALS ---
BOT_TOKEN = "8648160911:AAHidzCyvcksTRAiPEvb0kNVonYRQCYjR3s"
CHAT_ID = "977055722"

if "alert_memory" not in st.session_state:
    st.session_state.alert_memory = {}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def check_login(username, password):
    if username.strip() == "admin" and password.strip() == "bullrun2026":
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

# --- 3. WATCHLIST FETCH ---
@st.cache_data(ttl=86400)
def get_nifty_200_watchlist():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        df_nse = pd.read_csv(url)
        return [f"{sym}.NS" for sym in df_nse['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

nifty_watchlist = get_nifty_200_watchlist()

st.set_page_config(page_title="DIY Institutional Bot", layout="wide")

if st.sidebar.button("🔒 Log Out"):
    st.session_state.logged_in = False
    st.rerun()

st.title("🏹 DIY Institutional Grade Alert Bot")
st.subheader(f"📊 Tracking Total Stocks: {len(nifty_watchlist)} (Nifty 200)")

# --- TELEGRAM FUNCTION ---
def send_telegram_alert(msg):
    try:
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(api_url, data=payload, timeout=10)
    except:
        pass

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
    highs = list(df['High'])
    lows = list(df['Low'])
    for i in range(left, len(df) - right):
        if highs[i] == max(highs[i-left:i+right+1]):
            levels.append({'type': 'DIY_SUPPLY', 'price': round(float(highs[i]), 2)})
        if lows[i] == min(lows[i-left:i+right+1]):
            levels.append({'type': 'DIY_DEMAND', 'price': round(float(lows[i]), 2)})
    return levels

auto_mode = st.sidebar.checkbox("🚀 START MASTER SCAN")
pivot_len = st.sidebar.slider("DIY Strength (Left/Right)", 5, 20, 10)
proximity = st.sidebar.slider("Alert Proximity %", 0.01, 5.0, 1.50, step=0.05)
vol_multiplier = st.sidebar.slider("Volume Multiplier (X)", 1.0, 3.0, 1.0, step=0.1)
rsi_filter_on = st.sidebar.checkbox("🔥 Enable RSI Exhaustion Filter (30/70)", value=False)

if st.sidebar.button("Clear Alert History"):
    st.session_state.alert_memory = {}
    st.sidebar.success("Memory Cleared!")

if auto_mode:
    st.success("Bot is LIVE! Scanning 200 Stocks...")
    placeholder = st.empty()
    
    send_telegram_alert("🚀 *DIY Bot Master Scan Started Successfully! Tracking Nifty 200...*")
    
    while auto_mode:
        ist = pytz.timezone('Asia/Kolkata')
        curr_time = datetime.now(ist).strftime("%H:%M:%S")
        today_date = datetime.now(ist).strftime("%Y-%m-%d")
        found_alerts = []
        
        for ticker in nifty_watchlist:
            try:
                df = yf.download(ticker, period="15d", interval="30m", auto_adjust=True, progress=False)
                if df.empty or len(df) < 25: continue
                
                if isinstance(df.columns, pd.MultiIndex): 
                    df.columns = df.columns.get_level_values(0)
                
                curr_p = float(df['Close'].iloc[-1])
                curr_v = float(df['Volume'].iloc[-1])
                
                df['RSI'] = calculate_rsi(df, period=14)
                curr_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
                avg_volume = float(df['Volume'].iloc[-20:-1].mean())
                
                zones = get_diy_zones(df, pivot_len, pivot_len)
                
                if zones:
                    l_sup = next((z for z in reversed(zones) if z['type'] == 'DIY_SUPPLY'), None)
                    l_dem = next((z for z in reversed(zones) if z['type'] == 'DIY_DEMAND'), None)
                    
                    for target in [l_sup, l_dem]:
                        if target:
                            dist = (abs(curr_p - target['price']) / target['price']) * 100
                            
                            if dist <= proximity and curr_v >= (avg_volume * vol_multiplier):
                                if rsi_filter_on:
                                    if target['type'] == 'DIY_SUPPLY' and curr_rsi < 65: continue
                                    if target['type'] == 'DIY_DEMAND' and curr_rsi > 35: continue
                                
                                ticker_clean = ticker.replace(".NS", "")
                                memory_key = f"{ticker_clean}_{target['type']}_{today_date}"
                                
                                if memory_key in st.session_state.alert_memory:
                                    found_alerts.append({
                                        "Stock": ticker_clean, "Type": target['type'], "Level": target['price'], "LTP": round(curr_p, 2), "RSI": round(curr_rsi,1), "Volume": "Sent"
                                    })
                                    continue
                                
                                st.session_state.alert_memory[memory_key] = True
                                
                                msg = (
                                    f"🚨 *DIY INSTITUTIONAL ALERT: {ticker_clean}*\n\n"
                                    f"🔹 *Type:* {target['type']}\n"
                                    f"🎯 *Zone Level:* ₹{target['price']}\n"
                                    f"💰 *Live Price (LTP):* ₹{curr_p:.2f}\n"
                                    f"📈 *30-Min RSI:* {curr_rsi:.1f}\n"
                                    f"⏰ *India Time (IST):* {curr_time}"
                                )
                                
                                send_telegram_alert(msg)
                                
                                found
