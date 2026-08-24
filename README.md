# tradingAssistant

Full-stack stock screening and charting app — a yfinance→TimescaleDB price pipeline with
relative-strength ratings, a FastAPI backend, and a React/TypeScript charting frontend.

The system loads daily OHLCV for the US equity universe (~11,400 symbols) into
PostgreSQL/TimescaleDB, computes relative-strength and momentum indicators each evening,
and serves them to a TradingView-style charting UI.

---

## Architecture

```
NASDAQ Trader symbol lists ─┐
                            ├─► daily_update_stocks.py ─► PostgreSQL + TimescaleDB
Yahoo Finance (yfinance) ───┘                             ├─ yahoo_adjusted_stock_prices
                                                          ├─ tickers
                              calculate_indicators.py ───►├─ stock_indicators
                                                          └─ watchlists / watchlist_items
                                                                    │
                                            FastAPI (backend/) ◄────┘
                                                     │
                                     React + Vite (frontend/)
                                     lightweight-charts
```

| Layer | Stack |
|---|---|
| Ingest / compute | Python 3.11, pandas, yfinance, psycopg2 |
| Storage | PostgreSQL + TimescaleDB (hypertables on price & indicator tables) |
| API | FastAPI + Pydantic, uvicorn, pooled psycopg2 connections |
| UI | React 19, TypeScript, Vite, `lightweight-charts` v5, axios |
| Ops | cron on AWS EC2 / Lightsail, Telegram job notifications |

---

## Data model

| Table | Purpose |
|---|---|
| `yahoo_adjusted_stock_prices` | Split/dividend-adjusted daily OHLCV. Hypertable, PK `(symbol, timestamp)` |
| `tickers` | Symbol metadata — `asset_type`, `country`, first/last date, record count |
| `stock_indicators` | Per-symbol daily indicators. Hypertable, PK `(symbol, calculation_date)` |
| `watchlists`, `watchlist_items` | User watchlists backing the chart sidebar |

Schema lives in `yahoo_table_generation.sql` and `watchlist_schema.sql` (the latter is idempotent).

### Relative strength

`calculate_indicators.py` computes a weighted trailing return per symbol:

```
weighted_change = 0.4 × pct_change_3mo
                + 0.2 × pct_change_6mo
                + 0.2 × pct_change_9mo
                + 0.2 × pct_change_12mo
```

then percentile-ranks the whole universe for that date into `rs_rating` (1–99), IBD-style.
Alongside it the job stores `close_price`, `pct_change_1d`, `daily_percent_range`, `adr20`
(20-day average daily range), `low_52w`, `current_volume`, and `avg_volume_30d`.

---

## Getting started

### 1. Database

Provision PostgreSQL with the TimescaleDB extension, then apply the schema:

```bash
psql -d financialDB1 -f yahoo_table_generation.sql
psql -d financialDB1 -f watchlist_schema.sql
```

### 2. Environment

```bash
cp env.example .env
```

| Variable | Used by | Notes |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | everything | Postgres connection |
| `CORS_ORIGINS` | backend | Comma-separated origins; `*` in development |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `telegram_notifier.py` | Optional — notifications are skipped silently if unset |

### 3. Python

```bash
conda create --prefix ./env python=3.11
conda activate ./env
pip install -r requirements.txt
```

### 4. Backfill prices

```bash
python store_stock_data.py          # seed history
python daily_update_stocks.py       # incremental; --limit N, --lookback-days N
python calculate_indicators.py      # indicators + RS ratings
```

---

## Daily pipeline

`run_daily_jobs.py` is the orchestrator. It runs `run_daily_update_ec2.py`, and only on
success proceeds to `calculate_indicators.py` — a failure in the price load aborts before
indicators are computed off incomplete data. Either way it reports duration and exit codes
to Telegram.

```cron
30 16 * * 1-5 cd ~/tradingAssistant && /usr/bin/python3 run_daily_jobs.py >> logs/cron.log 2>&1
```

See `cron_daily_update` for scheduling notes. `rerun_rs_rating.py` recomputes ratings for a
date range without re-pulling prices.

---

## Backend API

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs at `/docs`. Health check at `/health`.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/v1/symbols` | List symbols with metadata |
| `GET` | `/api/v1/symbols/search` | Search by ticker or name |
| `GET` | `/api/v1/symbols/{symbol}/metadata` | Asset type, country, date coverage |
| `GET` | `/api/v1/symbols/{symbol}/prices` | OHLCV time series |
| `GET` | `/api/v1/symbols/{symbol}/latest` | Most recent bar |
| `GET` | `/api/v1/symbols/{symbol}/relative-strength` | RS rating time series |
| `POST` | `/api/v1/symbols/quotes` | Batch quote lookup |
| `GET`/`POST` | `/api/v1/watchlists` | List / create watchlists |
| `DELETE` | `/api/v1/watchlists/{wid}` | Delete a watchlist |
| `GET`/`POST` | `/api/v1/watchlists/{wid}/items` | List / add symbols |
| `DELETE` | `/api/v1/watchlists/{wid}/items/{symbol}` | Remove a symbol |

`test_api_performance.py` benchmarks these; results land in `performance_test_results.json`.

---

## Frontend

```bash
cd frontend
npm install
npm run dev
```

React 19 + Vite. `Chart/` wraps `lightweight-charts`, `Indicators/IndicatorPanel` renders the
RS and momentum figures, `Watchlist/` drives the sidebar, and `services/api.ts` is the typed
client for the routes above.

---

## Deployment

| Script | Target |
|---|---|
| `deploy_lightsail.ps1` | Creates a Lightsail instance + static IP, SSH-only ingress, runs `server_setup.sh`. No public API — the DB is reached over an SSH tunnel |
| `deploy_to_ec2.sh`, `setup_ec2.sh` | EC2 equivalent; see `EC2_DEPLOYMENT.md` |
| `cheat_sheet.md` | Postgres recovery notes (service restart, `max_locks_per_transaction`) |

---

## Repository layout

| Path | Contents |
|---|---|
| `store_stock_data.py` | Initial bulk price load, DB connection helper |
| `daily_update_stocks.py` | Incremental daily loader |
| `calculate_indicators.py` | Indicators + RS percentile ranking |
| `relative_strength.py` | Standalone RS computation |
| `get_price.py` | Trading-date helpers |
| `run_daily_jobs.py` | Nightly orchestrator with Telegram reporting |
| `telegram_notifier.py` | Telegram messaging |
| `backend/` | FastAPI application |
| `frontend/` | React + TypeScript client |
| `us_stock_tickers.txt` | Symbol universe (~11,400) |
| `ROADMAP.md`, `WEB_APP_PLAN.md` | Design notes from initial planning |
