/**
 * Watchlist sidebar — shows a switchable list of symbols with last/change%,
 * persisted server-side. Click a row to load that symbol into the chart.
 */
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { apiService } from '../../services/api';
import type { Watchlist as WatchlistT, Quote, SymbolMetadata } from '../../types';

const ACTIVE_WATCHLIST_KEY = 'active_watchlist_id';
const POLL_INTERVAL_MS = 60_000;

const UP_COLOR = '#26a69a';
const DOWN_COLOR = '#ef5350';

interface WatchlistProps {
  onSelectSymbol: (symbol: string) => void;
  selectedSymbol: string;
}

export default function Watchlist({ onSelectSymbol, selectedSymbol }: WatchlistProps) {
  const [watchlists, setWatchlists] = useState<WatchlistT[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [items, setItems] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map());
  const [loadingItems, setLoadingItems] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal/dialog state
  const [showNewList, setShowNewList] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [showListMenu, setShowListMenu] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  // Add-symbol state
  const [addQuery, setAddQuery] = useState('');
  const [addResults, setAddResults] = useState<SymbolMetadata[]>([]);
  const [adding, setAdding] = useState(false);

  const itemsForRefresh = useRef<string[]>([]);
  itemsForRefresh.current = items;

  // ----- Load watchlists on mount -----
  useEffect(() => {
    (async () => {
      try {
        const lists = await apiService.listWatchlists();
        setWatchlists(lists);

        const saved = localStorage.getItem(ACTIVE_WATCHLIST_KEY);
        const savedNum = saved ? parseInt(saved, 10) : NaN;
        const restore = lists.find((w) => w.id === savedNum);
        if (restore) setActiveId(restore.id);
        else if (lists.length > 0) setActiveId(lists[0].id);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load watchlists');
      }
    })();
  }, []);

  // Persist active list selection
  useEffect(() => {
    if (activeId != null) localStorage.setItem(ACTIVE_WATCHLIST_KEY, String(activeId));
  }, [activeId]);

  // ----- Load items + quotes when active list changes -----
  useEffect(() => {
    if (activeId == null) {
      setItems([]);
      setQuotes(new Map());
      return;
    }

    let cancelled = false;
    setLoadingItems(true);
    setError(null);

    (async () => {
      try {
        const symbols = await apiService.getWatchlistItems(activeId);
        if (cancelled) return;
        setItems(symbols);

        if (symbols.length > 0) {
          const fetched = await apiService.getQuotes(symbols);
          if (cancelled) return;
          setQuotes(new Map(fetched.map((q) => [q.symbol, q])));
        } else {
          setQuotes(new Map());
        }
      } catch (err: any) {
        if (!cancelled) setError(err.response?.data?.detail || 'Failed to load watchlist');
      } finally {
        if (!cancelled) setLoadingItems(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeId]);

  // ----- Poll quotes every minute, pause when tab hidden -----
  useEffect(() => {
    const refresh = async () => {
      const syms = itemsForRefresh.current;
      if (!syms.length || document.hidden) return;
      try {
        const fetched = await apiService.getQuotes(syms);
        setQuotes(new Map(fetched.map((q) => [q.symbol, q])));
      } catch {
        // silent — keep stale quotes on transient failure
      }
    };

    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    const onVis = () => {
      if (!document.hidden) refresh();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, []);

  // ----- Add-symbol search (debounced) -----
  useEffect(() => {
    if (!adding || addQuery.trim().length < 1) {
      setAddResults([]);
      return;
    }
    const handle = window.setTimeout(async () => {
      try {
        const data = await apiService.searchSymbols(addQuery.trim(), 20);
        setAddResults(data);
      } catch {
        setAddResults([]);
      }
    }, 200);
    return () => window.clearTimeout(handle);
  }, [addQuery, adding]);

  const activeList = useMemo(
    () => watchlists.find((w) => w.id === activeId) ?? null,
    [watchlists, activeId],
  );

  // ----- Mutations -----

  const handleCreateList = async () => {
    const name = newListName.trim();
    if (!name) return;
    try {
      const created = await apiService.createWatchlist(name);
      setWatchlists([...watchlists, created]);
      setActiveId(created.id);
      setNewListName('');
      setShowNewList(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create list');
    }
  };

  const handleRename = async () => {
    if (!activeList) return;
    const name = renameValue.trim();
    if (!name || name === activeList.name) {
      setRenaming(false);
      return;
    }
    try {
      const updated = await apiService.renameWatchlist(activeList.id, name);
      setWatchlists(watchlists.map((w) => (w.id === updated.id ? updated : w)));
      setRenaming(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to rename list');
    }
  };

  const handleDeleteList = async () => {
    if (!activeList) return;
    if (!window.confirm(`Delete watchlist "${activeList.name}"?`)) return;
    try {
      await apiService.deleteWatchlist(activeList.id);
      const remaining = watchlists.filter((w) => w.id !== activeList.id);
      setWatchlists(remaining);
      setActiveId(remaining.length ? remaining[0].id : null);
      setShowListMenu(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete list');
    }
  };

  const handleAddSymbol = async (symbol: string) => {
    if (activeId == null) return;
    const sym = symbol.toUpperCase();
    try {
      await apiService.addWatchlistItem(activeId, sym);
      const nextItems = [...items, sym];
      setItems(nextItems);
      setWatchlists(
        watchlists.map((w) =>
          w.id === activeId ? { ...w, item_count: w.item_count + 1 } : w,
        ),
      );
      const fresh = await apiService.getQuotes([sym]);
      if (fresh.length) {
        setQuotes((prev) => {
          const next = new Map(prev);
          next.set(sym, fresh[0]);
          return next;
        });
      }
      setAddQuery('');
      setAddResults([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to add symbol');
    }
  };

  const handleRemoveSymbol = async (symbol: string) => {
    if (activeId == null) return;
    try {
      await apiService.removeWatchlistItem(activeId, symbol);
      setItems(items.filter((s) => s !== symbol));
      setQuotes((prev) => {
        const next = new Map(prev);
        next.delete(symbol);
        return next;
      });
      setWatchlists(
        watchlists.map((w) =>
          w.id === activeId ? { ...w, item_count: Math.max(0, w.item_count - 1) } : w,
        ),
      );
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove symbol');
    }
  };

  // ----- Render -----

  return (
    <div
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: '4px',
        backgroundColor: '#fff',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header: list switcher + menu */}
      <div
        style={{
          padding: '10px 12px',
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          backgroundColor: '#f9f9f9',
        }}
      >
        {watchlists.length === 0 ? (
          <span style={{ fontSize: '13px', color: '#666', flex: 1 }}>No watchlists yet</span>
        ) : renaming && activeList ? (
          <>
            <input
              autoFocus
              type="text"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRename();
                if (e.key === 'Escape') setRenaming(false);
              }}
              style={{
                flex: 1,
                padding: '4px 8px',
                border: '1px solid #ccc',
                borderRadius: '3px',
                fontSize: '14px',
              }}
            />
            <button
              onClick={handleRename}
              style={{
                padding: '4px 8px',
                border: '1px solid #26a69a',
                backgroundColor: '#26a69a',
                color: 'white',
                borderRadius: '3px',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              Save
            </button>
          </>
        ) : (
          <>
            <select
              value={activeId ?? ''}
              onChange={(e) => setActiveId(parseInt(e.target.value, 10))}
              style={{
                flex: 1,
                padding: '6px 8px',
                border: '1px solid #ccc',
                borderRadius: '3px',
                fontSize: '14px',
                cursor: 'pointer',
                backgroundColor: 'white',
              }}
            >
              {watchlists.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.item_count})
                </option>
              ))}
            </select>
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setShowListMenu(!showListMenu)}
                title="List actions"
                style={{
                  padding: '4px 8px',
                  border: '1px solid #ccc',
                  borderRadius: '3px',
                  backgroundColor: 'white',
                  cursor: 'pointer',
                  fontSize: '14px',
                  lineHeight: 1,
                }}
              >
                ⋯
              </button>
              {showListMenu && (
                <>
                  <div
                    onClick={() => setShowListMenu(false)}
                    style={{
                      position: 'fixed',
                      inset: 0,
                      zIndex: 998,
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '110%',
                      backgroundColor: 'white',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      zIndex: 999,
                      minWidth: '140px',
                    }}
                  >
                    <button
                      onClick={() => {
                        setShowNewList(true);
                        setShowListMenu(false);
                      }}
                      style={menuItemStyle}
                    >
                      + New list
                    </button>
                    {activeList && (
                      <>
                        <button
                          onClick={() => {
                            setRenameValue(activeList.name);
                            setRenaming(true);
                            setShowListMenu(false);
                          }}
                          style={menuItemStyle}
                        >
                          Rename
                        </button>
                        <button
                          onClick={handleDeleteList}
                          style={{ ...menuItemStyle, color: DOWN_COLOR }}
                        >
                          Delete list
                        </button>
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          </>
        )}
      </div>

      {/* New-list inline form */}
      {(showNewList || watchlists.length === 0) && (
        <div
          style={{
            padding: '10px 12px',
            borderBottom: '1px solid #e0e0e0',
            backgroundColor: '#fafafa',
            display: 'flex',
            gap: '6px',
          }}
        >
          <input
            autoFocus
            type="text"
            placeholder="New list name…"
            value={newListName}
            onChange={(e) => setNewListName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreateList();
              if (e.key === 'Escape') setShowNewList(false);
            }}
            style={{
              flex: 1,
              padding: '4px 8px',
              border: '1px solid #ccc',
              borderRadius: '3px',
              fontSize: '13px',
            }}
          />
          <button
            onClick={handleCreateList}
            disabled={!newListName.trim()}
            style={{
              padding: '4px 10px',
              border: '1px solid #26a69a',
              backgroundColor: newListName.trim() ? '#26a69a' : '#ccc',
              color: 'white',
              borderRadius: '3px',
              cursor: newListName.trim() ? 'pointer' : 'not-allowed',
              fontSize: '12px',
            }}
          >
            Create
          </button>
          {watchlists.length > 0 && (
            <button
              onClick={() => {
                setShowNewList(false);
                setNewListName('');
              }}
              style={{
                padding: '4px 8px',
                border: '1px solid #ccc',
                backgroundColor: 'white',
                borderRadius: '3px',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div
          style={{
            padding: '8px 12px',
            backgroundColor: '#fee',
            color: '#c00',
            fontSize: '12px',
            borderBottom: '1px solid #fcc',
          }}
        >
          {error}
          <button
            onClick={() => setError(null)}
            style={{
              float: 'right',
              border: 'none',
              background: 'transparent',
              color: '#c00',
              cursor: 'pointer',
              fontSize: '14px',
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* Items */}
      <div style={{ flex: 1, overflowY: 'auto', maxHeight: '60vh' }}>
        {loadingItems ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#666', fontSize: '13px' }}>
            Loading…
          </div>
        ) : items.length === 0 && activeId != null ? (
          <div style={{ padding: '20px', textAlign: 'center', color: '#999', fontSize: '13px' }}>
            No symbols. Add one below.
          </div>
        ) : (
          items.map((sym) => {
            const q = quotes.get(sym);
            const isActive = sym === selectedSymbol;
            const changePct = q?.change_pct;
            const changeColor =
              changePct == null ? '#666' : changePct >= 0 ? UP_COLOR : DOWN_COLOR;
            return (
              <WatchlistRow
                key={sym}
                symbol={sym}
                lastClose={q?.last_close}
                changePct={changePct}
                changeColor={changeColor}
                active={isActive}
                onSelect={() => onSelectSymbol(sym)}
                onRemove={() => handleRemoveSymbol(sym)}
              />
            );
          })
        )}
      </div>

      {/* Add symbol */}
      {activeId != null && (
        <div
          style={{
            borderTop: '1px solid #e0e0e0',
            padding: '8px 12px',
            backgroundColor: '#fafafa',
            position: 'relative',
          }}
        >
          <input
            type="text"
            placeholder="+ Add symbol…"
            value={addQuery}
            onChange={(e) => {
              setAdding(true);
              setAddQuery(e.target.value);
            }}
            onFocus={() => setAdding(true)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && addQuery.trim()) {
                handleAddSymbol(addQuery.trim());
              }
              if (e.key === 'Escape') {
                setAdding(false);
                setAddQuery('');
              }
            }}
            style={{
              width: '100%',
              padding: '6px 8px',
              border: '1px solid #ccc',
              borderRadius: '3px',
              fontSize: '13px',
              boxSizing: 'border-box',
            }}
          />
          {adding && addResults.length > 0 && (
            <div
              style={{
                position: 'absolute',
                bottom: '100%',
                left: '12px',
                right: '12px',
                backgroundColor: 'white',
                border: '1px solid #ccc',
                borderRadius: '4px',
                maxHeight: '240px',
                overflowY: 'auto',
                boxShadow: '0 -2px 8px rgba(0,0,0,0.1)',
                zIndex: 100,
              }}
            >
              {addResults.map((r) => (
                <div
                  key={r.symbol}
                  onClick={() => handleAddSymbol(r.symbol)}
                  style={{
                    padding: '6px 10px',
                    cursor: 'pointer',
                    borderBottom: '1px solid #f0f0f0',
                    fontSize: '13px',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f5f5f5')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'white')}
                >
                  <strong>{r.symbol}</strong>
                  {r.asset_type && (
                    <span style={{ color: '#999', marginLeft: '8px', fontSize: '11px' }}>
                      {r.asset_type}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ----- Row component -----

interface RowProps {
  symbol: string;
  lastClose?: number;
  changePct: number | null | undefined;
  changeColor: string;
  active: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

function WatchlistRow({
  symbol,
  lastClose,
  changePct,
  changeColor,
  active,
  onSelect,
  onRemove,
}: RowProps) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        borderBottom: '1px solid #f0f0f0',
        cursor: 'pointer',
        backgroundColor: active ? '#e8f5f3' : hovered ? '#f9f9f9' : 'white',
        fontSize: '13px',
      }}
    >
      <span style={{ fontWeight: active ? 600 : 500, color: '#222', flex: 1 }}>{symbol}</span>
      <span
        style={{
          fontFamily: 'monospace',
          color: '#333',
          minWidth: '60px',
          textAlign: 'right',
          marginRight: '8px',
        }}
      >
        {lastClose != null ? lastClose.toFixed(2) : '--'}
      </span>
      <span
        style={{
          fontFamily: 'monospace',
          color: changeColor,
          minWidth: '60px',
          textAlign: 'right',
          fontWeight: 500,
        }}
      >
        {changePct != null
          ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(2)}%`
          : '--'}
      </span>
      {hovered && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          title="Remove"
          style={{
            marginLeft: '6px',
            padding: '2px 6px',
            border: '1px solid #ef5350',
            backgroundColor: '#ef5350',
            color: 'white',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '11px',
            lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </div>
  );
}

const menuItemStyle: CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  textAlign: 'left',
  border: 'none',
  backgroundColor: 'white',
  cursor: 'pointer',
  fontSize: '13px',
};
