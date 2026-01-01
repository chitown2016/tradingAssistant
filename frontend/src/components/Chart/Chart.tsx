/**
 * TradingView Lightweight Charts component
 * Displays candlestick chart with volume histogram
 */
import { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import type { PriceData, RelativeStrengthData } from '../../types';

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
}

/**
 * Main Chart component
 * Renders a TradingView-style candlestick chart with volume bars
 */
export default function Chart({ data, volumeData, height = 500, width, relativeStrengthData, loadingIndicator }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const indicatorContainerRef = useRef<HTMLDivElement>(null);
  // Use 'any' for chart and series refs since types aren't exported from lightweight-charts
  const chartRef = useRef<any>(null);
  const indicatorChartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const rsSeriesRef = useRef<any>(null);

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
      },
    });

    chartRef.current = chart;

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
        chart.applyOptions({
          width: width || chartContainerRef.current.clientWidth,
        });
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
    const indicatorChart = createChart(indicatorContainerRef.current, {
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      width: width || indicatorContainerRef.current.clientWidth,
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
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
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

    // Handle window resize for indicator chart
    const handleIndicatorResize = () => {
      if (indicatorContainerRef.current && indicatorChart) {
        indicatorChart.applyOptions({
          width: width || indicatorContainerRef.current.clientWidth,
        });
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
  }, [relativeStrengthData, width]);

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

    // Wait for indicator chart to have data loaded
    setupTimeout = setTimeout(() => {
      if (!chartRef.current || !indicatorChartRef.current || !rsSeriesRef.current) {
        return;
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

      // Subscribe to main chart time scale changes
      try {
        const result = chartRef.current.timeScale().subscribeVisibleTimeRangeChange((timeRange: any) => {
          if (!areChartsReady() || isUpdating || !timeRange) return;
          
          try {
            // Validate time range - it can be an object with from/to (numbers) or null
            if (timeRange && typeof timeRange === 'object') {
              const from = timeRange.from;
              const to = timeRange.to;
              
              // Both must be valid numbers
              if (
                from != null &&
                to != null &&
                typeof from === 'number' &&
                typeof to === 'number' &&
                !isNaN(from) &&
                !isNaN(to) &&
                from <= to
              ) {
                isUpdating = true;
                // Use requestAnimationFrame to ensure chart is ready
                requestAnimationFrame(() => {
                  try {
                    if (indicatorChartRef.current && areChartsReady()) {
                      indicatorChartRef.current.timeScale().setVisibleRange({ from, to });
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
              
              // Both must be valid numbers
              if (
                from != null &&
                to != null &&
                typeof from === 'number' &&
                typeof to === 'number' &&
                !isNaN(from) &&
                !isNaN(to) &&
                from <= to
              ) {
                isUpdating = true;
                // Use requestAnimationFrame to ensure chart is ready
                requestAnimationFrame(() => {
                  try {
                    if (chartRef.current && areChartsReady()) {
                      chartRef.current.timeScale().setVisibleRange({ from, to });
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

    // Fit content to view
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data]);

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

    // Create indicator data - only include dates with valid RS values
    // Lightweight-charts doesn't support null values, so we omit them
    // The time scales are synchronized, so charts will still align
    // Gaps will naturally appear where data points are missing
    const rsLineData = data
      .map((item) => {
        const date = new Date(item.timestamp);
        const dateStr = date.toISOString().split('T')[0];
        const rsRating = rsDataByDate.get(dateStr) ?? null;
        
        // Only include if we have a valid number value
        if (rsRating !== null && typeof rsRating === 'number') {
          return {
            time: dateStr as Time,
            value: rsRating,
          };
        }
        return null;
      })
      .filter((item): item is { time: Time; value: number } => item !== null);

    if (rsLineData.length > 0) {
      rsSeriesRef.current.setData(rsLineData);
      
      // Ensure both charts have the same time scale range
      // Calculate the time range from price data and set it explicitly on the indicator chart
      if (indicatorChartRef.current && chartRef.current && data.length > 0) {
        // Wait for main chart to finish updating, then sync the range
        requestAnimationFrame(() => {
          setTimeout(() => {
            try {
              if (!indicatorChartRef.current || !chartRef.current) return;
              
              // Get the visible range from the main chart (it should have all price data)
              const mainTimeRange = chartRef.current.timeScale().getVisibleRange();
              
              if (mainTimeRange && mainTimeRange.from != null && mainTimeRange.to != null) {
                // Set the same range on the indicator chart
                indicatorChartRef.current.timeScale().setVisibleRange({
                  from: mainTimeRange.from,
                  to: mainTimeRange.to,
                });
              } else {
                // Fallback: calculate from price data directly
                // Get the first and last dates from price data
                const firstDate = new Date(data[0].timestamp);
                const lastDate = new Date(data[data.length - 1].timestamp);
                
                // Convert to Unix timestamps (seconds since epoch)
                const firstTimestamp = Math.floor(firstDate.getTime() / 1000);
                const lastTimestamp = Math.floor(lastDate.getTime() / 1000);
                
                indicatorChartRef.current.timeScale().setVisibleRange({
                  from: firstTimestamp,
                  to: lastTimestamp,
                });
              }
            } catch (error) {
              // If setting range fails, try fitContent as fallback
              try {
                if (indicatorChartRef.current) {
                  indicatorChartRef.current.timeScale().fitContent();
                }
              } catch (fitError) {
                // Ignore errors
              }
            }
          }, 100);
        });
      }
    }
  }, [relativeStrengthData, data]);

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
      />
      
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

