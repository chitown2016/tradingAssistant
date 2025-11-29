#!/bin/bash
# EC2 Setup Script for Daily Stock Update
# Run this script once when setting up a new EC2 instance

set -e  # Exit on error

echo "=========================================="
echo "EC2 Setup for Daily Stock Update"
echo "=========================================="

# Update system packages
echo "Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Git, Python 3.11+ and pip (Ubuntu)
echo "Installing Git, Python 3.11 and pip..."

# Update package list
sudo apt update

# Install prerequisites
sudo apt install -y git software-properties-common

# Add deadsnakes PPA for Python 3.11
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-distutils curl

# Install pip for Python 3.11 using get-pip.py
echo "Installing pip for Python 3.11..."
curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Create symlinks so python3 and pip3 point to 3.11
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

# Verify installations
echo ""
echo "Verifying installations:"
git --version
python3 --version
pip3 --version

# Verify Python version is 3.11+
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d'.' -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "⚠️  WARNING: Python version is $PYTHON_VERSION, not 3.11+"
    echo "   The script may still work, but Python 3.11+ is recommended"
else
    echo "✓ Python 3.11+ confirmed: $PYTHON_VERSION"
fi

# Create application directory
APP_DIR="$HOME/tradingAssistant"
echo "Creating application directory: $APP_DIR"
mkdir -p "$APP_DIR/logs"

# Set up log rotation
echo "Setting up log rotation..."
sudo tee /etc/logrotate.d/trading-assistant > /dev/null <<EOF
$APP_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 \$USER \$USER
}
EOF

# Make scripts executable
chmod +x "$APP_DIR/run_daily_update_ec2.py"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo "Next steps:"
echo "1. Clone your Git repository:"
echo "   cd ~ && git clone YOUR_REPO_URL tradingAssistant"
echo "   OR if using SSH:"
echo "   cd ~ && git clone git@github.com:USERNAME/REPO.git tradingAssistant"
echo ""
echo "2. Set up .env file with database credentials:"
echo "   cd $APP_DIR && cp env.example .env"
echo "   nano .env  # Add your database credentials"
echo ""
echo "3. Install Python dependencies:"
echo "   cd $APP_DIR && pip3 install --user -r requirements.txt"
echo ""
echo "4. Configure cron job (see cron_daily_update file)"
echo ""

