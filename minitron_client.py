#!/usr/bin/env python3
"""
MINITRON API Client - Calls the secured API backdoor
Supports: search, status, extract, onu/scan, onu/wifi, onu/change_wifi, traffic
Connects to multiple API servers (cloud + LAN)
"""

import requests
import sys
import json
import os
import re
from datetime import datetime

# Multiple API servers - tries cloud first, then LAN
API_SERVERS = {
    "cloud": "http://0.0.0.0:8000",
    "lan": "http://192.168.1.100:8000",  # Adjust LAN IP as needed
}
API_TOKEN = None
CURRENT_SERVER = "cloud"

PORT_ANALYSIS_DB = []

def load_port_analysis_db():
    global PORT_ANALYSIS_DB
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tron.json')
    default_db = [
        {"id": 1, "input": "{'onl': 0, 'LOS': 0, 'pf': 0, 'ofl': 100, 'flags': {'JCU': 0, 'JWD': 0, 'HL': 0, 'MPI': 0, 'MST': 0}}",
         "output": "There is a general downtime affecting the clients location. The PON Port is currently down."},
        {"id": 2, "input": "{'onl': 0, 'LOS': 0, 'pf': 0, 'ofl': 100, 'flags': {'JCU': 0, 'JWD': 0, 'HL': 0, 'MPI': 0, 'MST': 1}}",
         "output": "There is a suspected MST/splitter issue affecting multiple clients. The PON Port is currently down."},
        {"id": 3, "input": "{'onl': 0, 'LOS': 0, 'pf': 0, 'ofl': 100, 'flags': {'JCU': 0, 'JWD': 0, 'HL': 0, 'MPI': 1, 'MST': 0}}",
         "output": "There is a major port issue affecting the clients location. The PON Port is currently down."},
        {"id": 4, "input": "{'onl': 0, 'LOS': 100, 'pf': 0, 'ofl': 0, 'flags': {'JCU': 0, 'JWD': 0, 'HL': 0, 'MPI': 1, 'MST': 0}}",
         "output": "All clients on this port are experiencing LOS. The PON Port is currently down."},
        {"id": 5, "input": "{'onl': 10, 'LOS': 80, 'pf': 10, 'ofl': 0, 'flags': {'JCU': 0, 'JWD': 0, 'HL': 0, 'MPI': 1, 'MST': 1}}",
         "output": "Multiple clients are down with LOS and Power Failures. There is a suspected MST/splitter issue with major port impact."}
    ]
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                PORT_ANALYSIS_DB = json.load(f)
            return
        except: pass
    PORT_ANALYSIS_DB = default_db
    try:
        with open(db_path, 'w') as f:
            json.dump(default_db, f, indent=2)
    except: pass

def find_port_analysis_match(raw_debug_data):
    if not raw_debug_data: return None
    input_str = str(raw_debug_data)
    for record in PORT_ANALYSIS_DB:
        if record.get('input', '').strip() == input_str:
            return record.get('output', None)
    return None

def check_account_expired(expiry_date_str):
    if not expiry_date_str or expiry_date_str == 'N/A': return False, None
    try:
        expiry_date = None
        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y', '%m/%d/%Y']:
            try: expiry_date = datetime.strptime(expiry_date_str.split()[0], fmt); break
            except: continue
        if expiry_date is None: return False, None
        now = datetime.now()
        days_remaining = (expiry_date - now).days
        if days_remaining < 0: return True, abs(days_remaining)
        elif days_remaining <= 7: return 'expiring_soon', days_remaining
        return False, days_remaining
    except: return False, None

def format_account_status_from_raw(result):
    if not result: return ""
    network = result.get('network_analysis')
    diam_data = network.get('diameter_data', {}) if network else {}
    if not diam_data or not diam_data.get('found'): return ""
    
    full_name = f"{diam_data.get('first_name', '')} {diam_data.get('last_name', '')}".strip()
    if not full_name or full_name == 'N/A N/A': full_name = diam_data.get('username', 'N/A')
    expiry_date = diam_data.get('expiry_date', 'N/A')
    service_plan = diam_data.get('service_plan', 'N/A')
    account_status, days_info = check_account_expired(expiry_date)
    ping_reachable = diam_data.get('ping_reachable', False)
    cpe_ip = diam_data.get('cpe_ip', 'N/A')
    status = diam_data.get('status', 'N/A')
    phone = diam_data.get('phone', 'N/A')
    address = diam_data.get('address', 'N/A')
    last_logoff = diam_data.get('last_logoff', 'N/A')
    
    lines = []
    lines.append(f"The client's name is {full_name} with the username {diam_data.get('username', 'N/A')}.")
    if service_plan != 'N/A': lines.append(f"They are currently on the {service_plan} plan.")
    if status == 'ONLINE': lines.append("The account is currently online.")
    else: lines.append("The account is currently offline.")
    if account_status == True: lines.append(f"The account has expired {days_info} days ago on {expiry_date}.")
    elif account_status == 'expiring_soon': lines.append(f"The account will expire in {days_info} days on {expiry_date}.")
    else: lines.append(f"The account is active and will expire on {expiry_date}.")
    if cpe_ip != 'N/A': lines.append(f"The CPE IP address is {cpe_ip} and it {'is' if ping_reachable else 'is not'} reachable via ping.")
    if phone != 'N/A': lines.append(f"The phone number on file is {phone}.")
    if address != 'N/A': lines.append(f"The registered address is {address}.")
    if last_logoff != 'N/A': lines.append(f"The last logoff was recorded on {last_logoff}.")
    return " ".join(lines)

def set_token():
    global API_TOKEN
    token_file = os.path.expanduser("~/.minitron_token")
    if os.path.exists(token_file):
        with open(token_file, 'r') as f: saved_token = f.read().strip()
        use_saved = input("Use saved token? (y/n): ").lower()
        if use_saved == 'y': API_TOKEN = saved_token; return
    API_TOKEN = input("Enter API token: ").strip()
    save = input("Save token for future use? (y/n): ").lower()
    if save == 'y':
        with open(token_file, 'w') as f: f.write(API_TOKEN)
        os.chmod(token_file, 0o600)

def switch_server():
    global CURRENT_SERVER
    print(f"\nAvailable servers:")
    for name, url in API_SERVERS.items():
        marker = " <-- CURRENT" if name == CURRENT_SERVER else ""
        print(f"  {name}: {url}{marker}")
    choice = input("Switch to (cloud/lan): ").strip().lower()
    if choice in API_SERVERS:
        CURRENT_SERVER = choice
        print(f"Switched to {choice}: {API_SERVERS[choice]}")
    else:
        print("Invalid server")

def get_api_url():
    return API_SERVERS.get(CURRENT_SERVER, API_SERVERS["cloud"])

def api_get(endpoint, timeout=200):
    if not API_TOKEN: return None
    url = f"{get_api_url()}{endpoint}"
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code == 401: print("Invalid API token!"); return None
        elif response.status_code == 403: print("Access denied from this IP!"); return None
        elif response.status_code == 429: print("Rate limit exceeded."); return None
        elif response.status_code != 200: print(f"Error: {response.status_code}"); return None
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to {get_api_url()}")
        return None
    except Exception as e: print(f"Error: {e}"); return None

def search_username(username):
    return api_get(f"/search/{username}")

def get_traffic(username):
    return api_get(f"/traffic/{username}")

def get_traffic_stream(username, duration=60):
    """Stream live traffic for `duration` seconds."""
    print(f"Streaming traffic for {username} ({duration}s)...")
    return api_get(f"/traffic/stream/{username}", timeout=duration + 30)

def onu_scan(username):
    return api_get(f"/onu/scan?token={API_TOKEN}&username={username}", timeout=120)

def onu_wifi(username):
    return api_get(f"/onu/wifi?token={API_TOKEN}&username={username}", timeout=120)

def onu_change_wifi(username, new_ssid, new_password):
    if not API_TOKEN: return None
    url = f"{get_api_url()}/onu/wifi/change?token={API_TOKEN}"
    data = {"username": username, "ssid": new_ssid, "password": new_password}
    try:
        response = requests.post(url, json=data, timeout=120)
        if response.status_code != 200: return None
        return response.json()
    except: return None

def generate_initial_report(result):
    """Generate a structured initial report from raw API response using regex patterns."""
    if not result:
        return "❌ No data available."
    
    report_text = result.get('report', '')
    network = result.get('network_analysis', {})
    diam_data = network.get('diameter_data', {}) if network else {}
    
    # ---- Extract from diagnostic report text ----
    # Name
    name = "N/A"
    name_match = re.search(r'\*{0,2}([A-Za-z0-9_]+)\*{0,2}\s+identifies the', report_text)
    if not name_match:
        name_match = re.search(r'>\s*\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report_text)
    if not name_match:
        name_match = re.search(r'Analysis of\s+\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report_text)
    if name_match:
        name = name_match.group(1)
    
    # Device type & vendor
    device_vendor = "N/A"
    device_type = "N/A"
    vendor_match = re.search(r'\*{0,2}(ZTE|Huawei|Cdata|C-Data)\*{0,2}\s+\*{0,2}(GPON|EPON)\*{0,2}', report_text, re.IGNORECASE)
    if vendor_match:
        device_vendor = vendor_match.group(1)
        device_type = vendor_match.group(2).upper()
    else:
        # Try from Diameter MAC vendor
        mac_vendor = diam_data.get('mac_address', '')
        if 'huawei' in str(mac_vendor).lower() or 'goodman' in str(mac_vendor).lower():
            device_vendor = "Huawei"
    
    # Status
    status = result.get('status', 'N/A')
    status_text = "🟢 ONLINE" if status == 'online' else "🔴 OFFLINE"
    
    # Offline reason - check tron.json first, then regex fallback
    offline_reason = ""
    if status == 'offline':
        # Check port analysis from tron.json
        port = result.get('port_analysis', {})
        raw_debug = port.get('raw_debug_data') if port else None
        if raw_debug:
            db_match = find_port_analysis_match(raw_debug)
            if db_match:
                offline_reason = db_match
        
        # Regex fallback if no tron.json match
        if not offline_reason:
            if 'loss of signal' in report_text.lower() or 'LOS' in report_text:
                offline_reason = "Loss of Signal (LOS)"
            elif 'power failure' in report_text.lower() or 'dying gasp' in report_text.lower():
                offline_reason = "Power Failure (Dying Gasp)"
            elif 'pon port is currently down' in report_text.lower().replace('**',''):
                offline_reason = "PON Port Down (BTS Outage)"
            elif 'bts or olt' in report_text.lower():
                offline_reason = "BTS/OLT Down"
            else:
                offline_reason = "Unknown"
    
    # ---- Extract from Network Analysis ----
    cpe_ip = diam_data.get('cpe_ip', 'N/A')
    ping_reachable = diam_data.get('ping_reachable', False)
    ping_text = "🟢 Reachable" if ping_reachable else "🔴 Unreachable"
    
    service_plan = diam_data.get('service_plan', 'N/A')
    expiry_date = diam_data.get('expiry_date', 'N/A')
    account_status = diam_data.get('expired', False)
    status_account = "🔴 EXPIRED" if account_status else "🟢 Active"
    
    full_name = f"{diam_data.get('first_name', '')} {diam_data.get('last_name', '')}".strip()
    if not full_name or full_name == 'N/A N/A':
        full_name = diam_data.get('username', name)
    
    phone = diam_data.get('phone', 'N/A')
    address = diam_data.get('address', 'N/A')
    last_logoff = diam_data.get('last_logoff', 'N/A')
    
    # ---- Build Report ----
    lines = []
    lines.append("=" * 50)
    lines.append("📋 INITIAL REPORT")
    lines.append("=" * 50)
    lines.append(f"\n👤 Name: {name}")
    lines.append(f"📡 Device: {device_vendor} {device_type}")
    lines.append(f"📶 Status: {status_text}")
    if offline_reason:
        lines.append(f"   Reason: {offline_reason}")
    lines.append(f"\n🌐 Connection:")
    lines.append(f"   Ping (CPE IP): {ping_text} | via {cpe_ip}")
    lines.append(f"\n💳 Account:")
    lines.append(f"   Status: {status_account}")
    if expiry_date != 'N/A':
        lines.append(f"   Expires: {expiry_date}")
    if service_plan != 'N/A':
        lines.append(f"   Plan: {service_plan}")
    if full_name != name and full_name != 'N/A':
        lines.append(f"   Full Name: {full_name}")
    if phone != 'N/A':
        lines.append(f"   Phone: {phone}")
    if address != 'N/A':
        lines.append(f"   Address: {address}")
    if last_logoff != 'N/A':
        lines.append(f"   Last Logoff: {last_logoff}")
    lines.append("\n" + "=" * 50)
    
    return "\n".join(lines)

def generate_initial_report(result):
    """Generate a structured initial report from raw API response using regex patterns."""
    if not result:
        return "❌ No data available."
    
    report_text = result.get('report', '')
    network = result.get('network_analysis', {})
    diam_data = network.get('diameter_data', {}) if network else {}
    
    # ---- Extract from diagnostic report text ----
    # Name
    name = "N/A"
    name_match = re.search(r'\*{0,2}([A-Za-z0-9_]+)\*{0,2}\s+identifies the', report_text)
    if not name_match:
        name_match = re.search(r'>\s*\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report_text)
    if not name_match:
        name_match = re.search(r'Analysis of\s+\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report_text)
    if name_match:
        name = name_match.group(1)
    
    # Device type & vendor
    device_vendor = "N/A"
    device_type = "N/A"
    vendor_match = re.search(r'\*{0,2}(ZTE|Huawei|Cdata|C-Data)\*{0,2}\s+\*{0,2}(GPON|EPON)\*{0,2}', report_text, re.IGNORECASE)
    if vendor_match:
        device_vendor = vendor_match.group(1)
        device_type = vendor_match.group(2).upper()
    else:
        # Try from Diameter MAC vendor
        mac_vendor = diam_data.get('mac_address', '')
        if 'huawei' in str(mac_vendor).lower() or 'goodman' in str(mac_vendor).lower():
            device_vendor = "Huawei"
    
    # Status
    status = result.get('status', 'N/A')
    status_text = "🟢 ONLINE" if status == 'online' else "🔴 OFFLINE"
    
    # Offline reason - check tron.json first, then regex fallback
    offline_reason = ""
    if status == 'offline':
        # Check port analysis from tron.json
        port = result.get('port_analysis', {})
        raw_debug = port.get('raw_debug_data') if port else None
        if raw_debug:
            db_match = find_port_analysis_match(raw_debug)
            if db_match:
                offline_reason = db_match
        
        # Regex fallback if no tron.json match
        if not offline_reason:
            if 'loss of signal' in report_text.lower() or 'LOS' in report_text:
                offline_reason = "Loss of Signal (LOS)"
            elif 'power failure' in report_text.lower() or 'dying gasp' in report_text.lower():
                offline_reason = "Power Failure (Dying Gasp)"
            elif 'pon port is currently down' in report_text.lower().replace('**',''):
                offline_reason = "PON Port Down (BTS Outage)"
            elif 'bts or olt' in report_text.lower():
                offline_reason = "BTS/OLT Down"
            else:
                offline_reason = "Unknown"
    
    # ---- Extract from Network Analysis ----
    cpe_ip = diam_data.get('cpe_ip', 'N/A')
    ping_reachable = diam_data.get('ping_reachable', False)
    ping_text = "🟢 Reachable" if ping_reachable else "🔴 Unreachable"
    
    service_plan = diam_data.get('service_plan', 'N/A')
    expiry_date = diam_data.get('expiry_date', 'N/A')
    account_status = diam_data.get('expired', False)
    status_account = "🔴 EXPIRED" if account_status else "🟢 Active"
    
    full_name = f"{diam_data.get('first_name', '')} {diam_data.get('last_name', '')}".strip()
    if not full_name or full_name == 'N/A N/A':
        full_name = diam_data.get('username', name)
    
    phone = diam_data.get('phone', 'N/A')
    address = diam_data.get('address', 'N/A')
    last_logoff = diam_data.get('last_logoff', 'N/A')
    
    # ---- Build Report ----
    lines = []
    lines.append("=" * 50)
    lines.append("📋 INITIAL REPORT")
    lines.append("=" * 50)
    lines.append(f"\n👤 Name: {name}")
    lines.append(f"📡 Device: {device_vendor} {device_type}")
    lines.append(f"📶 Status: {status_text}")
    if offline_reason:
        lines.append(f"   Reason: {offline_reason}")
    lines.append(f"\n🌐 Connection:")
    lines.append(f"   Ping (CPE IP): {ping_text} | via {cpe_ip}")
    lines.append(f"\n💳 Account:")
    lines.append(f"   Status: {status_account}")
    if expiry_date != 'N/A':
        lines.append(f"   Expires: {expiry_date}")
    if service_plan != 'N/A':
        lines.append(f"   Plan: {service_plan}")
    if full_name != name and full_name != 'N/A':
        lines.append(f"   Full Name: {full_name}")
    if phone != 'N/A':
        lines.append(f"   Phone: {phone}")
    if address != 'N/A':
        lines.append(f"   Address: {address}")
    if last_logoff != 'N/A':
        lines.append(f"   Last Logoff: {last_logoff}")
    lines.append("\n" + "=" * 50)
    
    return "\n".join(lines)

def check_signal_quality(report):
    report_lower = report.lower()
    if re.search(r'signal:\s*\*{0,2}good\*{0,2}', report_lower): return 'good'
    if re.search(r'signal:\s*\*{0,2}poor\*{0,2}', report_lower): return 'poor'
    if re.search(r'signal:\s*\*{0,2}marginal\*{0,2}', report_lower): return 'marginal'
    return 'unknown'

def extract_onu_info(result):
    info = {"session_ip":"N/A","device_name":"N/A","device_vendor":"N/A","device_type":"N/A","status":"N/A","board":"N/A","port":"N/A","olt_name":"N/A","serial_number":"N/A"}
    if not result: return info
    report = result.get('report','')
    network = result.get('network_analysis')
    diam_data = network.get('diameter_data',{}) if network else {}
    info["session_ip"] = diam_data.get('cpe_ip', diam_data.get('session_ip','N/A'))
    info["status"] = result.get('status','N/A')
    name_match = re.search(r'\*{0,2}([A-Za-z0-9_]+)\*{0,2}\s+(?:identifies the|is currently|is currently utilizing a)', report)
    if not name_match: name_match = re.search(r'Analysis of\s+\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report)
    if name_match: info["device_name"] = name_match.group(1)
    vendor_type_match = re.search(r'\*{0,2}(ZTE|Huawei|Cdata|C\-Data)\*{0,2}\s+\*{0,2}(GPON|EPON|Epon|Gpon)\*{0,2}', report, re.IGNORECASE)
    if vendor_type_match: info["device_vendor"] = vendor_type_match.group(1); info["device_type"] = vendor_type_match.group(2).upper()
    sn_match = re.search(r'SN:\s*\*{0,2}([A-Za-z0-9.]+)\*{0,2}', report)
    if sn_match: info["serial_number"] = sn_match.group(1)
    board_match = re.search(r'Board\s+\*{0,2}(\d+)\*{0,2}', report)
    if board_match: info["board"] = board_match.group(1)
    port_match = re.search(r'Port\s+\*{0,2}(\d+)\*{0,2}', report)
    if port_match: info["port"] = port_match.group(1)
    olt_match = re.search(r'\*{0,2}OLT\*{0,2}:\s*(.+?)(?:\n|\*|$)', report)
    if olt_match: info["olt_name"] = olt_match.group(1).strip()
    if info["device_name"] == "N/A":
        sel_name = re.search(r'Analysis of\s+\*{0,2}([A-Za-z0-9_]+)\*{0,2}', report)
        if sel_name: info["device_name"] = sel_name.group(1)
    if info["port"] == "N/A":
        sel_port = re.search(r'Port:\s*\*{0,2}(\d+)\*{0,2}', report)
        if sel_port: info["port"] = sel_port.group(1)
    if info["device_name"] == "N/A":
        cdata_name = re.search(r'\*{0,2}([A-Za-z0-9_]+)\*{0,2}\s+(?:EPON|GPON)\s+device', report)
        if cdata_name: info["device_name"] = cdata_name.group(1)
    if info["device_type"] == "N/A":
        cdata_type = re.search(r'(EPON|GPON)\s+device', report, re.IGNORECASE)
        if cdata_type: info["device_type"] = cdata_type.group(1).upper()
    if info["port"] == "N/A":
        cdata_port = re.search(r'Port\s+(\d+)', report)
        if cdata_port: info["port"] = cdata_port.group(1)
    return info

def format_response(result, account_status_only=False):
    if not result: return "No response was received from the API."
    source = result.get('source','unknown'); status = result.get('status','unknown')
    report = result.get('report',''); network = result.get('network_analysis')
    port = result.get('port_analysis'); report_lower = report.lower()
    diam_data = network.get('diameter_data',{}) if network else {}
    expiry_date = diam_data.get('expiry_date','N/A')
    account_status, days_info = check_account_expired(expiry_date)
    
    if account_status_only:
        return format_account_status_from_raw(result) if diam_data else "No account data found."
    if source == 'diameter' and status == 'not_found':
        return "The username does not exist in our database. Please verify and try again." if 'does not exist' in report_lower else report
    if source == 'none' or status == 'not_found':
        return "Could not find this username in any system. Ask client for photo of router sticker."
    
    is_radio = ('ubnt' in report_lower or 'cambium' in report_lower or 'radio client' in report_lower)
    if is_radio:
        ping_reachable = diam_data.get('ping_reachable', False)
        expiry_msg = f" Account expired {days_info} days ago." if account_status == True else (f" Expires in {days_info} days." if account_status == 'expiring_soon' else "")
        if ping_reachable: return f"Radio device is online and reachable. Check LAN cable from PoE to router.{expiry_msg}"
        else: return f"Radio device is offline. Verify both LAN cables to PoE. Wait 5 min. Escalate if still down.{expiry_msg}"
    
    if source == 'diameter_gpon':
        return "Cannot determine connection type. Ask client for GPON serial number (starts with ZTE, HWTC, or ALCL)."
    
    if source in ['csv_olt', 'selenium', 'cdata']:
        if 'olt is currently down' in report_lower or 'bts or olt' in report_lower:
            return "General downtime at client location. Base station is down."
        if 'pon port is currently down' in report_lower.replace('**',''):
            return "General downtime. PON port serving this area is down."
        
        if status == 'online':
            signal = check_signal_quality(report); ping = diam_data.get('ping_reachable', False)
            if account_status == True:
                return f"Connection up but account expired {days_info} days ago. Client needs renewal." if signal == 'good' else f"Poor signal and account expired {days_info} days ago. Needs technician + renewal."
            exp_warn = f" Expires in {days_info} days." if account_status == 'expiring_soon' else ""
            if signal == 'good':
                return f"Connection up with good signal. CPE {'reachable' if ping else 'not reachable'}.{exp_warn}"
            elif signal in ['poor','marginal']:
                return f"Online but poor signal. Technician visit needed.{exp_warn}"
            else:
                return f"Connection appears up. CPE {'reachable' if ping else 'not reachable'}.{exp_warn}"
        
        if status == 'offline':
            exp_note = f" Account expired {days_info} days ago." if account_status == True else (f" Expires in {days_info} days." if account_status == 'expiring_soon' else "")
            if port:
                raw_debug = port.get('raw_debug_data')
                if raw_debug:
                    db_match = find_port_analysis_match(raw_debug)
                    if db_match: return f"{db_match}{exp_note}"
                raw_flags = port.get('raw_flags',{})
                if raw_flags.get('MST',0) == 1: return f"Multiple clients affected. Possible MST/splitter issue.{exp_note}"
                if raw_flags.get('MPI',0) == 1: return f"Major port issue affecting multiple clients.{exp_note}"
            if 'loss of signal' in report_lower: return f"Offline due to LOS. Raise support ticket for technician.{exp_note}"
            elif 'power failure' in report_lower or 'dying gasp' in report_lower: return f"Offline due to power failure. Confirm power at location.{exp_note}"
            else: return f"ONU is offline. Investigate cause.{exp_note}"
    
    if status == 'error': return f"Error: {report}"
    return "Check raw response for details."

def display_initial_report(result):
    """Display the initial structured report."""
    if not result:
        print("No data available.")
        return
    print(generate_initial_report(result))

def display_initial_report(result):
    """Display the initial structured report."""
    if not result:
        print("No data available.")
        return
    print(generate_initial_report(result))

def display_result(result, account_status_only=False):
    if not result: return
    print("\n" + "=" * 60)
    print(f"Server: {CURRENT_SERVER} | Source: {result.get('source','unknown')} | Status: {result.get('status','unknown')}")
    print("=" * 60)
    formatted = format_response(result, account_status_only)
    print(f"\n{formatted}")
    if not account_status_only:
        account = format_account_status_from_raw(result)
        if account: print(f"\n--- Account Details ---\n{account}")
    if result.get('source') in ['csv_olt','selenium','cdata']:
        info = extract_onu_info(result)
        print(f"\n--- Device Info ---")
        print(f"Device: {info['device_name']} | Vendor: {info['device_vendor']} | Type: {info['device_type']}")
        print(f"Status: {info['status']} | OLT: {info['olt_name']} | Board: {info['board']} | Port: {info['port']}")
        print(f"Serial: {info['serial_number']} | CPE IP: {info['session_ip']}")
    print("\n" + "-" * 40)
    print("Raw API Response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)

def display_traffic_live(username, duration=60):
    """Poll traffic every 2 seconds, printing live."""
    import time as time_mod
    print(f"\n📈 Live Traffic — {username} (polling every 2s for {duration}s)")
    print(f"{'Time':<10} {'Input Mbps':>12} {'Output Mbps':>12}")
    print("-" * 40)
    deadline = time_mod.time() + duration
    samples = []
    while time_mod.time() < deadline:
        result = get_traffic(username)
        if result and result.get('success'):
            t = time_mod.strftime('%H:%M:%S')
            inp = result.get('input_mbps', 0)
            out = result.get('output_mbps', 0)
            print(f"{t:<10} {inp:>12.3f} {out:>12.3f}")
            samples.append({'input_mbps': inp, 'output_mbps': out})
        else:
            print(f"{time_mod.strftime('%H:%M:%S'):<10} {'ERR':>12} {'ERR':>12}")
        time_mod.sleep(2)
    if samples:
        avg_in = sum(s['input_mbps'] for s in samples) / len(samples)
        avg_out = sum(s['output_mbps'] for s in samples) / len(samples)
        print("-" * 40)
        print(f"{'AVERAGE':<10} {avg_in:>12.3f} {avg_out:>12.3f}")

def display_traffic_result(result):
    if not result or not result.get('success'):
        print(f"Traffic check failed: {result.get('error','Unknown error') if result else 'No response'}")
        return
    # Single snapshot
    if 'input_mbps' in result:
        print(f"\n📈 Live Traffic — {result.get('name','N/A')}")
        print(f"OLT: {result.get('olt','N/A')} | {result.get('onu_type','N/A')} | Port {result.get('port','N/A')} | ONU {result.get('onu_id','N/A')}")
        print(f"📥 Input:  {result.get('input_mbps',0):.3f} Mbps ({result.get('input_bps',0)} bps)")
        print(f"📤 Output: {result.get('output_mbps',0):.3f} Mbps ({result.get('output_bps',0)} bps)")
    # Stream (multiple samples)
    elif 'samples' in result:
        samples = result.get('samples', [])
        print(f"\n📈 Traffic Stream — {result.get('name','N/A')} ({len(samples)} samples over {result.get('duration',60)}s)")
        print(f"OLT: {result.get('olt','N/A')} | {result.get('onu_type','N/A')}")
        print(f"{'Time':<20} {'Input Mbps':>12} {'Output Mbps':>12}")
        print("-" * 48)
        for s in samples:
            t = s.get('timestamp','')[-12:].split('.')[0]
            print(f"{t:<20} {s.get('input_mbps',0):>12.3f} {s.get('output_mbps',0):>12.3f}")
        if samples:
            avg_in = sum(s['input_mbps'] for s in samples) / len(samples)
            avg_out = sum(s['output_mbps'] for s in samples) / len(samples)
            print("-" * 48)
            print(f"{'AVERAGE':<20} {avg_in:>12.3f} {avg_out:>12.3f}")

def display_onu_scan_result(result):
    if not result or not result.get('success'): print(f"Scan failed: {result.get('error','Unknown') if result else 'No response'}"); return
    devices = result.get('devices',[]); ctx = result.get('device_context',{})
    print(f"\nScan for {ctx.get('smartolt_name','N/A')} ({ctx.get('cpe_ip','N/A')})")
    print(f"Found {result.get('total_count',0)} devices: {result.get('online_count',0)} online")
    for d in devices:
        status = "Online" if d.get('status') == 'Online' else "Offline"
        print(f"  {status} | {d.get('hostname','Unknown')[:25]} | {d.get('ip','N/A')} | {d.get('mac','N/A')}")

def display_onu_wifi_result(result):
    if not result or not result.get('success'): print(f"Failed: {result.get('error','Unknown') if result else 'No response'}"); return
    ctx = result.get('device_context',{})
    print(f"\nWiFi for {ctx.get('smartolt_name','N/A')} ({ctx.get('cpe_ip','N/A')})")
    print(f"SSID: {result.get('ssid','N/A')}\nPassword: {result.get('password','N/A')}")

def display_onu_change_wifi_result(result):
    if not result or not result.get('success'): print(f"Failed: {result.get('error','Unknown') if result else 'No response'}"); return
    ctx = result.get('device_context',{})
    print(f"\nWiFi changed for {ctx.get('smartolt_name','N/A')} ({ctx.get('cpe_ip','N/A')})")
    if result.get('ssid_changed'): print(f"New SSID: {result.get('new_ssid','N/A')}")
    if result.get('password_changed'): print(f"New Password: {result.get('new_password','N/A')}")

def main():
    print("=" * 50)
    print("MINITRON API Client")
    print("=" * 50)
    load_port_analysis_db()
    set_token()
    if not API_TOKEN: print("No token provided. Exiting."); sys.exit(1)
    print(f"\nServer: {CURRENT_SERVER} ({get_api_url()})")
    print("Commands: name, name/report, name/status, name/traffic, name/live, name/stream, name/scan, name/wifi, name/wifi/change, server, quit, token\n")
    while True:
        try:
            user_input = input("Enter username: ").strip()
            if user_input.lower() == 'quit': print("Goodbye!"); break
            if user_input.lower() == 'token': set_token(); continue
            if user_input.lower() == 'server': switch_server(); continue
            if not user_input: continue
            
            account_only = False; action_scan = False; action_wifi = False
            action_change = False; action_traffic = False; action_stream = False; action_live = False; action_report = False; search_name = user_input
            
            if '/' in user_input:
                parts = user_input.rsplit('/', 2)
                search_name = parts[0]
                cmd = parts[1].lower() if len(parts) >= 2 else ''
                if cmd == 'status': account_only = True
                elif cmd == 'report': action_report = True
                elif cmd == 'traffic': action_traffic = True
                elif cmd == 'stream': action_traffic = True; action_stream = True
                elif cmd == 'live': action_traffic = True; action_live = True
                elif cmd == 'scan': action_scan = True
                elif cmd == 'wifi':
                    if len(parts) == 3 and parts[2].lower() == 'change': action_change = True
                    else: action_wifi = True
            
            if action_report:
                result = search_username(search_name)
                if result: display_initial_report(result)
                else: print("No results found.")
            elif action_scan: display_onu_scan_result(onu_scan(search_name))
            elif action_traffic:
                if action_live:
                    display_traffic_live(search_name)
                elif action_stream:
                    display_traffic_result(get_traffic_stream(search_name))
                else:
                    display_traffic_result(get_traffic(search_name))
            elif action_wifi: display_onu_wifi_result(onu_wifi(search_name))
            elif action_change:
                ssid = input("New SSID (blank to keep): ").strip() or None
                pw = input("New Password (blank to keep): ").strip() or None
                if pw and len(pw) < 8: print("Password must be at least 8 characters.")
                else: display_onu_change_wifi_result(onu_change_wifi(search_name, ssid, pw))
            else:
                result = search_username(search_name)
                if result: display_result(result, account_only)
                else: print("No results found or an error occurred.")
        except KeyboardInterrupt: print("\nGoodbye!"); break

if __name__ == "__main__":
    main()
