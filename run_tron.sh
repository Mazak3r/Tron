#!/bin/bash
# =============================================================================
# TRON Run Script - Activates environment and launches TRON
# Usage: bash run_tron.sh
# =============================================================================

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -f "tron_env/bin/activate" ]; then
    source tron_env/bin/activate
    echo "✓ TRON environment activated"
else
    echo "❌ Virtual environment not found!"
    echo "Run setup first: bash setup_tron.sh"
    exit 1
fi

# Check for secrets
if [ ! -f ".streamlit/secrets.toml" ]; then
    echo "⚠️  Secrets file not found. Creating template..."
    mkdir -p .streamlit
    cat > .streamlit/secrets.toml << 'EOF'
OPENAI_API_KEY = "your-openai-api-key-here"
EOF
    echo "Please edit .streamlit/secrets.toml and add your OpenAI API key"
    exit 1
fi

# Check for MINITRON API
if [ ! -f "minitron_lookup.py" ]; then
    echo "⚠️  minitron_lookup.py not found in current directory"
    echo "Make sure it's in the same folder as tron_app.py"
fi

echo "========================================="
echo "  TRON - Starting..."
echo "========================================="
echo ""

# Run TRON
streamlit run tron_app.py --server.port=8501 --server.address=0.0.0.0
