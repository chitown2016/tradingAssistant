import type { PriceData } from '../types';

export type IndicatorType = 'SMA' | 'EMA';

export interface IndicatorConfig {
  id: string; // Unique ID for this indicator instance
  type: IndicatorType;
  period: number; // e.g., 20, 50, 200
  color: string; // Hex color code
  lineWidth: number; // 1-5
  lineStyle: 'solid' | 'dashed' | 'dotted';
  visible: boolean;
}

export interface IndicatorDataPoint {
  time: string; // YYYY-MM-DD format
  value: number;
}

/**
 * Calculate Simple Moving Average (SMA)
 */
export function calculateSMA(
  data: PriceData[],
  period: number,
  source: 'close' | 'open' | 'high' | 'low' = 'close'
): IndicatorDataPoint[] {
  if (data.length < period) {
    return [];
  }

  const result: IndicatorDataPoint[] = [];
  
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += data[j][source];
    }
    const average = sum / period;
    
    const date = new Date(data[i].timestamp);
    const dateStr = date.toISOString().split('T')[0];
    
    result.push({
      time: dateStr,
      value: average,
    });
  }
  
  return result;
}

/**
 * Calculate Exponential Moving Average (EMA)
 */
export function calculateEMA(
  data: PriceData[],
  period: number,
  source: 'close' | 'open' | 'high' | 'low' = 'close'
): IndicatorDataPoint[] {
  if (data.length < period) {
    return [];
  }

  const result: IndicatorDataPoint[] = [];
  const multiplier = 2 / (period + 1);
  
  // Start with SMA for the first value
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += data[i][source];
  }
  let ema = sum / period;
  
  const firstDate = new Date(data[period - 1].timestamp);
  result.push({
    time: firstDate.toISOString().split('T')[0],
    value: ema,
  });
  
  // Calculate EMA for remaining values
  for (let i = period; i < data.length; i++) {
    ema = (data[i][source] - ema) * multiplier + ema;
    
    const date = new Date(data[i].timestamp);
    const dateStr = date.toISOString().split('T')[0];
    
    result.push({
      time: dateStr,
      value: ema,
    });
  }
  
  return result;
}

/**
 * Calculate indicator based on config
 */
export function calculateIndicator(
  data: PriceData[],
  config: IndicatorConfig
): IndicatorDataPoint[] {
  switch (config.type) {
    case 'SMA':
      return calculateSMA(data, config.period);
    case 'EMA':
      return calculateEMA(data, config.period);
    default:
      return [];
  }
}

