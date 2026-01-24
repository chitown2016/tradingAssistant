/**
 * TradingView Lightweight Charts component
 * Displays candlestick chart with volume histogram
 */
import { useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import type { PriceData, RelativeStrengthData, IndicatorConfig } from '../../types';
import { calculateIndicator } from '../../utils/indicators';

// Define Time type locally (not exported from lightweight-charts)
// Time can be: number (Unix timestamp), string (YYYY-MM-DD), or BusinessDay object
type Time = string | number | { year: number; month: number; day: number };

// Define data types locally (not exported from lightweight-charts)
type CandlestickData = {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
};

type HistogramData = {
  time: Time;
  value: number;
  color?: string;
};

interface ChartProps {
  data: PriceData[];
  volumeData?: HistogramData[];
  height?: number;
  width?: number;
  relativeStrengthData?: RelativeStrengthData[];
  loadingIndicator?: boolean;
  indicators?: IndicatorConfig[];
  onUpdateIndicator?: (id: string, updates: Partial<IndicatorConfig>) => void;
  onRemoveIndicator?: (id: string) => void;
  onAddIndicator?: (type: 'SMA' | 'EMA', period: number) => void;
  onLoadOlderData?: (beforeDate: string) => Promise<PriceData[]>;
}

/**
 * Main Chart component
 * Renders a TradingView-style candlestick chart with volume bars
 */
export default function Chart({ 
  data, 
  volumeData, 
  height = 500, 
  width, 
  relativeStrengthData, 
  loadingIndicator, 
  indicators,
  onUpdateIndicator,
  onRemoveIndicator,
  onAddIndicator,
  onLoadOlderData,
}: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const indicatorContainerRef = useRef<HTMLDivElement>(null);
  // Use 'any' for chart and series refs since types aren't exported from lightweight-charts
  const chartRef = useRef<any>(null);
  const indicatorChartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const rsSeriesRef = useRef<any>(null);
  const indicatorSeriesRefs = useRef<Map<string, any>>(new Map());
  
  // State for crosshair indicator values
  const [indicatorValues, setIndicatorValues] = useState<Map<string, number>>(new Map());
  const indicatorDataCache = useRef<Map<string, Array<{ time: string; value: number }>>>(new Map());
  const [hoveredIndicatorId, setHoveredIndicatorId] = useState<string | null>(null);
  const [settingsIndicatorId, setSettingsIndicatorId] = useState<string | null>(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [newIndicatorType, setNewIndicatorType] = useState<'SMA' | 'EMA'>('SMA');
  const [newIndicatorPeriod, setNewIndicatorPeriod] = useState(20);
  const isLoadingOlderDataRef = useRef(false);
  const dataRef = useRef<PriceData[]>([]); // Add ref to track latest data

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart instance
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      width: width || chartContainerRef.current.clientWidth,
      height: height,
      grid: {
        vertLines: {
          color: '#e0e0e0',
        },
        horzLines: {
          color: '#e0e0e0',
        },
      },
      crosshair: {
        mode: 1, // Normal crosshair mode
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
    });

    chartRef.current = chart;

    // Clear indicator series refs when chart is recreated
    // Old series references become invalid when chart is recreated
    indicatorSeriesRefs.current.clear();
    indicatorDataCache.current.clear();

    // Add candlestick series (v5 API: use addSeries with series type)
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeriesRef.current = candlestickSeries;

    // Add volume histogram series (v5 API: use addSeries with series type)
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    });

    volumeSeriesRef.current = volumeSeries;

    // Configure volume price scale
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    // Handle window resize
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        const newWidth = width || chartContainerRef.current.clientWidth;
        chart.applyOptions({
          width: newWidth,
        });
        // Sync indicator chart width and time scale if it exists
        if (indicatorChartRef.current) {
          indicatorChartRef.current.applyOptions({
            width: newWidth,
          });
          // Sync time scale options to maintain grid alignment
          const mainTimeScaleOptions = chart.timeScale().options();
          indicatorChartRef.current.timeScale().applyOptions(mainTimeScaleOptions);
        }
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup function
    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart) {
        chart.remove();
      }
    };
  }, [height, width]);

  // Create indicator chart when relative strength data is available
  useEffect(() => {
    // Clean up previous chart if it exists
    if (indicatorChartRef.current) {
      try {
        // Check if chart is still valid before removing
        // Try to access a property to see if it's disposed
        const chart = indicatorChartRef.current;
        if (chart && typeof chart.remove === 'function') {
          chart.remove();
        }
      } catch (error) {
        // Chart might already be disposed, ignore the error
      }
      indicatorChartRef.current = null;
      rsSeriesRef.current = null;
    }

    if (!indicatorContainerRef.current || !relativeStrengthData || relativeStrengthData.length === 0) {
      return;
    }

    // Create indicator chart
    // Use the same width as main chart to ensure grid alignment
    const chartContainer = chartContainerRef.current;
    const mainChartWidth = width || (chartContainer ? chartContainer.clientWidth : indicatorContainerRef.current.clientWidth);
    
    // Get main chart's time scale options to ensure exact match
    let timeScaleOptions: any = {
      borderColor: '#cccccc',
      timeVisible: true,
      secondsVisible: false,
    };
    
    if (chartRef.current) {
      try {
        timeScaleOptions = chartRef.current.timeScale().options();
      } catch (error) {
        // Use default if main chart not ready
      }
    }
    
    const indicatorChart = createChart(indicatorContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      width: mainChartWidth,
      height: 300,
      grid: {
        vertLines: {
          color: '#e0e0e0',
        },
        horzLines: {
          color: '#e0e0e0',
        },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        ...timeScaleOptions,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
    });

    indicatorChartRef.current = indicatorChart;

    // Add line series for RS Rating
    const rsSeries = indicatorChart.addSeries(LineSeries, {
      color: '#2196F3',
      lineWidth: 2,
      title: 'RS Rating',
    });

    rsSeriesRef.current = rsSeries;

    // Don't set initial range here - let the sync effect handle it
    // This ensures it matches the main chart's visible range exactly

    // Handle window resize for indicator chart
    const handleIndicatorResize = () => {
      if (indicatorContainerRef.current && indicatorChart && chartRef.current && chartContainerRef.current) {
        // Use the same width as main chart to ensure grid alignment
        const mainChartWidth = width || chartContainerRef.current.clientWidth;
        indicatorChart.applyOptions({
          width: mainChartWidth,
        });
        // Sync time scale options to maintain grid alignment
        const mainTimeScaleOptions = chartRef.current.timeScale().options();
        indicatorChart.timeScale().applyOptions(mainTimeScaleOptions);
      }
    };

    window.addEventListener('resize', handleIndicatorResize);

    // Cleanup function
    return () => {
      window.removeEventListener('resize', handleIndicatorResize);
      if (indicatorChart) {
        try {
          // Check if chart is still valid before removing
          if (indicatorChart && typeof indicatorChart.remove === 'function') {
            indicatorChart.remove();
          }
        } catch (error) {
          // Chart might already be disposed, ignore the error
        }
      }
      indicatorChartRef.current = null;
      rsSeriesRef.current = null;
    };
  }, [relativeStrengthData, width, data]);

  // Synchronize time scales between main chart and indicator chart
  useEffect(() => {
    if (!chartRef.current || !indicatorChartRef.current) return;

    // Only sync if both charts have data
    if (!data.length || !relativeStrengthData || relativeStrengthData.length === 0) {
      return;
    }

    let isUpdating = false; // Prevent infinite loops
    let unsubscribeMain: (() => void) | null = null;
    let unsubscribeIndicator: (() => void) | null = null;
    let setupTimeout: ReturnType<typeof setTimeout> | null = null;

    // Wait for indicator chart to have data loaded, then sync initial visible range
    setupTimeout = setTimeout(() => {
      if (!chartRef.current || !indicatorChartRef.current || !rsSeriesRef.current) {
        return;
      }
      
      // Initially sync the visible range from main chart to indicator chart
      try {
        const mainTimeRange = chartRef.current.timeScale().getVisibleRange();
        if (mainTimeRange && mainTimeRange.from != null && mainTimeRange.to != null) {
          // Use exact same values from main chart
          indicatorChartRef.current.timeScale().setVisibleRange({
            from: mainTimeRange.from,
            to: mainTimeRange.to,
          });
        } else {
          // If main chart hasn't set a range yet, use fitContent on both
          chartRef.current.timeScale().fitContent();
          indicatorChartRef.current.timeScale().fitContent();
        }
      } catch (error) {
        // Ignore errors - charts might not be ready
      }

      // Helper function to check if charts are ready and have valid data
      const areChartsReady = () => {
        try {
          return (
            chartRef.current &&
            indicatorChartRef.current &&
            rsSeriesRef.current &&
            data.length > 0 &&
            relativeStrengthData &&
            relativeStrengthData.length > 0
          );
        } catch {
          return false;
        }
      };

      // Helper function to convert time to consistent format
      // Use the same format as the main chart to ensure perfect alignment
      const normalizeTime = (time: any): any => {
        // Don't convert - use the exact same format/type as received
        // This ensures both charts use identical time values
        return time;
      };

      // Subscribe to main chart time scale changes
      try {
        const result = chartRef.current.timeScale().subscribeVisibleTimeRangeChange((timeRange: any) => {
          if (!areChartsReady() || isUpdating || !timeRange) return;
          
          try {
            // Validate time range - it can be an object with from/to (numbers) or null
            if (timeRange && typeof timeRange === 'object') {
              const from = timeRange.from;
              const to = timeRange.to;
              
              // Both must be valid
              if (from != null && to != null) {
                isUpdating = true;
                // Normalize times to date strings for consistency
                const fromTime = normalizeTime(from);
                const toTime = normalizeTime(to);
                
                // Use requestAnimationFrame to ensure chart is ready
                requestAnimationFrame(() => {
                  try {
                    if (indicatorChartRef.current && areChartsReady()) {
                      // Set visible range with exact same values
                      indicatorChartRef.current.timeScale().setVisibleRange({
                        from: fromTime,
                        to: toTime,
                      });
                    }
                  } catch (error) {
                    // Silently ignore - chart might not be ready
                  } finally {
                    setTimeout(() => {
                      isUpdating = false;
                    }, 50);
                  }
                });
              }
            }
          } catch (error) {
            // Silently ignore - chart might not be ready yet
            isUpdating = false;
          }
        });
        
        // Check if result is an unsubscribe function
        if (typeof result === 'function') {
          unsubscribeMain = result;
        }
      } catch (error) {
        // Silently ignore - subscription might fail if chart is being destroyed
      }

      // Subscribe to indicator chart time scale changes
      try {
        const result = indicatorChartRef.current.timeScale().subscribeVisibleTimeRangeChange((timeRange: any) => {
          if (!areChartsReady() || isUpdating || !timeRange) return;
          
          try {
            // Validate time range - it can be an object with from/to (numbers) or null
            if (timeRange && typeof timeRange === 'object') {
              const from = timeRange.from;
              const to = timeRange.to;
              
              // Both must be valid
              if (from != null && to != null) {
                isUpdating = true;
                // Normalize times to date strings for consistency
                const fromTime = normalizeTime(from);
                const toTime = normalizeTime(to);
                
                // Use requestAnimationFrame to ensure chart is ready
                requestAnimationFrame(() => {
                  try {
                    if (chartRef.current && areChartsReady()) {
                      // Set visible range with exact same values
                      chartRef.current.timeScale().setVisibleRange({
                        from: fromTime,
                        to: toTime,
                      });
                    }
                  } catch (error) {
                    // Silently ignore - chart might not be ready
                  } finally {
                    setTimeout(() => {
                      isUpdating = false;
                    }, 50);
                  }
                });
              }
            }
          } catch (error) {
            // Silently ignore - chart might not be ready yet
            isUpdating = false;
          }
        });
        
        // Check if result is an unsubscribe function
        if (typeof result === 'function') {
          unsubscribeIndicator = result;
        }
      } catch (error) {
        // Silently ignore - subscription might fail if chart is being destroyed
      }
    }, 300); // Wait 300ms for charts to fully initialize with data

    // Cleanup function
    return () => {
      if (setupTimeout) {
        clearTimeout(setupTimeout);
      }
      if (unsubscribeMain && typeof unsubscribeMain === 'function') {
        try {
          unsubscribeMain();
        } catch (error) {
          // Ignore cleanup errors
        }
      }
      if (unsubscribeIndicator && typeof unsubscribeIndicator === 'function') {
        try {
          unsubscribeIndicator();
        } catch (error) {
          // Ignore cleanup errors
        }
      }
    };
  }, [data, relativeStrengthData]);

  // Update candlestick data
  useEffect(() => {
    if (!candlestickSeriesRef.current || !data.length) return;

    // Convert PriceData to CandlestickData format
    // For daily data, use YYYY-MM-DD format (Time type accepts string or number)
    const candlestickData: CandlestickData[] = data.map((item) => {
      const date = new Date(item.timestamp);
      const dateStr = date.toISOString().split('T')[0]; // YYYY-MM-DD format
      return {
        time: dateStr as Time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      };
    });

    candlestickSeriesRef.current.setData(candlestickData);

    // Fit content to view only if this is initial data load (not when loading older data)
    // We'll track this with a ref to avoid resetting view when prepending older data
    if (chartRef.current && !isLoadingOlderDataRef.current) {
      // Only fit content if we don't have a saved visible range (meaning it's initial load)
      const currentRange = chartRef.current.timeScale().getVisibleRange();
      if (!currentRange || currentRange.from === null) {
        chartRef.current.timeScale().fitContent();
      }
    }
  }, [data]);

  // Update dataRef whenever data changes
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  // Subscribe to visible range changes to detect panning and load older data
  useEffect(() => {
    if (!chartRef.current || !onLoadOlderData || !data.length) return;

    const timeScale = chartRef.current.timeScale();
    
    const unsubscribe = timeScale.subscribeVisibleTimeRangeChange((newVisibleTimeRange: any) => {
      if (!newVisibleTimeRange || isLoadingOlderDataRef.current || !newVisibleTimeRange.from) return;
      
      const currentData = dataRef.current;
      if (!currentData || currentData.length === 0) return;
      
      // Get the earliest date in current data
      const earliestDate = currentData[0].timestamp;
      const earliestDateObj = new Date(earliestDate);
      
      // Get the visible start date
      let visibleFromDate: Date;
      if (typeof newVisibleTimeRange.from === 'number') {
        visibleFromDate = new Date(newVisibleTimeRange.from * 1000);
      } else {
        visibleFromDate = new Date(newVisibleTimeRange.from);
      }
      
      // If user is viewing within 30 days of the earliest data, load older data
      const daysDiff = (earliestDateObj.getTime() - visibleFromDate.getTime()) / (1000 * 60 * 60 * 24);
      
      if (daysDiff <= 30 && daysDiff >= 0) {
        isLoadingOlderDataRef.current = true;
        
        onLoadOlderData(earliestDate)
          .then((olderData) => {
            isLoadingOlderDataRef.current = false;
          })
          .catch((error) => {
            console.error('[Chart] Failed to load older data:', error);
            isLoadingOlderDataRef.current = false;
          });
      }
    });

    return () => {
      if (unsubscribe && typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, [onLoadOlderData]);

  // Update volume data
  useEffect(() => {
    if (!volumeSeriesRef.current) return;

    if (volumeData && volumeData.length > 0) {
      // Use provided volume data
      volumeSeriesRef.current.setData(volumeData);
    } else if (data.length > 0) {
      // Generate volume data from price data
      const histogramData: HistogramData[] = data.map((item, index) => {
        // Use green for up days, red for down days
        const isUp = index === 0 || item.close >= data[index - 1].close;
        const date = new Date(item.timestamp);
        const dateStr = date.toISOString().split('T')[0]; // YYYY-MM-DD format
        return {
          time: dateStr as Time,
          value: item.volume,
          color: isUp ? '#26a69a80' : '#ef535080', // Semi-transparent colors
        };
      });

      volumeSeriesRef.current.setData(histogramData);
    }
  }, [data, volumeData]);

  // Update relative strength data
  useEffect(() => {
    if (!rsSeriesRef.current || !data.length) return;

    // Create a map of RS data by date for quick lookup
    const rsDataByDate = new Map<string, number | null>();
    if (relativeStrengthData && relativeStrengthData.length > 0) {
      relativeStrengthData.forEach((item) => {
        const date = new Date(item.calculation_date);
        const dateStr = date.toISOString().split('T')[0];
        rsDataByDate.set(dateStr, item.rs_rating);
      });
    }

    // Merge price data with indicator data - include ALL price dates
    // For missing indicator values, use whitespace data (time only, no value)
    // This ensures the time scale spans the full range and shows gaps where data is missing
    const rsLineData: Array<{ time: Time; value?: number }> = [];
    
    for (const priceItem of data) {
      const date = new Date(priceItem.timestamp);
      const dateStr = date.toISOString().split('T')[0];
      const rsRating = rsDataByDate.get(dateStr);
      
      if (rsRating !== null && rsRating !== undefined && typeof rsRating === 'number' && !isNaN(rsRating)) {
        // Include date with value
        rsLineData.push({
          time: dateStr as Time,
          value: rsRating,
        });
      } else {
        // Include date without value (whitespace data) - creates a gap in the chart
        rsLineData.push({
          time: dateStr as Time,
        });
      }
    }

    if (rsLineData.length > 0) {
      rsSeriesRef.current.setData(rsLineData);
      // Don't set visible range here - let the sync effect handle it
      // This prevents conflicts and ensures the sync effect is the single source of truth
    }
  }, [relativeStrengthData, data]);

  // Manage indicator series (SMA/EMA)
  useEffect(() => {
    // Wait for chart to be ready and data to be available
    if (!chartRef.current || !data || data.length === 0) {
      // Don't clear indicators if chart isn't ready yet - they'll be added when chart is ready
      return;
    }

    if (!indicators || indicators.length === 0) {
      // Remove all indicator series if no indicators
      indicatorSeriesRefs.current.forEach((series) => {
        try {
          chartRef.current?.removeSeries(series);
        } catch (error) {
          // Ignore errors
        }
      });
      indicatorSeriesRefs.current.clear();
      indicatorDataCache.current.clear();
      setIndicatorValues(new Map());
      return;
    }

    // Calculate and add/update indicators
    indicators.forEach((config) => {
      if (!config.visible) {
        // Remove if exists and not visible
        const existingSeries = indicatorSeriesRefs.current.get(config.id);
        if (existingSeries) {
          try {
            chartRef.current?.removeSeries(existingSeries);
          } catch (error) {
            // Ignore
          }
          indicatorSeriesRefs.current.delete(config.id);
          indicatorDataCache.current.delete(config.id);
        }
        return;
      }

      // Calculate indicator data
      const indicatorData = calculateIndicator(data, config);
      
      // Cache indicator data for crosshair lookup (even if empty)
      indicatorDataCache.current.set(config.id, indicatorData);
      
      if (indicatorData.length === 0) {
        // If no data, remove the series but keep the indicator config
        const existingSeries = indicatorSeriesRefs.current.get(config.id);
        if (existingSeries) {
          try {
            chartRef.current?.removeSeries(existingSeries);
          } catch (error) {
            // Ignore
          }
          indicatorSeriesRefs.current.delete(config.id);
        }
        return;
      }

      // Convert to lightweight-charts format
      const lineData = indicatorData.map((point) => ({
        time: point.time as Time,
        value: point.value,
      }));

      // Check if series already exists
      let series = indicatorSeriesRefs.current.get(config.id);
      
      // If series exists, check if it's still valid (chart might have been recreated)
      if (series) {
        try {
          // Try to access a property to see if series is still valid
          // If chart was recreated, the old series reference is invalid
          const test = series.applyOptions;
          if (!test) {
            // Series is invalid, remove from refs
            indicatorSeriesRefs.current.delete(config.id);
            series = null;
          }
        } catch (error) {
          // Series is invalid, remove from refs
          indicatorSeriesRefs.current.delete(config.id);
          series = null;
        }
      }
      
      if (!series) {
        // Create new series without title, overlay on main price scale
        // This ensures indicators adjust with the main y-axis when user zooms/pans
        // overlay: true makes it use the main price scale instead of a separate one
        try {
          series = chartRef.current.addSeries(LineSeries, {
            color: config.color,
            lineWidth: config.lineWidth,
            lineStyle: config.lineStyle === 'dashed' ? 1 : config.lineStyle === 'dotted' ? 2 : 0,
            // Don't set title - this prevents the name from showing on y-axis
            lastValueVisible: false, // Hide the last value label on the y-axis
            priceLineVisible: false, // Hide the price line that extends to the right
            overlay: true, // Overlay on main price scale so it adjusts with y-axis zoom/pan
            priceFormat: {
              type: 'price',
              precision: 2,
              minMove: 0.01,
            },
          });
          
          indicatorSeriesRefs.current.set(config.id, series);
        } catch (error) {
          console.error('Failed to create indicator series:', error);
          return;
        }
      } else {
        // Update existing series - explicitly remove title
        try {
          series.applyOptions({
            color: config.color,
            lineWidth: config.lineWidth,
            lineStyle: config.lineStyle === 'dashed' ? 1 : config.lineStyle === 'dotted' ? 2 : 0,
            // Don't set title - this prevents the name from showing on y-axis
            lastValueVisible: false, // Hide the last value label on the y-axis
            priceLineVisible: false, // Hide the price line that extends to the right
            overlay: true, // Ensure it's overlaying on main price scale
          });
        } catch (error) {
          // Series might be invalid, try to recreate it
          try {
            indicatorSeriesRefs.current.delete(config.id);
            series = chartRef.current.addSeries(LineSeries, {
              color: config.color,
              lineWidth: config.lineWidth,
              lineStyle: config.lineStyle === 'dashed' ? 1 : config.lineStyle === 'dotted' ? 2 : 0,
              lastValueVisible: false,
              priceLineVisible: false, // Hide the price line that extends to the right
              overlay: true,
              priceFormat: {
                type: 'price',
                precision: 2,
                minMove: 0.01,
              },
            });
            indicatorSeriesRefs.current.set(config.id, series);
          } catch (recreateError) {
            console.error('Failed to recreate indicator series:', recreateError);
            return;
          }
        }
      }

      // Update data
      try {
        series.setData(lineData);
      } catch (error) {
        console.error('Failed to set indicator data:', error);
      }
    });

    // Cleanup: remove indicators that are no longer in the list
    const currentIds = new Set(indicators.map((ind) => ind.id));
    indicatorSeriesRefs.current.forEach((series, id) => {
      if (!currentIds.has(id)) {
        try {
          chartRef.current?.removeSeries(series);
        } catch (error) {
          // Ignore
        }
        indicatorSeriesRefs.current.delete(id);
        indicatorDataCache.current.delete(id);
      }
    });
  }, [indicators, data]);

  // Subscribe to crosshair move events to update indicator values
  useEffect(() => {
    if (!chartRef.current || !indicators || indicators.length === 0) {
      return;
    }

    const unsubscribe = chartRef.current.subscribeCrosshairMove((param: any) => {
      if (!param || !param.time) {
        setIndicatorValues(new Map());
        return;
      }

      // Get indicator values directly from series data in crosshair param
      // This ensures we get the exact value that's displayed on the chart
      const values = new Map<string, number>();
      
      indicators.forEach((config) => {
        if (!config.visible) return;
        
        const series = indicatorSeriesRefs.current.get(config.id);
        if (!series) return;

        // Get the series data from the crosshair param
        // The param.seriesData is a Map of series -> data point
        if (param.seriesData && param.seriesData.get) {
          const seriesData = param.seriesData.get(series);
          if (seriesData && seriesData.value !== undefined && !isNaN(seriesData.value)) {
            values.set(config.id, seriesData.value);
          }
        }
      });

      setIndicatorValues(values);
    });

    return () => {
      if (unsubscribe && typeof unsubscribe === 'function') {
        unsubscribe();
      }
    };
  }, [indicators, data]);

  return (
    <div style={{ width: width || '100%' }}>
      {/* Main Chart */}
      <div
        ref={chartContainerRef}
        style={{
          width: width || '100%',
          height: `${height}px`,
          position: 'relative',
        }}
      >
        {/* Indicator Legend Overlay */}
        <div
          style={{
            position: 'absolute',
            top: '8px',
            left: '8px',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '1px solid #e0e0e0',
            borderRadius: '4px',
            padding: '6px 10px',
            zIndex: 10,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            minWidth: '180px',
          }}
        >
          {/* Add Indicator Button */}
          {onAddIndicator && (
            <div style={{ marginBottom: '6px', paddingBottom: '6px', borderBottom: '1px solid #e0e0e0' }}>
              <button
                onClick={() => setShowAddDialog(true)}
                style={{
                  padding: '4px 8px',
                  border: '1px solid #26a69a',
                  borderRadius: '4px',
                  backgroundColor: '#26a69a',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: '500',
                  width: '100%',
                }}
              >
                + Add Indicator
              </button>
            </div>
          )}
          
          {/* Indicator Items */}
          {indicators && indicators.filter(ind => ind.visible).length > 0 ? (
            indicators
              .filter(ind => ind.visible)
              .map((config) => {
                const value = indicatorValues.get(config.id);
                const isHovered = hoveredIndicatorId === config.id;
                return (
                  <div
                    key={config.id}
                    onMouseEnter={() => setHoveredIndicatorId(config.id)}
                    onMouseLeave={() => setHoveredIndicatorId(null)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      marginBottom: '4px',
                      fontSize: '13px',
                      padding: '2px 4px',
                      borderRadius: '3px',
                      backgroundColor: isHovered ? '#f5f5f5' : 'transparent',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        width: '12px',
                        height: '2px',
                        backgroundColor: config.color,
                        borderRadius: '1px',
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontWeight: '500', color: '#333', flex: 1 }}>
                      {config.type}({config.period}):
                    </span>
                    <span style={{ color: '#666', fontFamily: 'monospace', minWidth: '50px', textAlign: 'right' }}>
                      {value !== undefined ? value.toFixed(2) : '--'}
                    </span>
                    {isHovered && onUpdateIndicator && onRemoveIndicator && (
                      <div style={{ display: 'flex', gap: '4px', marginLeft: '4px' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSettingsIndicatorId(config.id);
                          }}
                          style={{
                            padding: '2px 6px',
                            border: '1px solid #ccc',
                            borderRadius: '3px',
                            backgroundColor: 'white',
                            cursor: 'pointer',
                            fontSize: '11px',
                            lineHeight: '1',
                          }}
                          title="Settings"
                        >
                          ⚙️
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onRemoveIndicator(config.id);
                          }}
                          style={{
                            padding: '2px 6px',
                            border: '1px solid #ef5350',
                            borderRadius: '3px',
                            backgroundColor: '#ef5350',
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '11px',
                            lineHeight: '1',
                          }}
                          title="Delete"
                        >
                          ×
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
          ) : (
            <div style={{ color: '#999', fontSize: '12px', textAlign: 'center', padding: '4px' }}>
              No indicators
            </div>
          )}
        </div>

        {/* Settings Dialog */}
        {settingsIndicatorId && onUpdateIndicator && (
          <>
            {/* Backdrop */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                zIndex: 999,
              }}
              onClick={() => setSettingsIndicatorId(null)}
            />
            {/* Dialog */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                backgroundColor: 'white',
                border: '1px solid #ccc',
                borderRadius: '8px',
                padding: '20px',
                zIndex: 1000,
                boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
                minWidth: '300px',
              }}
              onClick={(e) => e.stopPropagation()}
            >
            {(() => {
              const config = indicators?.find(ind => ind.id === settingsIndicatorId);
              if (!config) return null;
              
              return (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>
                      {config.type}({config.period}) Settings
                    </h3>
                    <button
                      onClick={() => setSettingsIndicatorId(null)}
                      style={{
                        padding: '4px 8px',
                        border: 'none',
                        backgroundColor: 'transparent',
                        cursor: 'pointer',
                        fontSize: '18px',
                        lineHeight: '1',
                      }}
                    >
                      ×
                    </button>
                  </div>
                  
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                      Period:
                    </label>
                    <input
                      type="number"
                      value={config.period}
                      onChange={(e) => onUpdateIndicator(config.id, { period: parseInt(e.target.value) || 20 })}
                      min="1"
                      max="500"
                      style={{
                        width: '100%',
                        padding: '6px',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                        fontSize: '14px',
                      }}
                    />
                  </div>
                  
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                      Color:
                    </label>
                    <input
                      type="color"
                      value={config.color}
                      onChange={(e) => onUpdateIndicator(config.id, { color: e.target.value })}
                      style={{
                        width: '100%',
                        height: '40px',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    />
                  </div>
                  
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                      Line Width: {config.lineWidth}px
                    </label>
                    <input
                      type="range"
                      min="1"
                      max="5"
                      value={config.lineWidth}
                      onChange={(e) => onUpdateIndicator(config.id, { lineWidth: parseInt(e.target.value) })}
                      style={{ width: '100%' }}
                    />
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                      Line Style:
                    </label>
                    <select
                      value={config.lineStyle}
                      onChange={(e) => onUpdateIndicator(config.id, { lineStyle: e.target.value as 'solid' | 'dashed' | 'dotted' })}
                      style={{
                        width: '100%',
                        padding: '6px',
                        border: '1px solid #ccc',
                        borderRadius: '4px',
                        fontSize: '14px',
                      }}
                    >
                      <option value="solid">Solid</option>
                      <option value="dashed">Dashed</option>
                      <option value="dotted">Dotted</option>
                    </select>
                  </div>
                </>
              );
            })()}
            </div>
          </>
        )}

        {/* Add Indicator Dialog */}
        {showAddDialog && onAddIndicator && (
          <>
            {/* Backdrop */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                zIndex: 999,
              }}
              onClick={() => setShowAddDialog(false)}
            />
            {/* Dialog */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                backgroundColor: 'white',
                border: '1px solid #ccc',
                borderRadius: '8px',
                padding: '20px',
                zIndex: 1000,
                boxShadow: '0 4px 20px rgba(0,0,0,0.2)',
                minWidth: '300px',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600' }}>Add Indicator</h3>
                <button
                  onClick={() => setShowAddDialog(false)}
                  style={{
                    padding: '4px 8px',
                    border: 'none',
                    backgroundColor: 'transparent',
                    cursor: 'pointer',
                    fontSize: '18px',
                    lineHeight: '1',
                  }}
                >
                  ×
                </button>
              </div>
              
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                  Type:
                </label>
                <select
                  value={newIndicatorType}
                  onChange={(e) => setNewIndicatorType(e.target.value as 'SMA' | 'EMA')}
                  style={{
                    width: '100%',
                    padding: '6px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    fontSize: '14px',
                  }}
                >
                  <option value="SMA">SMA (Simple Moving Average)</option>
                  <option value="EMA">EMA (Exponential Moving Average)</option>
                </select>
              </div>
              
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '4px', fontSize: '14px', fontWeight: '500' }}>
                  Period:
                </label>
                <input
                  type="number"
                  value={newIndicatorPeriod}
                  onChange={(e) => setNewIndicatorPeriod(parseInt(e.target.value) || 20)}
                  min="1"
                  max="500"
                  style={{
                    width: '100%',
                    padding: '6px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    fontSize: '14px',
                  }}
                />
              </div>
              
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowAddDialog(false)}
                  style={{
                    padding: '8px 16px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    onAddIndicator(newIndicatorType, newIndicatorPeriod);
                    setShowAddDialog(false);
                    setNewIndicatorPeriod(20);
                  }}
                  style={{
                    padding: '8px 16px',
                    border: '1px solid #26a69a',
                    borderRadius: '4px',
                    backgroundColor: '#26a69a',
                    color: 'white',
                    cursor: 'pointer',
                    fontSize: '14px',
                  }}
                >
                  Add
                </button>
              </div>
            </div>
          </>
        )}
      </div>
      
      {/* Indicator Panel */}
      {relativeStrengthData && relativeStrengthData.length > 0 && (
        <div style={{ marginTop: '8px', borderTop: '1px solid #e0e0e0', paddingTop: '8px' }}>
          {loadingIndicator ? (
            <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
              Loading indicator data...
            </div>
          ) : (
            <div
              ref={indicatorContainerRef}
              style={{
                width: width || '100%',
                height: '300px',
                position: 'relative',
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}

