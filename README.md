# TRON — AI Fiber Support Agent

TRON is an AI-powered customer support agent for fiber optic ISPs. It connects to the **MINITRON NMS** (Network Management System) to retrieve real-time network data and uses **OpenAI GPT-4** to communicate naturally with customers.

## How It Works

Customer Chat → TRON (Streamlit) → OpenAI GPT-4 → Function Calls → MINITRON NMS
text

TRON receives a username, pulls a full diagnostic report from MINITRON, and caches everything in a single call. When customers ask questions, the AI decides which tools to use — scanning devices, checking traffic, managing WiFi — all through the MINITRON API.

## What It Can Do

| Capability | Description |
|------------|-------------|
| **Connection Diagnostics** | Detects online/offline status, LOS (Loss of Signal), poor signal, general downtime |
| **Live Traffic Monitoring** | 60-second bandwidth stream showing download/upload speeds and plan usage percentage |
| **WiFi Management** | View current SSID and password; change either or both remotely |
| **Device Scanning** | List all devices connected to the customer's network with hostname and IP |
| **Account Lookup** | Plan details, speed tier, subscription status, expiry date, pricing |
| **Plan Comparison** | Reference available plans with speeds and pricing for upgrades or renewals |

## Architecture

┌──────────────────────────────────────────────────┐
│ Streamlit UI │
│ (Customer Chat + Sidebar) │
├──────────────────────────────────────────────────┤
│ OpenAI GPT-4o │
│ (Natural language understanding) │
├──────────────────────────────────────────────────┤
│ Function Calling Layer │
│ refresh_report │ scan │ wifi │ change │ traffic │
├──────────────────────────────────────────────────┤
│ minitron_lookup.py │
│ lookup() initial_report() onu_scan() │
│ onu_wifi() onu_change_wifi() onu_traffic() │
│ onu_traffic_stream() onu_extract() │
├──────────────────────────────────────────────────┤
│ minitron_client.py │
│ (HTTP API client for MINITRON NMS) │
├──────────────────────────────────────────────────┤
│ MINITRON NMS │
│ (Network Management System - the source of │
│ all diagnostic, account, and device data) │
└──────────────────────────────────────────────────┘
text

## The MINITRON Connection

TRON gets its data through **MINITRON**, a command-line NMS client:

- **`minitron_client.py`** — Talks to the MINITRON API over HTTP. Operators type a username to get instant diagnostic answers: online/offline status, signal strength, account details, outage cause. Supports `/traffic` for bandwidth snapshots, `/live` for real-time graphs, `/scan` for router device lists, `/wifi` for password management. Token-based authentication.

- **`minitron_lookup.py`** — Wraps the client into importable Python functions: `lookup()`, `initial_report()`, `onu_traffic()`, `onu_traffic_stream()`, `onu_scan()`, `onu_wifi()`, `onu_change_wifi()`. Used by TRON to get diagnostic answers, traffic data, and manage routers programmatically.

## API Calls Per Session

| Call | Count | When |
|------|-------|------|
| `initial_report()` | 1 | Startup — caches everything |
| `onu_traffic_stream()` | 1 | Chat traffic request (60s block) |
| `onu_traffic()` | ~30 | Sidebar live monitor (every 2s) |
| `onu_scan()` | On demand | Device list request |
| `onu_wifi()` | On demand | WiFi credentials request |
| `onu_change_wifi()` | On demand | WiFi change request |

## Setup

### Prerequisites
- Python 3.10+
- Ubuntu/Debian
- MINITRON API token
- OpenAI API key

### Installation

```
cd tron

# Create virtual environment
python3 -m venv tron_env
source tron_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure OpenAI key
mkdir -p .streamlit
echo 'OPENAI_API_KEY = "your-key-here"' > .streamlit/secrets.toml

# Set MINITRON token
echo "your-minitron-token" > ~/.minitron_token

# Run
streamlit run tron_app.py --server.port=8501 --server.address=0.0.0.0
Quick Start Scripts

bash setup_tron.sh   # One-time environment setup
bash run_tron.sh     # Launch TRON


## Project Structure

tron/
├── tron_app.py              # Streamlit application
├── minitron_lookup.py       # Importable function wrappers
├── minitron_client.py       # MINITRON HTTP API client
├── plans.json               # ISP plans database
├── requirements.txt         # Python dependencies
├── setup_tron.sh            # Setup script
├── run_tron.sh              # Launch script
└── .streamlit/
    └── secrets.toml         # OpenAI API key (gitignored)

```

Environment Variables

Variable
Location
Purpose
OPENAI_API_KEY
.streamlit/secrets.toml
OpenAI authentication
MINITRON_TOKEN
~/.minitron_token
MINITRON NMS authentication

Supported Routers
Huawei GPON/EPON
ZTE GPON/EPON
Troubleshooting Flow

Issue
TRON Response
LOS / Red Light
Physical checks → Escalate to field tech
Slow Speed
Auto-start 60s traffic stream → Check devices → Check WiFi security
WiFi Issues
Scan devices → View/change credentials
Account Expired
Notify customer → Show plan options
General Downtime
Inform of known outage → No troubleshooting needed

License
MIT
