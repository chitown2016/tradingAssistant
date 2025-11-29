#!/bin/bash
# EC2 Setup Script for Daily Stock Update
# Run this script once when setting up a new EC2 instance

set -e  # Exit on error

echo "=========================================="
echo "EC2 Setup for Daily Stock Update"
echo "=========================================="

# Update system packages
echo "Updating system packages..."
sudo yum update -y

# Install Git, Python 3.11+ and pip
echo "Installing Git, Python 3.11 and pip..."
sudo yum install -y git python3 python3-pip

# Verify installations
git --version
python3 --version
pip3 --version

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

