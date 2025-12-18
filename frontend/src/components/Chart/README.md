# Chart Component

TradingView Lightweight Charts component for displaying stock price data.

## Features

- **Candlestick Series**: Displays OHLC (Open, High, Low, Close) price data
- **Volume Histogram**: Shows trading volume below the price chart
- **Time Scale**: Configurable time axis with date/time display
- **Price Scale**: Right-side price axis
- **Responsive**: Automatically resizes with window

## Usage

```typescript
import Chart from './components/Chart';
import { apiService } from './services/api';

function App() {
  const [priceData, setPriceData] = useState<PriceData[]>([]);

  useEffect(() => {
    async function loadData() {
      const response = await apiService.getPrices('AAPL', {
        interval: '1d',
        start_date: '2024-01-01T00:00:00',
        end_date: '2024-01-31T00:00:00'
      });
      setPriceData(response.data);
    }
    loadData();
  }, []);

  return (
    <Chart 
      data={priceData}
      height={500}
    />
  );
}
```

## Props

- `data: PriceData[]` - Required. Array of price data points
- `volumeData?: HistogramData[]` - Optional. Custom volume data (auto-generated from price data if not provided)
- `height?: number` - Optional. Chart height in pixels (default: 500)
- `width?: number` - Optional. Chart width in pixels (default: 100% of container)

## Data Format

The component expects `PriceData[]` which matches the backend API response:

```typescript
interface PriceData {
  timestamp: string;  // ISO 8601 datetime string
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
```

## Styling

The chart uses TradingView's default styling:
- Green candles for up days
- Red candles for down days
- Light gray grid lines
- White background

Customization can be added by modifying the chart configuration in `Chart.tsx`.

