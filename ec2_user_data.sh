#!/bin/bash
# EC2 User Data Script (Ubuntu)
# Paste this into EC2 Launch Configuration -> Advanced -> User Data
# This will run automatically when the instance starts

# Update system packages
apt update
apt upgrade -y

# Install prerequisites
apt install -y git software-properties-common

# Add deadsnakes PPA for Python 3.11
add-apt-repository -y ppa:deadsnakes/ppa
apt update

# Install Python 3.11 and pip
apt install -y python3.11 python3.11-pip python3.11-venv

# Create symlinks for python3 and pip3 to point to 3.11
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

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

