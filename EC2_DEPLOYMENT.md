# EC2 Deployment Guide

## Quick Setup

### 1. Launch EC2 Instance
- Instance: **t3.micro** (Ubuntu 22.04 LTS)
- Security Group: Allow SSH (port 22) from your IP

### 2. Clone Repository and Setup

```bash
# SSH into EC2
ssh ubuntu@YOUR_EC2_IP

# Clone repository
git clone YOUR_REPO_URL ~/tradingAssistant
cd ~/tradingAssistant

# Run setup
chmod +x setup_ec2.sh
./setup_ec2.sh

# Create .env file
cp env.example .env
nano .env  # Add database credentials

# Install dependencies
pip3 install --user -r requirements.txt
```

### 3. Set Up Cron Job

```bash
crontab -e

# Add this line (runs daily at 2 AM UTC):
0 2 * * * cd ~/tradingAssistant && /usr/bin/python3 run_daily_update_ec2.py >> logs/cron.log 2>&1
```

### 4. Test

```bash
cd ~/tradingAssistant
python3 run_daily_update_ec2.py
```

## Updating Code

**Option 1: Using deploy script (from local machine)**
```bash
./deploy_to_ec2.sh ubuntu@YOUR_EC2_IP
```

**Option 2: Manual (on EC2)**
```bash
cd ~/tradingAssistant
rm -rf *
git clone YOUR_REPO_URL .
# Restore .env if needed
pip3 install --user -r requirements.txt
```

## Monitoring

```bash
# View latest log
ls -lt ~/tradingAssistant/logs/daily_update_*.log | head -1 | xargs tail -f

# Check cron
crontab -l
```
