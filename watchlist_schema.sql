-- Watchlist tables for the chart sidebar.
-- Apply once on the box:
--   sudo -u postgres psql -d financialDB1 -f ~/tradingAssistant/watchlist_schema.sql
-- Idempotent.

CREATE TABLE IF NOT EXISTS watchlists (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    position     INTEGER NOT NULL DEFAULT 0,
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (watchlist_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_watchlist_items_wid
    ON watchlist_items (watchlist_id, position);

ALTER TABLE watchlists      OWNER TO trading;
ALTER TABLE watchlist_items OWNER TO trading;
