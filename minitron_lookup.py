#!/usr/bin/env python3
"""
MINITRON Lookup Module - All API functions importable
Supports: lookup, initial_report, onu_traffic, onu_scan, onu_wifi, onu_change_wifi
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import minitron_client

minitron_client.load_port_analysis_db()

def _auto_load_token():
    if not minitron_client.API_TOKEN:
        token_file = os.path.expanduser("~/.minitron_token")
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                minitron_client.API_TOKEN = f.read().strip()

# ============ LOOKUP (Diagnostic) ============
def lookup(username):
    """
    Full diagnostic lookup. Returns formatted sentence response.
    
    Possible returns (strings):
    - "The client's connection is up and running with good signal strength..."
    - "The client's connection is online but the signal strength is poor..."
    - "The client's ONU is offline due to loss of signal..."
    - "The client's ONU is offline due to a power failure..."
    - "There is currently a general downtime affecting the client's location..."
    - "Multiple clients at this location are experiencing issues..."
    - "The client's radio device appears to be online and reachable..."
    - "I could not find this username in any of our systems..."
    - "The username you provided does not exist in our database..."
    - "❌ No API token configured..."
    - "❌ No results found or error occurred."
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return "❌ No API token configured. Run minitron_client.py once to set it."
    account_only = False
    search_name = username
    if '/' in username:
        parts = username.rsplit('/', 1)
        search_name = parts[0]
        if parts[1].lower() == 'status':
            account_only = True
    result = minitron_client.search_username(search_name)
    if not result:
        return "❌ No results found or error occurred."
    return minitron_client.format_response(result, account_only)

# ============ INITIAL REPORT ============
def initial_report(username):
    """
    Structured initial report with name, device, status, account details.
    
    Possible returns (string):
    ==================================================
    📋 INITIAL REPORT
    ==================================================
    
    👤 Name: IKECHUKWU_ABILI
    📡 Device: Huawei GPON
    📶 Status: 🔴 OFFLINE
       Reason: Loss of Signal (LOS)
    
    🌐 Connection:
       Ping (CPE IP): 🔴 Unreachable | via 102.22.221.43
    
    💳 Account:
       Status: 🟢 Active
       Expires: 2026-08-27
       Plan: FibreHome-OutsideLagos
       Full Name: Ikechukwu Abili
       Phone: 08012345678
       Address: 123 Main Street
       Last Logoff: 2026-07-25 10:30:00
    ==================================================
    
    Or: "❌ No API token configured."
    Or: "❌ No results found or error occurred."
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return "❌ No API token configured."
    result = minitron_client.search_username(username)
    if not result:
        return "❌ No results found or error occurred."
    return minitron_client.generate_initial_report(result)

# ============ ONU EXTRACT ============
def onu_extract(username):
    """
    Extract ONU device information.
    
    Possible returns (dict):
    {
        "session_ip": "102.22.221.43",
        "device_name": "john_doe",
        "device_vendor": "ZTE",
        "device_type": "GPON",
        "status": "online",
        "board": "7",
        "port": "10",
        "olt_name": "SCHEME2 ZTE",
        "serial_number": "ZTEGC82E9D72"
    }
    Or: {"error": "No API token configured"}
    Or: {"error": "No results found"}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"error": "No API token configured"}
    result = minitron_client.search_username(username)
    if not result:
        return {"error": "No results found"}
    return minitron_client.extract_onu_info(result)

# ============ TRAFFIC ============
def onu_traffic(username):
    """
    Single traffic snapshot.
    
    Possible returns (dict):
    {
        "success": True,
        "name": "john_doe",
        "olt": "SCHEME2 ZTE",
        "onu_type": "GPON",
        "board": "1",
        "port": "7",
        "onu_id": "10",
        "input_bps": 25000,
        "output_bps": 1800000,
        "input_mbps": 0.25,
        "output_mbps": 18.0
    }
    Or: {"success": False, "error": "No API token configured"}
    Or: {"success": False, "error": "User not found"}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    return minitron_client.get_traffic(username)

def onu_traffic_stream(username):
    """
    60-second traffic stream (all samples at once).
    
    Possible returns (dict):
    {
        "success": True,
        "samples": [
            {"timestamp": "...", "input_mbps": 0.25, "output_mbps": 18.0, ...},
            ...30 samples...
        ],
        "count": 30,
        "duration": 60,
        "name": "john_doe",
        "olt": "SCHEME2 ZTE"
    }
    Or: {"success": False, "error": "..."}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    return minitron_client.get_traffic_stream(username)

def onu_traffic_live(username, duration=60):
    """
    Live traffic - prints each sample as it arrives. Returns summary dict.
    Prints to stdout in real-time, returns averages at end.
    
    Prints:
    📈 Live Traffic — john_doe (polling every 2s for 60s)
    Time        Input Mbps  Output Mbps
    ----------------------------------------
    18:36:41        0.236       11.647
    18:36:43        0.651       68.997
    ...
    AVERAGE        0.154        9.460
    
    Returns (dict):
    {"success": True, "samples": 30, "avg_input_mbps": 0.154, "avg_output_mbps": 9.460}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    minitron_client.display_traffic_live(username, duration)
    return {"success": True, "message": "Live traffic complete"}

# ============ ONU SCAN ============
def onu_scan(username):
    """
    Scan devices connected to client's router.
    
    Possible returns (dict):
    {
        "success": True,
        "devices": [
            {"hostname": "iPhone", "ip": "192.168.1.5", "mac": "aa:bb:cc:dd:ee:ff", "status": "Online"},
            ...
        ],
        "total_count": 5,
        "online_count": 3,
        "device_context": {"smartolt_name": "john_doe", "cpe_ip": "102.22.221.43", ...}
    }
    Or: {"success": False, "error": "No API token configured"}
    Or: {"success": False, "error": "Could not find device"}
    Or: {"success": False, "error": "CPE IP not found"}
    Or: {"success": False, "error": "Failed to login to router"}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    return minitron_client.onu_scan(username)

# ============ ONU WIFI ============
def onu_wifi(username):
    """
    Get WiFi settings from client's router.
    
    Possible returns (dict):
    {
        "success": True,
        "ssid": "JohnWiFi",
        "password": "Password123",
        "device_context": {"smartolt_name": "john_doe", "cpe_ip": "102.22.221.43", ...}
    }
    Or: {"success": False, "error": "No API token configured"}
    Or: {"success": False, "error": "Failed to login to router"}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    return minitron_client.onu_wifi(username)

# ============ ONU CHANGE WIFI ============
def onu_change_wifi(username, new_ssid=None, new_password=None):
    """
    Change WiFi SSID/password on client's router.
    
    Possible returns (dict):
    {
        "success": True,
        "ssid_changed": True,
        "password_changed": True,
        "new_ssid": "NewWiFi",
        "new_password": "NewPass123",
        "device_context": {...}
    }
    Or: {"success": False, "error": "No API token configured"}
    Or: {"success": False, "error": "Failed to login to router"}
    """
    _auto_load_token()
    if not minitron_client.API_TOKEN:
        return {"success": False, "error": "No API token configured"}
    return minitron_client.onu_change_wifi(username, new_ssid, new_password)

# ============ ACCOUNT STATUS ============
def account_status(username):
    """
    Get account status only (no diagnostic).
    
    Returns (string):
    "The client's name is John Doe with the username john_doe. 
     They are currently on the FiberMax Home Extra plan. 
     The account is currently online. 
     The account is active and will expire on 2026-08-27. 
     The CPE IP address is 102.22.221.43 and it is reachable via ping. 
     The phone number on file is 08178251908. 
     The registered address is 123 Main Street. 
     The last logoff was recorded on 2026-07-28 19:36:49."
    """
    return lookup(f"{username}/status")

# ============ CLI ============
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python minitron_lookup.py <username>              - Full diagnostic")
        print("  python minitron_lookup.py <username>/report       - Initial report")
        print("  python minitron_lookup.py <username>/status       - Account status")
        print("  python minitron_lookup.py <username>/extract      - ONU device info")
        print("  python minitron_lookup.py <username>/traffic      - Traffic snapshot")
        print("  python minitron_lookup.py <username>/stream       - 60s traffic stream")
        print("  python minitron_lookup.py <username>/live         - Live traffic (prints real-time)")
        print("  python minitron_lookup.py <username>/scan         - Scan router devices")
        print("  python minitron_lookup.py <username>/wifi         - Get WiFi settings")
        print("  python minitron_lookup.py <username>/wifi/change  - Change WiFi")
        print()
        print("Import usage:")
        print("  from minitron_lookup import lookup, initial_report, onu_traffic, onu_traffic_live, onu_scan, onu_wifi, onu_change_wifi")
        sys.exit(0)
    
    arg = sys.argv[1]
    
    if arg.endswith('/report'):
        print(initial_report(arg[:-7]))
    elif arg.endswith('/status'):
        print(account_status(arg[:-7]))
    elif arg.endswith('/live'):
        onu_traffic_live(arg[:-5])
    elif arg.endswith('/stream'):
        result = onu_traffic_stream(arg[:-7])
        print(json.dumps(result, indent=2, default=str))
    elif arg.endswith('/traffic'):
        result = onu_traffic(arg[:-8])
        print(json.dumps(result, indent=2, default=str))
    elif arg.endswith('/extract'):
        result = onu_extract(arg[:-8])
        print(json.dumps(result, indent=2, default=str))
    elif arg.endswith('/wifi/change'):
        username = arg[:-12]
        ssid = input("New SSID (blank to skip): ").strip() or None
        pw = input("New Password (blank to skip): ").strip() or None
        result = onu_change_wifi(username, ssid, pw)
        print(json.dumps(result, indent=2, default=str))
    elif arg.endswith('/wifi'):
        result = onu_wifi(arg[:-5])
        print(json.dumps(result, indent=2, default=str))
    elif arg.endswith('/scan'):
        result = onu_scan(arg[:-5])
        print(json.dumps(result, indent=2, default=str))
    else:
        print(lookup(arg))
