#!/usr/bin/env python3
"""
TRON - AI-Powered Fiber Optic ISP Customer Support Agent
"""

import streamlit as st
from openai import OpenAI
import sys
import json
import logging
from datetime import datetime
import os
import re
import time

# -----------------------------------------------------------------------------
# 1. Configure logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    filename=f"tron_debug_{datetime.now().strftime('%Y%m%d')}.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 2. Import
# -----------------------------------------------------------------------------
sys.path.insert(0, "/home/mazakar/TRON/TRON1")
from minitron_lookup import (
    initial_report,
    onu_scan,
    onu_wifi,
    onu_change_wifi,
    onu_traffic,
    onu_traffic_stream
)

# -----------------------------------------------------------------------------
# 3. Page config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="TRON", page_icon="⚡", layout="wide")

st.markdown("""
<style>
    .main-header { text-align: center; padding: 1rem 0; }
    .main-header h1 { font-size: 2.5rem; font-weight: 700; letter-spacing: -1px; margin: 0; }
    .main-header p { color: #888; font-size: 0.9rem; margin: 0; }
    .stChatMessage { border-radius: 12px !important; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px; padding: 1rem; text-align: center;
        border: 1px solid #2a2a4a;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; }
    .metric-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
    .online-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: #00ff88; margin-right: 6px; animation: pulse 2s infinite;
    }
    .offline-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        background: #ff4444; margin-right: 6px;
    }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    div[data-testid="stSidebar"] { background: linear-gradient(180deg, #0a0a1a 0%, #1a1a2e 100%); }
    .stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.2s; }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .traffic-table { width: 100%; font-family: monospace; font-size: 0.85rem; border-collapse: collapse; }
    .traffic-table th { background: #1a1a2e; padding: 0.4rem 0.8rem; text-align: left; position: sticky; top: 0; }
    .traffic-table td { padding: 0.3rem 0.8rem; border-bottom: 1px solid #1a1a2e; }
    .traffic-high { color: #ff4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header"><h1>⚡ TRON</h1><p>Network Intelligence</p></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. OpenAI
# -----------------------------------------------------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -----------------------------------------------------------------------------
# 5. Plans
# -----------------------------------------------------------------------------
PLANS_FILE = "/home/mazakar/TRON/TRON1/plans.json"

DEFAULT_PLANS = {
    "FiberMax Home": {"plan": "FiberMax Home", "speed": "50 Mbps", "amount": "₦24,083"},
    "FiberMax LitePlus": {"plan": "FiberMax LitePlus", "speed": "20 Mbps", "amount": "₦17,043"},
    "FiberMax Home Extra": {"plan": "FiberMax Home Extra", "speed": "75 Mbps", "amount": "₦31,361"},
    "FiberMax Ultra": {"plan": "FiberMax Ultra", "speed": "100 Mbps", "amount": "₦52,427"},
    "FiberMax Ultimate+": {"plan": "FiberMax Ultimate+", "speed": "220 Mbps", "amount": "₦92,768"},
    "FiberMax Ultimate": {"plan": "FiberMax Ultimate", "speed": "145 Mbps", "amount": "₦70,395"},
    "AirFiber Home": {"plan": "AirFiber Home", "speed": "50 Mbps", "amount": "₦24,083"},
    "FibreHome-OutsideLagos": {"plan": "FibreHome-OutsideLagos", "speed": "50 Mbps", "amount": "₦24,083"}
}

@st.cache_data(ttl=3600)
def load_plans():
    if os.path.exists(PLANS_FILE):
        try:
            with open(PLANS_FILE, 'r') as f: return json.load(f)
        except: pass
    with open(PLANS_FILE, 'w') as f: json.dump(DEFAULT_PLANS, f, indent=2)
    return DEFAULT_PLANS

PLANS = load_plans()

# -----------------------------------------------------------------------------
# 6. Session state
# -----------------------------------------------------------------------------
if "setup_complete" not in st.session_state: st.session_state.setup_complete = False
if "messages" not in st.session_state: st.session_state.messages = []
if "username" not in st.session_state: st.session_state.username = ""
if "formatted_username" not in st.session_state: st.session_state.formatted_username = ""
if "initial_report" not in st.session_state: st.session_state.initial_report = ""
if "connection_up" not in st.session_state: st.session_state.connection_up = False
if "last_check" not in st.session_state: st.session_state.last_check = None
if "traffic_plan_speed" not in st.session_state: st.session_state.traffic_plan_speed = 0

# Traffic
if "traffic_mode" not in st.session_state: st.session_state.traffic_mode = None
if "traffic_stream_data" not in st.session_state: st.session_state.traffic_stream_data = None
if "traffic_live_active" not in st.session_state: st.session_state.traffic_live_active = False
if "traffic_live_start" not in st.session_state: st.session_state.traffic_live_start = 0
if "traffic_live_download" not in st.session_state: st.session_state.traffic_live_download = 0
if "traffic_live_upload" not in st.session_state: st.session_state.traffic_live_upload = 0
if "traffic_live_last_fetch" not in st.session_state: st.session_state.traffic_live_last_fetch = 0
if "traffic_live_count" not in st.session_state: st.session_state.traffic_live_count = 0

# -----------------------------------------------------------------------------
# 7. Cached initial report - called ONCE
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def get_cached_report(username):
    """Fetch initial report. Cached by Streamlit - runs ONCE per username."""
    logger.info(f"FETCHING REPORT - {username}")
    return initial_report(username)

# -----------------------------------------------------------------------------
# 8. Utility functions
# -----------------------------------------------------------------------------
def format_username(raw):
    return raw.strip().lower().replace(' ', '_')

def detect_connection(report_text):
    t = report_text.lower()
    if "🔴 offline" in t: return False
    if "🟢 online" in t: return True
    if "🔴 unreachable" in t: return False
    if "🟢 reachable" in t: return True
    if "loss of signal" in t or "los" in t: return False
    return False

def get_plan_speed():
    report = st.session_state.initial_report
    if report:
        match = re.search(r"Plan:\s+(.+)", report)
        if match:
            for key, plan in PLANS.items():
                if key.lower() == match.group(1).strip().lower():
                    return int(plan["speed"].split()[0])
    return 0

def check_connection():
    return st.session_state.connection_up

def scan_devices():
    if not check_connection(): return {"success": False, "error": "Connection is down."}
    try: return onu_scan(st.session_state.formatted_username)
    except Exception as e: return {"success": False, "error": str(e)}

def get_wifi_details():
    if not check_connection(): return {"success": False, "error": "Connection is down."}
    try: return onu_wifi(st.session_state.formatted_username)
    except Exception as e: return {"success": False, "error": str(e)}

def change_wifi(ssid=None, password=None):
    if not check_connection(): return {"success": False, "error": "Connection is down."}
    try: return onu_change_wifi(st.session_state.formatted_username, ssid, password)
    except Exception as e: return {"success": False, "error": str(e)}

# -----------------------------------------------------------------------------
# 9. Response formatting
# -----------------------------------------------------------------------------
def format_result(func_name, result):
    if isinstance(result, str): return f"Result: {result}"
    if not isinstance(result, dict): return str(result)
    err = str(result.get("error", ""))
    
    if func_name in ["scan_devices", "get_wifi_details", "change_wifi"] and "connection is down" in err.lower():
        return "SYSTEM: Connection is down."
    
    if func_name == "scan_devices":
        if result.get("success"):
            devices = result.get("devices", [])
            total = result.get("total_count", len(devices))
            if total == 0: return "No devices connected."
            dl = "\n".join([f"- {d.get('hostname','?')} ({d.get('ip','?')})" for d in devices])
            return f"Found {total} device(s):\n{dl}"
        return f"Scan failed: {err}"
    
    if func_name == "get_wifi_details":
        if result.get("success") or result.get("ssid"):
            return f"SSID: {result.get('ssid','?')}\nPassword: {result.get('password','?')}"
        return f"Failed: {err}"
    
    if func_name == "change_wifi":
        if result.get("success"):
            parts = []
            if result.get("ssid_changed"): parts.append(f"SSID → {result.get('new_ssid')}")
            if result.get("password_changed"): parts.append("Password updated")
            return "WiFi updated. " + ", ".join(parts)
        return f"Failed: {err}"
    
    return f"Result: {json.dumps(result, default=str)}"

# -----------------------------------------------------------------------------
# 10. Setup
# -----------------------------------------------------------------------------
if not st.session_state.setup_complete:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("", max_chars=40, key="user_input", placeholder="Enter username...", label_visibility="collapsed")
        
        if st.button("⚡ Initialize", type="primary", use_container_width=True):
            if username.strip():
                st.session_state.username = username.strip()
                st.session_state.formatted_username = format_username(username)
                
                # ONE CALL
                report = get_cached_report(st.session_state.formatted_username)
                
                st.session_state.initial_report = report
                st.session_state.connection_up = detect_connection(report)
                st.session_state.last_check = datetime.now().isoformat()
                st.session_state.traffic_plan_speed = get_plan_speed()
                st.session_state.setup_complete = True
                
                plans_info = "\n".join([f"- {p['plan']}: {p['speed']} at {p['amount']}/month" for p in PLANS.values()])
                conn = "UP" if st.session_state.connection_up else "DOWN"
                
                st.session_state.messages = [{
                    "role": "system",
                    "content": (
                        f"You are TRON, an ISP support agent. Be concise and helpful.\n\n"
                        f"PLANS:\n{plans_info}\n\n"
                        f"REPORT:\n{report}\n\n"
                        f"CONNECTION: {conn}\n\n"
                        f"CAPABILITIES:\n"
                        f"- Connection status & troubleshooting (LOS, downtime, poor signal)\n"
                        f"- Live traffic monitoring (60-second stream or sidebar live view)\n"
                        f"- WiFi management (view/change SSID and password)\n"
                        f"- Device scanning (list all connected devices)\n"
                        f"- Account info (plan, speed, expiry, status)\n"
                        f"- Plan upgrades (compare available plans)\n\n"
                        f"RULES:\n"
                        f"- ONU access only if connection UP.\n"
                        f"- LOS/Offline: physical checks first, no remote access.\n"
                        f"- Traffic keywords: system auto-starts 60s stream.\n"
                        f"- Say 'One moment' for ONU operations.\n"
                        f"- Never show raw data. Be brief."
                    )
                }]
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Hello {st.session_state.username}. I'm TRON. How can I help?"
                })
                st.rerun()
            else:
                st.warning("Enter a username")

# -----------------------------------------------------------------------------
# 11. Main App
# -----------------------------------------------------------------------------
if st.session_state.setup_complete:
    
    # STREAM MODE (Chat) - 1 call
    if st.session_state.traffic_mode == "stream":
        if st.session_state.traffic_stream_data is None:
            with st.spinner("📡 Streaming traffic for 60 seconds..."):
                try:
                    result = onu_traffic_stream(st.session_state.formatted_username)
                    if result.get("success"):
                        st.session_state.traffic_stream_data = result
                    else:
                        st.session_state.traffic_mode = None
                        st.error("Stream failed.")
                except Exception as e:
                    st.session_state.traffic_mode = None
                    st.error(f"Error: {e}")
            st.rerun()
        else:
            data = st.session_state.traffic_stream_data
            samples = data.get("samples", [])
            plan_speed = st.session_state.traffic_plan_speed
            
            st.markdown("#### 📊 60-Second Traffic Report")
            st.caption(f"OLT: {data.get('olt', 'N/A')} | {len(samples)} samples | Plan: {plan_speed} Mbps")
            
            if samples:
                avg_dl = sum(s.get("output_mbps", 0) for s in samples) / len(samples)
                avg_ul = sum(s.get("input_mbps", 0) for s in samples) / len(samples)
                max_dl = max(s.get("output_mbps", 0) for s in samples)
                
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""<div class="metric-card"><div class="metric-label">Avg Download</div><div class="metric-value" style="color:{'#ff4444' if avg_dl > plan_speed*0.9 else '#00ff88'}">{avg_dl:.2f}</div><div style="font-size:0.7rem;color:#888">Mbps</div></div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""<div class="metric-card"><div class="metric-label">Max Download</div><div class="metric-value">{max_dl:.2f}</div><div style="font-size:0.7rem;color:#888">Mbps</div></div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""<div class="metric-card"><div class="metric-label">Avg Upload</div><div class="metric-value" style="color:#4dabf7">{avg_ul:.2f}</div><div style="font-size:0.7rem;color:#888">Mbps</div></div>""", unsafe_allow_html=True)
                with c4:
                    usage = min(avg_dl / plan_speed, 1.0) * 100 if plan_speed > 0 else 0
                    st.markdown(f"""<div class="metric-card"><div class="metric-label">Usage</div><div class="metric-value" style="color:{'#ff4444' if usage >= 90 else '#ffd43b' if usage >= 70 else '#00ff88'}">{usage:.0f}%</div><div style="font-size:0.7rem;color:#888">of plan</div></div>""", unsafe_allow_html=True)
                
                if plan_speed > 0:
                    st.progress(min(avg_dl / plan_speed, 1.0), text=f"Average: {min(avg_dl/plan_speed,1.0)*100:.0f}%")
                
                st.markdown("**📋 Samples:**")
                table = '<table class="traffic-table"><tr><th>#</th><th>Time</th><th>📥 Download</th><th>📤 Upload</th></tr>'
                for i, s in enumerate(samples):
                    dl = s.get("output_mbps", 0)
                    ul = s.get("input_mbps", 0)
                    ts = s.get("timestamp", "").split("T")[1].split(".")[0] if "T" in s.get("timestamp", "") else f"#{i+1}"
                    over = dl > plan_speed * 0.9 if plan_speed > 0 else False
                    rc = ' class="traffic-high"' if over else ""
                    table += f'<tr{rc}><td>{i+1}</td><td>{ts}</td><td>{dl:.3f}</td><td>{ul:.3f}</td></tr>'
                table += '</table>'
                st.markdown(f'<div style="max-height:400px;overflow-y:auto;">{table}</div>', unsafe_allow_html=True)
            
            if st.button("✅ Close", use_container_width=True):
                st.session_state.traffic_mode = None
                st.session_state.traffic_stream_data = None
                st.rerun()
            st.stop()
    
    # LIVE MODE (Sidebar)
    if st.session_state.traffic_live_active:
        elapsed = time.time() - st.session_state.traffic_live_start
        
        if elapsed < 60:
            now = time.time()
            if now - st.session_state.traffic_live_last_fetch >= 2.0:
                try:
                    r = onu_traffic(st.session_state.formatted_username)
                    if r.get("success"):
                        st.session_state.traffic_live_download = r.get("output_mbps", 0)
                        st.session_state.traffic_live_upload = r.get("input_mbps", 0)
                        st.session_state.traffic_live_count += 1
                        st.session_state.traffic_live_last_fetch = now
                except: pass
            
            dl = st.session_state.traffic_live_download
            ul = st.session_state.traffic_live_upload
            ps = st.session_state.traffic_plan_speed
            rem = 60 - int(elapsed)
            
            with st.sidebar:
                st.metric("📥 Download", f"{dl:.2f} Mbps")
                st.metric("📤 Upload", f"{ul:.2f} Mbps")
                if ps > 0:
                    st.progress(min(dl/ps, 1.0), text=f"Usage: {min(dl/ps,1.0)*100:.0f}%")
                st.caption(f"⏱ {rem}s • #{st.session_state.traffic_live_count}")
                if st.button("⏹ Stop", use_container_width=True):
                    st.session_state.traffic_live_active = False
                    st.rerun()
            
            time.sleep(0.5)
            st.rerun()
        else:
            st.session_state.traffic_live_active = False
            st.success("✅ 60s complete.")
            time.sleep(2)
            st.rerun()
    
    # CHAT DISPLAY
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    # CHAT INPUT
    if prompt := st.chat_input("Message..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if any(w in prompt.lower() for w in ["traffic", "bandwidth", "speed", "slow"]):
            if check_connection():
                st.session_state.messages.append({"role": "assistant", "content": "Starting 60-second traffic stream..."})
                st.session_state.traffic_mode = "stream"
                st.session_state.traffic_stream_data = None
                st.rerun()
            else:
                st.session_state.messages.append({"role": "assistant", "content": "Connection is down. Let's troubleshoot first."})
                st.rerun()
        
        tools = [
            {"type": "function", "function": {"name": "refresh_report", "description": "Refresh report.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "scan_devices", "description": "List WiFi devices.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "get_wifi_details", "description": "Get SSID/password.", "parameters": {"type": "object", "properties": {}, "required": []}}},
            {"type": "function", "function": {"name": "change_wifi", "description": "Change SSID/password.", "parameters": {"type": "object", "properties": {"ssid": {"type": "string"}, "password": {"type": "string"}}, "required": []}}}
        ]
        
        try:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                
                stream = client.chat.completions.create(
                    model="gpt-4o",
                    messages=st.session_state.messages,
                    tools=tools,
                    tool_choice="auto",
                    stream=True,
                )
                
                content = ""
                tool_calls = []
                
                for chunk in stream:
                    if not chunk.choices: continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        content += delta.content
                        placeholder.markdown(content + "▌")
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            while len(tool_calls) <= tc.index:
                                tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            t = tool_calls[tc.index]
                            if tc.id: t["id"] = tc.id
                            if tc.function:
                                if tc.function.name: t["function"]["name"] = tc.function.name
                                if tc.function.arguments: t["function"]["arguments"] += tc.function.arguments
                
                if tool_calls:
                    if content: placeholder.markdown(content)
                    st.session_state.messages.append({"role": "assistant", "content": content or None, "tool_calls": tool_calls})
                    
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
                        try:
                            if func_name == "refresh_report":
                                st.cache_data.clear()
                                report = get_cached_report(st.session_state.formatted_username)
                                st.session_state.initial_report = report
                                st.session_state.connection_up = detect_connection(report)
                                raw = {"report": report}
                            elif func_name == "scan_devices":
                                with st.spinner("..."): raw = scan_devices()
                            elif func_name == "get_wifi_details":
                                with st.spinner("..."): raw = get_wifi_details()
                            elif func_name == "change_wifi":
                                with st.spinner("..."): raw = change_wifi(args.get("ssid"), args.get("password"))
                            else:
                                raw = {"error": "Unknown"}
                        except Exception as e:
                            raw = {"error": str(e)}
                        
                        formatted = format_result(func_name, raw) if func_name != "refresh_report" else f"Report refreshed. Connection: {'UP' if st.session_state.connection_up else 'DOWN'}"
                        st.session_state.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": formatted})
                    
                    with st.spinner("..."):
                        final = client.chat.completions.create(model="gpt-4o", messages=st.session_state.messages, stream=True)
                    response = placeholder.write_stream(final)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    placeholder.markdown(content)
                    st.session_state.messages.append({"role": "assistant", "content": content})
        except Exception as e:
            st.error("Something went wrong. Please try again.")
        st.rerun()
    
    # SIDEBAR
    with st.sidebar:
        if st.session_state.connection_up:
            st.markdown(f'<p><span class="online-dot"></span> Online</p>', unsafe_allow_html=True)
        else:
            st.markdown(f'<p><span class="offline-dot"></span> Offline</p>', unsafe_allow_html=True)
        
        st.divider()
        
        if st.session_state.connection_up:
            if st.button("📊 Live Traffic (60s)", type="primary", use_container_width=True):
                st.session_state.traffic_live_active = True
                st.session_state.traffic_live_start = time.time()
                st.session_state.traffic_live_last_fetch = 0
                st.session_state.traffic_live_count = 0
                st.session_state.traffic_plan_speed = get_plan_speed()
                st.rerun()
        
        if st.button("🔄 Restart", use_container_width=True):
            st.cache_data.clear()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        
        st.divider()
        st.caption("TRON v3.1")
