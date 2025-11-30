#!/bin/bash
# EC2 Setup Script - Run from within cloned repository

set -e

echo "Installing dependencies..."
sudo apt update || true
sudo apt install -y git python3-pip

echo "Setting up log rotation..."
APP_DIR="$HOME/tradingAssistant"
mkdir -p "$APP_DIR/logs"
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

echo "Setup complete. Next:"
echo "1. Create .env file: cp env.example .env && nano .env"
echo "2. Install dependencies: pip3 install --user -r requirements.txt"
echo "3. Set up cron: crontab -e"
