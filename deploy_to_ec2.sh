#!/bin/bash
# Deploy to EC2 - removes directory and does fresh clone
# Usage: ./deploy_to_ec2.sh ubuntu@ec2-ip [repo-url]

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 ubuntu@ec2-ip [repo-url]"
    exit 1
fi

EC2_HOST="$1"
REPO_URL="$2"
APP_DIR="~/tradingAssistant"

if [ -n "$REPO_URL" ]; then
    echo "Cloning repository..."
    ssh "$EC2_HOST" "cd ~ && rm -rf tradingAssistant && git clone $REPO_URL tradingAssistant"
else
    echo "Getting repo URL and doing fresh clone..."
    REPO_URL=$(ssh "$EC2_HOST" "cd $APP_DIR && git remote get-url origin" 2>/dev/null || echo "")
    if [ -z "$REPO_URL" ]; then
        echo "Error: Could not determine repo URL. Provide it as second argument."
        exit 1
    fi
    ssh "$EC2_HOST" "if [ -f $APP_DIR/.env ]; then cp $APP_DIR/.env ~/.env.backup; fi"
    ssh "$EC2_HOST" "cd ~ && rm -rf tradingAssistant && git clone $REPO_URL tradingAssistant"
    ssh "$EC2_HOST" "if [ -f ~/.env.backup ]; then cp ~/.env.backup $APP_DIR/.env && rm ~/.env.backup; fi"
fi

echo "Installing dependencies..."
ssh "$EC2_HOST" "cd $APP_DIR && pip3 install --user -r requirements.txt"

echo "Deployment complete!"
