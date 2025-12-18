/**
 * TradingView Lightweight Charts component
 * Displays candlestick chart with volume histogram
 */
import { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';
import type { PriceData } from '../../types';

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
}

/**
 * Main Chart component
 * Renders a TradingView-style candlestick chart with volume bars
 */
export default function Chart({ data, volumeData, height = 500, width }: ChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  // Use 'any' for chart and series refs since types aren't exported from lightweight-charts
  const chartRef = useRef<any>(null);
  const candlestickSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);

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
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
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

  return (
    <div
      ref={chartContainerRef}
      style={{
        width: width || '100%',
        height: `${height}px`,
        position: 'relative',
      }}
    />
  );
}

