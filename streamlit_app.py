import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime
import pytz

# --- 1. CONFIGURATION ---
BOT_TOKEN = "8648160911:AAHidzCyvcksTRAiPEvb0kNVonYRQCYjR3s"
CHAT_ID = "977055722"

if "alert_memory" not in st.session_state:
    st.session_state.alert_memory = {}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- LOGIN ---
if not st.session_state.logged_in:
    st.set_page_config(page_title="Bot Login", layout="centered")
    st.title("🔒 DIY Strategy Bot - Secure Login")
    with st.form("login_form"):
        user_input = st.text_input("Login ID")
        pass_input = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            if user_input.strip() == "admin" and pass_input.strip() == "bullrun2026":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ Invalid Login")
    st.stop()

# --- WATCHLIST ---
@st.cache_data(ttl=86400)
def get_nifty_200_watchlist():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        return [f"{sym}.NS" for sym in pd.read_csv(url)['Symbol'].tolist()]
    except:
        return ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]

nifty_watchlist = get_nifty_200_watchlist()
st.set_page_config(page_title="DIY Institutional Bot", layout="wide")
st.title("🏹 DIY Institutional Grade Alert Bot")

# --- TELEGRAM FUNCTION ---
def send_telegram_alert(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def calculate_rsi(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    return 100 - (100 / (1 + (gain.ewm(com=13, min_periods=14).mean() / loss.ewm(com=13, min_periods=14).mean())))

def get_diy_zones(df, l=10, r=10):
    levels = []
    if len(df) < (l + r + 1): return []
    h, l_p = list(df['High']), list(df['Low'])
    for i in range(l, len(df) - r):
        if h[i] == max(h[i-l:i+r+1]): levels.append({'type': 'DIY_SUPPLY', 'price': round(float(h[i]), 2)})
        if l_p[i] == min(l_p[i-l:i+r+1]): levels.append({'type': 'DIY_DEMAND', 'price': round(float(l_p[i]), 2)})
    return levels

auto_mode = st.sidebar.checkbox("🚀 START MASTER SCAN")
pivot_len = st.sidebar.slider("DIY Strength", 5, 20, 10)
proximity = st.sidebar.slider("Alert Proximity %", 0.01, 5.0, 1.50, step=0.05)

if auto_mode:
    st.success("Bot is LIVE! Scanning Stocks...")
    placeholder = st.empty()
    send_telegram_alert("🚀 *DIY Bot Master Scan Started Successfully! Timezone: IST*")
    
    while auto_mode:
        ist = pytz.timezone('Asia/Kolkata')
        curr_time = datetime.now(ist).strftime("%H:%M:%S")
        today_date = datetime.now(ist).strftime("%Y-%m-%d")
        found_alerts = []
        
        for ticker in nifty_watchlist:
            try:
                df = yf.download(ticker, period="15d", interval="30m", auto_adjust=True, progress=False)
                if df.empty or len(df) < 25: continue
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                curr_p, curr_v = float(df['Close'].iloc[-1]), float(df['Volume'].iloc[-1])
                df['RSI'] = calculate_rsi(df)
                curr_rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
                zones = get_diy_zones(df, pivot_len, pivot_len)
                
                if zones:
                    for target in zones:
                        if (abs(curr_p - target['price']) / target['price']) * 100 <= proximity:
                            ticker_clean = ticker.replace(".NS", "")
                            m_key = f"{ticker_clean}_{target['type']}_{today_date}_{target['price']}"
                            
                            if m_key in st.session_state.alert_memory:
                                found_alerts.append({"Stock": ticker_clean, "Type": target['type'], "Level": target['price'], "LTP": round(curr_p, 2), "Status": "Sent"})
                                continue
                            
                            st.session_state.alert_memory[m_key] = True
                            msg = f"🚨 *DIY INSTITUTIONAL ALERT: {ticker_clean}*\n\n🔹 *Type:* {target['type']}\n🎯 *Level:* ₹{target['price']}\n💰 *LTP:* ₹{curr_p:.2f}\n📈 *RSI:* {curr_rsi:.1f}\n⏰ *IST Time:* {curr_time}"
                            send_telegram_alert(msg)
                            found_alerts.append({"Stock": ticker_clean, "Type": target['type'], "Level": target['price'], "LTP": round(curr_p, 2), "Status": "NEW"})
            except:
                continue
        
        with placeholder.container():
            st.write(f"### 🕒 Last Scan completed at (IST): {curr_time}")
            if found_alerts: 
                st.table(pd.DataFrame(found_alerts))
            else: 
                st.info("Scanning all Nifty 200 stocks...")
        time.sleep(15)
