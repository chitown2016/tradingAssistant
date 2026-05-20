#!/bin/bash
# Server setup for trading-assistant on Lightsail Ubuntu 24.04
# Idempotent: safe to re-run. Run as the default 'ubuntu' user.
#
# Env vars (optional):
#   REPO_URL  default: https://github.com/chitown2016/tradingAssistant.git
#   TZ        default: America/New_York

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/chitown2016/tradingAssistant.git}"
APP_DIR="$HOME/tradingAssistant"
DB_NAME="financialDB1"
DB_USER="trading"
TZ_DEFAULT="${TZ:-America/New_York}"

log()  { echo -e "\n>>> $*"; }
info() { echo "    $*"; }

# 1. System packages
log "Installing base system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv python3-pip curl gnupg lsb-release ca-certificates

# 2. PostgreSQL + TimescaleDB
log "Installing PostgreSQL + TimescaleDB"
sudo apt-get install -y -qq postgresql postgresql-contrib

if ! dpkg -l | grep -q timescaledb-2-postgresql; then
    curl -fsSL https://packagecloud.io/install/repositories/timescale/timescaledb/script.deb.sh \
        | sudo bash > /dev/null
    PG_VERSION=$(ls /etc/postgresql/ 2>/dev/null | head -1)
    PG_VERSION=${PG_VERSION:-16}
    sudo apt-get install -y -qq "timescaledb-2-postgresql-${PG_VERSION}"
    sudo timescaledb-tune --quiet --yes
    sudo systemctl restart postgresql
fi

# 3. Timezone
log "Setting timezone to $TZ_DEFAULT"
sudo timedatectl set-timezone "$TZ_DEFAULT"

# 4. Create DB + user (idempotent)
log "Creating database and user"
if [ ! -f "$HOME/.db_password" ]; then
    openssl rand -base64 24 | tr -d '=+/' | head -c 32 > "$HOME/.db_password"
    chmod 600 "$HOME/.db_password"
fi
DB_PASS=$(cat "$HOME/.db_password")

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
    CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
  ELSE
    ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';
  END IF;
END
\$\$;
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
fi

sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$DB_NAME" <<SQL
CREATE EXTENSION IF NOT EXISTS timescaledb;
GRANT ALL PRIVILEGES ON DATABASE "$DB_NAME" TO $DB_USER;
GRANT ALL ON SCHEMA public TO $DB_USER;
SQL

# 5. Clone or update repo
log "Fetching repository"
if [ -d "$APP_DIR/.git" ]; then
    info "Repo present, pulling latest"
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"
mkdir -p logs

# 6. Virtualenv + deps
log "Creating venv and installing Python deps"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# 7. Generate .env if missing
log "Writing .env (only if missing)"
if [ ! -f .env ]; then
    cat > .env <<EOF
# Database (local Postgres on this box)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASS

# Telegram notifications (optional — leave blank to disable)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# CORS (only matters if you ever expose the API publicly)
CORS_ORIGINS=
EOF
    chmod 600 .env
    info "Generated .env with random DB password"
else
    info ".env already exists, leaving untouched"
fi

# 8. Schema (only if missing)
log "Applying schema (idempotent)"
HAS_TABLE=$(sudo -u postgres psql -d "$DB_NAME" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='yahoo_adjusted_stock_prices'" || true)
if [ -z "$HAS_TABLE" ]; then
    sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -f yahoo_table_generation.sql
    sudo -u postgres psql -d "$DB_NAME" <<SQL
ALTER TABLE yahoo_adjusted_stock_prices OWNER TO $DB_USER;
ALTER TABLE tickers OWNER TO $DB_USER;
ALTER TABLE stock_indicators OWNER TO $DB_USER;
SQL
    info "Schema applied"
else
    info "Schema already present"
fi

# 9. Log rotation
log "Configuring log rotation"
sudo tee /etc/logrotate.d/trading-assistant > /dev/null <<EOF
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

# 10. Cron — 4:30 PM ET, weekdays
log "Installing daily cron"
CRON_LINE="30 16 * * 1-5 cd $APP_DIR && $APP_DIR/.venv/bin/python run_daily_jobs.py >> logs/cron.log 2>&1"
(crontab -l 2>/dev/null | grep -v "run_daily_jobs.py" || true; echo "$CRON_LINE") | crontab -

# 11. Nightly Postgres dump
log "Setting up nightly Postgres backup"
sudo tee /etc/cron.daily/pgbackup > /dev/null <<'EOF'
#!/bin/bash
set -e
mkdir -p /var/backups/pg
sudo -u postgres pg_dump -Fc financialDB1 \
  > /var/backups/pg/financialDB1_$(date +%F).pgc
find /var/backups/pg -mtime +14 -delete
EOF
sudo chmod +x /etc/cron.daily/pgbackup

# 12. FastAPI systemd unit (installed, disabled — for future use)
log "Installing FastAPI systemd unit (disabled by default)"
sudo tee /etc/systemd/system/trading-api.service > /dev/null <<EOF
[Unit]
Description=Trading Assistant FastAPI
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
info "Installed but not enabled. To turn on later: sudo systemctl enable --now trading-api"

# 13. Summary
log "Setup complete"
cat <<SUMMARY

============================================================
 trading-assistant on Lightsail: setup complete
============================================================
 App dir:     $APP_DIR
 DB:          $DB_NAME  (user: $DB_USER, host: 127.0.0.1)
 DB password: stored in ~/.db_password (mode 600)
 Cron:        weekdays 16:30 $TZ_DEFAULT
 Logs:        $APP_DIR/logs/
 Backups:     /var/backups/pg/  (14-day retention)
 API service: trading-api.service (disabled — not exposed)

 Next: run the first-time catch-up (fills the 4-month gap):

   cd $APP_DIR
   .venv/bin/python run_daily_update_ec2.py --lookback-days 130
   .venv/bin/python calculate_indicators.py

============================================================
SUMMARY
