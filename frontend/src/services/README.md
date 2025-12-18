# API Service

This directory contains the API client for communicating with the backend FastAPI server.

## Usage

```typescript
import { apiService } from './api';

// Get all symbols
const symbols = await apiService.getSymbols({ limit: 10 });

// Get symbol metadata
const metadata = await apiService.getSymbolMetadata('AAPL');

// Get price data
const prices = await apiService.getPrices('AAPL', {
  interval: '1d',
  start_date: '2024-01-01T00:00:00',
  end_date: '2024-01-31T00:00:00'
});

// Get latest price
const latest = await apiService.getLatestPrice('AAPL');
```

## Configuration

Set the API base URL via environment variable:

Create a `.env` file in the `frontend/` directory:

```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

For production, set it to your production API URL.

## Error Handling

The API client includes automatic error handling via interceptors:
- Logs errors in development mode
- Handles HTTP status codes (401, 403, 404, 500, etc.)
- Provides detailed error messages

