# EC2 Deployment Guide for Daily Stock Update

This guide explains how to deploy the daily stock update script to AWS EC2 using Git.

## Initial Git Repository Setup

Before deploying, make sure your code is in a Git repository:

1. **Initialize Git repository** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Push to GitHub/GitLab**:
   ```bash
   # Create a new repository on GitHub/GitLab, then:
   git remote add origin https://github.com/yourusername/tradingAssistant.git
   git push -u origin main
   ```

3. **Verify .gitignore** is working (`.env` and `logs/` should NOT be committed):
   ```bash
   git status  # Should not show .env or logs/
   ```

## Prerequisites

- AWS EC2 instance (t3.micro or t3.small recommended for cost optimization)
- SSH access to the EC2 instance
- Git repository (GitHub, GitLab, etc.) with your code
- Database credentials configured

## Quick Start

### 1. Launch EC2 Instance

- Instance type: **t3.micro** (free tier eligible) or **t3.small**
- OS: Amazon Linux 2 or Ubuntu 22.04 LTS
- Storage: 8GB minimum
- Security Group: Allow SSH (port 22) from your IP

### 2. Initial Setup (One-time)

SSH into your EC2 instance and run:

```bash
# Copy setup script to EC2
scp setup_ec2.sh ec2-user@YOUR_EC2_IP:~/

# SSH into EC2
ssh ec2-user@YOUR_EC2_IP

# Run setup script
chmod +x setup_ec2.sh
./setup_ec2.sh
```

### 3. Clone Git Repository

**Option A: Using deploy script (recommended)**

From your local machine:

```bash
# Make deploy script executable
chmod +x deploy_to_ec2.sh

# First time deployment (clones repo)
./deploy_to_ec2.sh ec2-user@YOUR_EC2_IP https://github.com/yourusername/tradingAssistant.git
```

**Option B: Manual clone on EC2**

SSH into EC2 and clone:

```bash
ssh ec2-user@YOUR_EC2_IP
cd ~
git clone https://github.com/yourusername/tradingAssistant.git tradingAssistant
# OR for private repo with SSH:
git clone git@github.com:yourusername/tradingAssistant.git tradingAssistant
```

### 4. Configure Environment Variables

SSH into EC2 and create `.env` file:

```bash
ssh ec2-user@YOUR_EC2_IP
cd ~/tradingAssistant
nano .env
```

Add your database credentials:

```
DB_HOST=your-database-host
DB_PORT=5432
DB_NAME=financialDB1
DB_USER=your_username
DB_PASSWORD=your_password
```

### 5. Install Dependencies

```bash
cd ~/tradingAssistant
pip3 install --user -r requirements.txt
```

### 6. Test the Script

```bash
cd ~/tradingAssistant
python3 run_daily_update_ec2.py
```

### 7. Set Up Cron Job

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM UTC):
0 2 * * * cd ~/tradingAssistant && /usr/bin/python3 run_daily_update_ec2.py >> logs/cron.log 2>&1
```

## File Structure on EC2

```
~/tradingAssistant/
├── daily_update_stocks.py      # Main script (unchanged)
├── store_stock_data.py         # Database utilities
├── run_daily_update_ec2.py     # EC2 wrapper script
├── requirements.txt            # Python dependencies
├── .env                        # Database credentials (create this)
└── logs/                       # Log files directory
    ├── daily_update_*.log
    ├── corporate_actions_*.log
    └── cron.log
```

## Monitoring

### View Recent Logs

```bash
# View latest daily update log
ls -lt ~/tradingAssistant/logs/daily_update_*.log | head -1 | xargs tail -f

# View cron execution log
tail -f ~/tradingAssistant/logs/cron.log
```

### Check Cron Job Status

```bash
# List cron jobs
crontab -l

# Check if cron service is running
sudo systemctl status crond  # Amazon Linux
# or
sudo systemctl status cron   # Ubuntu
```

## Cost Optimization Tips

1. **Use t3.micro**: ~$7/month (or free tier eligible)
2. **Stop instance when not needed**: If script runs <24/7, stop instance between runs
3. **Reserved Instances**: Save 40% with 1-year commitment
4. **Log rotation**: Configured automatically to prevent disk space issues

## Troubleshooting

### Script fails with "Module not found"

```bash
# Reinstall dependencies
cd ~/tradingAssistant
pip3 install --user -r requirements.txt
```

### Database connection errors

- Verify `.env` file has correct credentials
- Check security group allows connection from EC2 to database
- Test connection: `psql -h DB_HOST -U DB_USER -d DB_NAME`

### Cron job not running

- Check cron service: `sudo systemctl status crond`
- Verify cron job syntax: `crontab -l`
- Check cron logs: `tail -f ~/tradingAssistant/logs/cron.log`

### Out of memory errors

- Consider upgrading to t3.small (2GB RAM vs 1GB)
- Or reduce batch sizes in `daily_update_stocks.py`

## Manual Execution

To run the script manually:

```bash
cd ~/tradingAssistant
python3 run_daily_update_ec2.py
```

## Updating the Script

When you update your code:

1. **Commit and push to Git:**
   ```bash
   git add .
   git commit -m "Update daily update script"
   git push
   ```

2. **Deploy to EC2:**
   ```bash
   # From your local machine
   ./deploy_to_ec2.sh ec2-user@YOUR_EC2_IP
   ```
   
   Or manually on EC2:
   ```bash
   ssh ec2-user@YOUR_EC2_IP
   cd ~/tradingAssistant
   git pull
   pip3 install --user -r requirements.txt  # If requirements changed
   ```

No need to restart anything - cron will use the updated script on next run.

## Git Repository Setup

Make sure your repository includes:
- ✅ All Python files (daily_update_stocks.py, store_stock_data.py, etc.)
- ✅ requirements.txt
- ✅ setup_ec2.sh, deploy_to_ec2.sh
- ✅ env.example (template)
- ❌ .env file (excluded via .gitignore - contains secrets!)
- ❌ logs/ directory (excluded via .gitignore)

