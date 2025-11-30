#!/bin/bash
# Deployment script to update code on EC2 instance via Git
# Usage: ./deploy_to_ec2.sh user@ec2-instance-ip [repo-url]
#
# If repo-url is provided, it will clone the repo (first time setup)
# Otherwise, it will pull the latest changes from the existing repo

set -e  # Exit on error

if [ -z "$1" ]; then
    echo "Usage: $0 user@ec2-instance-ip [repo-url]"
    echo "Example (update existing): $0 ubuntu@44.200.137.210"
    echo "Example (first time): $0 ubuntu@44.200.137.210 https://github.com/username/tradingAssistant.git"
    exit 1
fi

EC2_HOST="$1"
REPO_URL="$2"
APP_DIR="~/tradingAssistant"

echo "=========================================="
echo "Deploying to EC2: $EC2_HOST"
echo "=========================================="

if [ -n "$REPO_URL" ]; then
    # First time setup - clone the repository
    echo "Cloning repository (first time setup)..."
    ssh "$EC2_HOST" "cd ~ && git clone $REPO_URL tradingAssistant"
    
    echo "Setting up .env file..."
    ssh "$EC2_HOST" "cd $APP_DIR && if [ ! -f .env ]; then cp env.example .env && echo '⚠️  Please edit .env file with your database credentials'; fi"
    
    echo "Running initial setup (if setup_ec2.sh exists)..."
    ssh "$EC2_HOST" "cd $APP_DIR && if [ -f setup_ec2.sh ]; then chmod +x setup_ec2.sh && ./setup_ec2.sh; fi"
else
    # Update existing repository
    echo "Pulling latest changes from Git..."
    ssh "$EC2_HOST" "cd $APP_DIR && git pull"
fi

# Make scripts executable
echo "Setting permissions..."
ssh "$EC2_HOST" "chmod +x $APP_DIR/run_daily_update_ec2.py"

# Install/update dependencies
echo "Installing/updating Python dependencies..."
ssh "$EC2_HOST" "cd $APP_DIR && pip3 install --user -r requirements.txt"

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Repository location: $APP_DIR"
echo ""
if [ -n "$REPO_URL" ]; then
    echo "⚠️  IMPORTANT: Set up .env file with database credentials:"
    echo "   ssh $EC2_HOST 'cd $APP_DIR && nano .env'"
    echo ""
fi
echo "Next steps:"
echo "1. Verify .env file is configured correctly"
echo "2. Test the script: ssh $EC2_HOST 'cd $APP_DIR && python3 run_daily_update_ec2.py'"
echo "3. Set up cron job (see cron_daily_update file)"
echo ""

