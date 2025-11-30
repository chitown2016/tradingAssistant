#!/bin/bash
# EC2 User Data Script (Ubuntu)
# Paste this into EC2 Launch Configuration -> Advanced -> User Data
# This will run automatically when the instance starts

# Update system packages
apt update
apt upgrade -y

# Install Git and pip (Python 3.10 is already installed)
apt install -y git python3-pip

# Create application directory
APP_DIR="/home/ubuntu/tradingAssistant"
mkdir -p "$APP_DIR/logs"

# Set up log rotation
tee /etc/logrotate.d/trading-assistant > /dev/null <<EOF
$APP_DIR/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ubuntu ubuntu
}
EOF

# Note: Git clone and dependency installation should be done manually
# or via deploy_to_ec2.sh script after instance is running

