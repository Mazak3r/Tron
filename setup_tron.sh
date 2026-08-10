#!/bin/bash
# =============================================================================
# TRON Setup Script - Run once to create environment and install dependencies
# Usage: bash setup_tron.sh
# =============================================================================

set -e  # Exit on error

echo "========================================="
echo "  TRON - Environment Setup"
echo "========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Create virtual environment
if [ ! -d "tron_env" ]; then
    echo "Creating virtual environment 'tron_env'..."
    python3 -m venv tron_env
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate environment
source tron_env/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install required packages
echo "Installing required packages..."
pip install requests streamlit openai streamlit-js-eval

# Create secrets directory if it doesn't exist
if [ ! -d ".streamlit" ]; then
    mkdir -p .streamlit
    echo "✓ Created .streamlit directory"
fi

# Create secrets.toml template if it doesn't exist
if [ ! -f ".streamlit/secrets.toml" ]; then
    cat > .streamlit/secrets.toml << 'EOF'
# TRON Secrets Configuration
# Add your OpenAI API key below
OPENAI_API_KEY = "your-openai-api-key-here"
EOF
    echo "✓ Created secrets.toml template"
    echo "⚠️  Please edit .streamlit/secrets.toml and add your OpenAI API key"
fi

# Create minitron token file if it doesn't exist
if [ ! -f "$HOME/.minitron_token" ]; then
    echo "Enter your MINITRON API token (or press Enter to skip):"
    read -r minitron_token
    if [ -n "$minitron_token" ]; then
        echo "$minitron_token" > "$HOME/.minitron_token"
        echo "✓ MINITRON token saved"
    else
        echo "⚠️  MINITRON token not set. You can set it later."
    fi
fi

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "To run TRON:"
echo "  bash run_tron.sh"
echo ""
echo "Or manually:"
echo "  source tron_env/bin/activate"
echo "  streamlit run tron_app.py"
echo ""
