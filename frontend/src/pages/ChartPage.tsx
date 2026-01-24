/**
 * Chart Page - Main page for displaying stock charts
 * Implements basic chart display with time range selection and symbol search
 */
import { useState, useEffect } from 'react';
import Chart from '../components/Chart';
import { apiService } from '../services/api';
import type { PriceData, SymbolMetadata, LatestPriceResponse, RelativeStrengthData, IndicatorConfig } from '../types';
import { getTemplates, saveTemplate, loadTemplate, deleteTemplate, type ChartTemplate } from '../utils/templates';

type TimeRange = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'ALL';

interface TimeRangeOption {
  label: string;
  value: TimeRange;
  days: number | null; // null means all data
}

const TIME_RANGES: TimeRangeOption[] = [
  { label: '1D', value: '1D', days: 1 },
  { label: '1W', value: '1W', days: 7 },
  { label: '1M', value: '1M', days: 30 },
  { label: '3M', value: '3M', days: 90 },
  { label: '6M', value: '6M', days: 180 },
  { label: '1Y', value: '1Y', days: 365 },
  { label: 'ALL', value: 'ALL', days: null },
];

export default function ChartPage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('AAPL');
  const [symbols, setSymbols] = useState<SymbolMetadata[]>([]);
  const [symbolSearch, setSymbolSearch] = useState<string>('');
  const [priceData, setPriceData] = useState<PriceData[]>([]);
  const [latestPrice, setLatestPrice] = useState<LatestPriceResponse | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>('1Y');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndicator, setSelectedIndicator] = useState<string>('');
  const [relativeStrengthData, setRelativeStrengthData] = useState<RelativeStrengthData[]>([]);
  const [loadingIndicator, setLoadingIndicator] = useState<boolean>(false);
  const [indicators, setIndicators] = useState<IndicatorConfig[]>([]);
  
  // Template management state
  const [templates, setTemplates] = useState<ChartTemplate[]>([]);
  const [templateName, setTemplateName] = useState<string>('');
  const [showSaveTemplate, setShowSaveTemplate] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Load templates on mount
  useEffect(() => {
    setTemplates(getTemplates());
  }, []);

  // Load default symbols on mount (for when search is empty)
  useEffect(() => {
    async function loadDefaultSymbols() {
      try {
        const data = await apiService.getSymbols({ limit: 100 });
        setSymbols(data);
      } catch (err) {
        console.error('Failed to load symbols:', err);
      }
    }
    loadDefaultSymbols();
  }, []);

  // Search symbols when user types (debounced)
  useEffect(() => {
    if (!symbolSearch || symbolSearch.length < 2) {
      // If search is too short, load default symbols
      async function loadDefaultSymbols() {
        try {
          const data = await apiService.getSymbols({ limit: 100 });
          setSymbols(data);
        } catch (err) {
          console.error('Failed to load symbols:', err);
        }
      }
      loadDefaultSymbols();
      return;
    }

    // Debounce search API call
    const timeoutId = setTimeout(async () => {
      try {
        const data = await apiService.searchSymbols(symbolSearch, 50);
        setSymbols(data);
      } catch (err) {
        console.error('Failed to search symbols:', err);
      }
    }, 300); // 300ms debounce

    return () => {
      clearTimeout(timeoutId);
    };
  }, [symbolSearch]);

  // Load price data when symbol or time range changes
  useEffect(() => {
    async function loadPriceData() {
      if (!selectedSymbol) return;

      setLoading(true);
      setError(null);

      try {
        // Calculate date range
        const endDate = new Date();
        const timeRangeOption = TIME_RANGES.find((r) => r.value === timeRange);
        const startDate = timeRangeOption?.days
          ? new Date(endDate.getTime() - timeRangeOption.days * 24 * 60 * 60 * 1000)
          : null;

        // Fetch price data
        const response = await apiService.getPrices(selectedSymbol, {
          interval: '1d',
          start_date: startDate ? startDate.toISOString() : undefined,
          end_date: endDate.toISOString(),
        });

        setPriceData(response.data);

        // Fetch latest price for current price display
        const latest = await apiService.getLatestPrice(selectedSymbol);
        setLatestPrice(latest);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load price data');
        console.error('Failed to load price data:', err);
      } finally {
        setLoading(false);
      }
    }

    loadPriceData();
  }, [selectedSymbol, timeRange]);

  // Load relative strength data when indicator is selected
  useEffect(() => {
    async function loadRelativeStrengthData() {
      if (!selectedIndicator || selectedIndicator !== 'relative-strength' || !selectedSymbol) {
        setRelativeStrengthData([]);
        return;
      }

      setLoadingIndicator(true);
      try {
        // Calculate date range to match price data
        const endDate = new Date();
        const timeRangeOption = TIME_RANGES.find((r) => r.value === timeRange);
        const startDate = timeRangeOption?.days
          ? new Date(endDate.getTime() - timeRangeOption.days * 24 * 60 * 60 * 1000)
          : null;

        const response = await apiService.getRelativeStrengthTimeseries(selectedSymbol, {
          start_date: startDate ? startDate.toISOString() : undefined,
          end_date: endDate.toISOString(),
        });

        setRelativeStrengthData(response.data);
      } catch (err: any) {
        console.error('Failed to load relative strength data:', err);
        setRelativeStrengthData([]);
      } finally {
        setLoadingIndicator(false);
      }
    }

    loadRelativeStrengthData();
  }, [selectedSymbol, timeRange, selectedIndicator]);

  // Filter symbols based on search (client-side fallback)
  const filteredSymbols = symbols.filter((symbol) =>
    symbol.symbol.toUpperCase().includes(symbolSearch.toUpperCase())
  );

  // Calculate price change
  const priceChange = latestPrice
    ? latestPrice.price.close - (priceData.length > 1 ? priceData[priceData.length - 2].close : latestPrice.price.close)
    : 0;
  const priceChangePercent =
    latestPrice && priceData.length > 1
      ? ((priceChange / priceData[priceData.length - 2].close) * 100)
      : 0;

  // Indicator management functions
  const handleAddIndicator = (type: 'SMA' | 'EMA', period: number) => {
    const id = `${type}-${period}-${Date.now()}`;
    const defaultColors = {
      SMA: '#2196F3',
      EMA: '#FF9800',
    };
    
    const newIndicator: IndicatorConfig = {
      id,
      type,
      period,
      color: defaultColors[type],
      lineWidth: 2,
      lineStyle: 'solid',
      visible: true,
    };
    
    setIndicators([...indicators, newIndicator]);
  };

  const handleUpdateIndicator = (id: string, updates: Partial<IndicatorConfig>) => {
    setIndicators(indicators.map(ind => 
      ind.id === id ? { ...ind, ...updates } : ind
    ));
  };

  const handleRemoveIndicator = (id: string) => {
    setIndicators(indicators.filter(ind => ind.id !== id));
  };

  // Template management functions
  const handleSaveTemplate = () => {
    if (!templateName.trim()) {
      setSaveError('Template name is required');
      return;
    }

    if (indicators.length === 0) {
      setSaveError('Add at least one indicator before saving');
      return;
    }

    try {
      saveTemplate(templateName.trim(), indicators);
      setTemplates(getTemplates());
      setTemplateName('');
      setShowSaveTemplate(false);
      setSaveError(null);
    } catch (error: any) {
      setSaveError(error.message || 'Failed to save template');
    }
  };

  const handleLoadTemplate = (templateId: string) => {
    const template = loadTemplate(templateId);
    if (template) {
      // Generate new IDs for loaded indicators to avoid conflicts
      const loadedIndicators = template.indicators.map(ind => ({
        ...ind,
        id: `${ind.type}-${ind.period}-${Date.now()}-${Math.random()}`,
      }));
      setIndicators(loadedIndicators);
      setSaveError(null);
    }
  };

  const handleDeleteTemplate = (templateId: string) => {
    if (window.confirm('Are you sure you want to delete this template?')) {
      if (deleteTemplate(templateId)) {
        setTemplates(getTemplates());
        setSaveError(null);
      }
    }
  };

  // Load older data when user pans to the beginning of the chart
  const handleLoadOlderData = async (beforeDate: string): Promise<PriceData[]> => {
    if (!selectedSymbol) return [];

    try {
      // Calculate how much older data to load (e.g., 1 year before the beforeDate)
      const endDate = new Date(beforeDate);
      const startDate = new Date(endDate.getTime() - 365 * 24 * 60 * 60 * 1000); // 1 year before

      // Fetch older price data
      const response = await apiService.getPrices(selectedSymbol, {
        interval: '1d',
        start_date: startDate.toISOString(),
        end_date: beforeDate, // Load up to (but not including) the beforeDate
      });

      // Filter out any data that might overlap with existing data
      const existingTimestamps = new Set(priceData.map(d => d.timestamp));
      const newData = response.data.filter(d => !existingTimestamps.has(d.timestamp));

      // Prepend older data to existing data
      if (newData.length > 0) {
        setPriceData([...newData, ...priceData]);
      }

      return newData;
    } catch (err: any) {
      console.error('Failed to load older data:', err);
      return [];
    }
  };


  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header with Symbol Search and Selection */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '1', minWidth: '200px' }}>
            <input
              type="text"
              placeholder="Search symbol..."
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: '16px',
                border: '1px solid #ccc',
                borderRadius: '4px',
              }}
            />
            {symbolSearch && filteredSymbols.length > 0 && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  backgroundColor: 'white',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  maxHeight: '200px',
                  overflowY: 'auto',
                  zIndex: 1000,
                  marginTop: '4px',
                }}
              >
                {filteredSymbols.slice(0, 10).map((symbol) => (
                  <div
                    key={symbol.symbol}
                    onClick={() => {
                      setSelectedSymbol(symbol.symbol);
                      setSymbolSearch('');
                    }}
                    style={{
                      padding: '8px 12px',
                      cursor: 'pointer',
                      borderBottom: '1px solid #eee',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#f0f0f0';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'white';
                    }}
                  >
                    <strong>{symbol.symbol}</strong>
                    {symbol.asset_type && <span style={{ color: '#666', marginLeft: '8px' }}>{symbol.asset_type}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <strong>Selected: {selectedSymbol}</strong>
          </div>
        </div>

        {/* Current Price Display */}
        {latestPrice && (
          <div style={{ display: 'flex', gap: '20px', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <div style={{ fontSize: '32px', fontWeight: 'bold' }}>
                ${latestPrice.price.close.toFixed(2)}
              </div>
              <div
                style={{
                  color: priceChange >= 0 ? '#26a69a' : '#ef5350',
                  fontSize: '18px',
                  fontWeight: '500',
                }}
              >
                {priceChange >= 0 ? '+' : ''}
                {priceChange.toFixed(2)} ({priceChangePercent >= 0 ? '+' : ''}
                {priceChangePercent.toFixed(2)}%)
              </div>
            </div>
            <div style={{ color: '#666', fontSize: '14px' }}>
              <div>High: ${latestPrice.price.high.toFixed(2)}</div>
              <div>Low: ${latestPrice.price.low.toFixed(2)}</div>
              <div>Volume: {latestPrice.price.volume.toLocaleString()}</div>
            </div>
          </div>
        )}
      </div>

      {/* Time Range Selection and Indicator Dropdown */}
      <div style={{ marginBottom: '20px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {TIME_RANGES.map((range) => (
            <button
              key={range.value}
              onClick={() => setTimeRange(range.value)}
              style={{
                padding: '8px 16px',
                border: '1px solid #ccc',
                borderRadius: '4px',
                backgroundColor: timeRange === range.value ? '#26a69a' : 'white',
                color: timeRange === range.value ? 'white' : '#333',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: timeRange === range.value ? 'bold' : 'normal',
              }}
            >
              {range.label}
            </button>
          ))}
        </div>
        
        {/* Indicator Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <label style={{ fontSize: '14px', fontWeight: '500' }}>Indicator:</label>
          <select
            value={selectedIndicator}
            onChange={(e) => setSelectedIndicator(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #ccc',
              borderRadius: '4px',
              fontSize: '14px',
              cursor: 'pointer',
              minWidth: '200px',
            }}
          >
            <option value="">None</option>
            <option value="relative-strength">Oneil Relative Strength Timeseries</option>
          </select>
        </div>
      </div>

      {/* Chart Templates Section */}
      <div style={{ 
        marginBottom: '20px', 
        padding: '16px', 
        border: '1px solid #e0e0e0', 
        borderRadius: '4px',
        backgroundColor: '#f9f9f9',
      }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '12px' }}>
          <strong style={{ fontSize: '16px' }}>Chart Templates:</strong>
          
          {/* Load Template Dropdown */}
          {templates.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ fontSize: '14px' }}>Load:</label>
              <select
                onChange={(e) => {
                  if (e.target.value) {
                    handleLoadTemplate(e.target.value);
                    e.target.value = ''; // Reset selection
                  }
                }}
                style={{
                  padding: '6px 10px',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '180px',
                }}
                defaultValue=""
              >
                <option value="">Select a template...</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name} ({template.indicators.length} indicator{template.indicators.length !== 1 ? 's' : ''})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Save Template Button */}
          <button
            onClick={() => {
              setShowSaveTemplate(!showSaveTemplate);
              setSaveError(null);
            }}
            style={{
              padding: '6px 12px',
              border: '1px solid #26a69a',
              borderRadius: '4px',
              backgroundColor: '#26a69a',
              color: 'white',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500',
            }}
          >
            {showSaveTemplate ? 'Cancel' : '💾 Save Template'}
          </button>
        </div>

        {/* Save Template Form */}
        {showSaveTemplate && (
          <div style={{ 
            padding: '12px', 
            backgroundColor: 'white', 
            borderRadius: '4px',
            border: '1px solid #ddd',
          }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                placeholder="Template name (e.g., 'My Trading Setup')"
                value={templateName}
                onChange={(e) => {
                  setTemplateName(e.target.value);
                  setSaveError(null);
                }}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    handleSaveTemplate();
                  }
                }}
                style={{
                  flex: '1',
                  minWidth: '200px',
                  padding: '6px 10px',
                  border: '1px solid #ccc',
                  borderRadius: '4px',
                  fontSize: '14px',
                }}
              />
              <button
                onClick={handleSaveTemplate}
                disabled={!templateName.trim() || indicators.length === 0}
                style={{
                  padding: '6px 16px',
                  border: 'none',
                  borderRadius: '4px',
                  backgroundColor: (!templateName.trim() || indicators.length === 0) ? '#ccc' : '#26a69a',
                  color: 'white',
                  cursor: (!templateName.trim() || indicators.length === 0) ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500',
                }}
              >
                Save
              </button>
            </div>
            {saveError && (
              <div style={{ 
                marginTop: '8px', 
                padding: '8px', 
                backgroundColor: '#fee', 
                border: '1px solid #fcc', 
                borderRadius: '4px', 
                color: '#c00',
                fontSize: '13px',
              }}>
                {saveError}
              </div>
            )}
            {indicators.length === 0 && (
              <div style={{ 
                marginTop: '8px', 
                fontSize: '13px', 
                color: '#666',
              }}>
                Add indicators to your chart before saving a template.
              </div>
            )}
          </div>
        )}

        {/* Template List */}
        {templates.length > 0 && (
          <div style={{ marginTop: '12px' }}>
            <div style={{ fontSize: '14px', fontWeight: '500', marginBottom: '8px' }}>
              Saved Templates ({templates.length}):
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {templates.map((template) => (
                <div
                  key={template.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '6px 12px',
                    backgroundColor: 'white',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    fontSize: '13px',
                  }}
                >
                  <span style={{ fontWeight: '500' }}>{template.name}</span>
                  <span style={{ color: '#666' }}>
                    ({template.indicators.length} indicator{template.indicators.length !== 1 ? 's' : ''})
                  </span>
                  <button
                    onClick={() => handleLoadTemplate(template.id)}
                    style={{
                      padding: '2px 8px',
                      border: '1px solid #26a69a',
                      borderRadius: '3px',
                      backgroundColor: 'transparent',
                      color: '#26a69a',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                    title="Load template"
                  >
                    Load
                  </button>
                  <button
                    onClick={() => handleDeleteTemplate(template.id)}
                    style={{
                      padding: '2px 8px',
                      border: '1px solid #ef5350',
                      borderRadius: '3px',
                      backgroundColor: 'transparent',
                      color: '#ef5350',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                    title="Delete template"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {templates.length === 0 && !showSaveTemplate && (
          <div style={{ fontSize: '13px', color: '#666', fontStyle: 'italic' }}>
            No saved templates. Save your indicator configurations as templates to reuse them later.
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div
          style={{
            padding: '12px',
            backgroundColor: '#fee',
            border: '1px solid #fcc',
            borderRadius: '4px',
            color: '#c00',
            marginBottom: '20px',
          }}
        >
          {error}
        </div>
      )}

      {/* Loading Indicator */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div>Loading chart data...</div>
        </div>
      )}

      {/* Chart */}
      {!loading && priceData.length > 0 && (
        <div style={{ border: '1px solid #e0e0e0', borderRadius: '4px', overflow: 'hidden' }}>
          <Chart 
            data={priceData} 
            height={600}
            relativeStrengthData={selectedIndicator === 'relative-strength' ? relativeStrengthData : undefined}
            loadingIndicator={loadingIndicator}
            indicators={indicators}
            onAddIndicator={handleAddIndicator}
            onUpdateIndicator={handleUpdateIndicator}
            onRemoveIndicator={handleRemoveIndicator}
            onLoadOlderData={handleLoadOlderData}
          />
        </div>
      )}

      {/* Empty State */}
      {!loading && priceData.length === 0 && !error && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          No price data available for {selectedSymbol}
        </div>
      )}
    </div>
  );
}

