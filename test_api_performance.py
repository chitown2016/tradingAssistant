"""
FastAPI Performance Testing Script
Tests all endpoints and measures response times
"""
import requests
import time
import statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple
import json

BASE_URL = "http://localhost:8000/api/v1"

class PerformanceTest:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[Dict] = []
    
    def test_endpoint(
        self, 
        name: str, 
        method: str, 
        endpoint: str, 
        params: dict = None,
        expected_status: int = 200
    ) -> Dict:
        """Test a single endpoint and measure performance"""
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=60)
            else:
                response = requests.request(method, url, json=params, timeout=60)
            
            elapsed = time.time() - start_time
            
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "status_code": response.status_code,
                "response_time": elapsed,
                "success": response.status_code == expected_status,
                "response_size": len(response.content),
                "error": None
            }
            
            if response.status_code != expected_status:
                result["error"] = f"Expected {expected_status}, got {response.status_code}"
                try:
                    result["error_detail"] = response.json()
                except:
                    result["error_detail"] = response.text[:200]
            
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "status_code": None,
                "response_time": elapsed,
                "success": False,
                "response_size": 0,
                "error": "Request timeout (>60s)"
            }
        except Exception as e:
            elapsed = time.time() - start_time
            result = {
                "name": name,
                "endpoint": endpoint,
                "method": method,
                "status_code": None,
                "response_time": elapsed,
                "success": False,
                "response_size": 0,
                "error": str(e)
            }
        
        self.results.append(result)
        return result
    
    # Around line 86-91, change test_health_check:
    def test_health_check(self):
        """Test health check endpoint"""
        print("Testing health check...")
        # Health endpoint is at root, not under /api/v1
        result = self.test_endpoint("Health Check", "GET", "/health", expected_status=200)
        # But we need to use the root URL, not /api/v1
        # So temporarily override base_url or use full URL
        original_base = self.base_url
        self.base_url = "http://localhost:8000"  # Root level
        result = self.test_endpoint("Health Check", "GET", "/health")
        self.base_url = original_base  # Restore
        print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']}")
        return result
    
    def test_list_symbols(self, limit: int = 100):
        """Test listing symbols"""
        print(f"Testing list symbols (limit={limit})...")
        result = self.test_endpoint(
            "List Symbols",
            "GET",
            "/symbols",
            params={"limit": limit}
        )
        print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']} - Size: {result['response_size']} bytes")
        return result
    
    def test_symbol_metadata(self, symbol: str = "AAPL"):
        """Test getting symbol metadata"""
        print(f"Testing symbol metadata for {symbol}...")
        result = self.test_endpoint(
            f"Symbol Metadata ({symbol})",
            "GET",
            f"/symbols/{symbol}/metadata"
        )
        print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']}")
        return result
    
    def test_prices(
        self, 
        symbol: str = "AAPL", 
        interval: str = "1d",
        days: int = 30
    ):
        """Test getting price data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        print(f"Testing prices for {symbol} ({interval}, {days} days)...")
        result = self.test_endpoint(
            f"Prices ({symbol}, {interval}, {days}d)",
            "GET",
            f"/symbols/{symbol}/prices",
            params={
                "interval": interval,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )
        
        if result['success']:
            try:
                data = requests.get(
                    f"{self.base_url}/symbols/{symbol}/prices",
                    params={
                        "interval": interval,
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat()
                    },
                    timeout=60
                ).json()
                result['data_points'] = data.get('count', 0)
                print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']} - {result['data_points']} data points")
            except:
                print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']}")
        else:
            print(f"  ✗ {result['response_time']:.3f}s - Status: {result['status_code']} - Error: {result.get('error', 'Unknown')}")
        
        return result
    
    def test_latest_price(self, symbol: str = "AAPL"):
        """Test getting latest price"""
        print(f"Testing latest price for {symbol}...")
        result = self.test_endpoint(
            f"Latest Price ({symbol})",
            "GET",
            f"/symbols/{symbol}/latest"
        )
        print(f"  ✓ {result['response_time']:.3f}s - Status: {result['status_code']}")
        return result
    
    def test_concurrent_requests(
        self, 
        endpoint: str, 
        params: dict, 
        num_requests: int = 10
    ):
        """Test concurrent requests to same endpoint"""
        print(f"Testing {num_requests} concurrent requests to {endpoint}...")
        
        def make_request():
            start = time.time()
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                    timeout=60
                )
                elapsed = time.time() - start
                return {
                    "success": response.status_code == 200,
                    "response_time": elapsed,
                    "status_code": response.status_code
                }
            except Exception as e:
                elapsed = time.time() - start
                return {
                    "success": False,
                    "response_time": elapsed,
                    "error": str(e)
                }
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [f.result() for f in as_completed(futures)]
        
        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.get('success', False))
        response_times = [r['response_time'] for r in results]
        
        result = {
            "name": f"Concurrent Requests ({num_requests})",
            "endpoint": endpoint,
            "total_time": total_time,
            "success_count": success_count,
            "failure_count": num_requests - success_count,
            "avg_response_time": statistics.mean(response_times) if response_times else 0,
            "min_response_time": min(response_times) if response_times else 0,
            "max_response_time": max(response_times) if response_times else 0,
            "median_response_time": statistics.median(response_times) if response_times else 0,
        }
        
        print(f"  ✓ Total: {total_time:.3f}s - Success: {success_count}/{num_requests}")
        print(f"    Avg: {result['avg_response_time']:.3f}s - Min: {result['min_response_time']:.3f}s - Max: {result['max_response_time']:.3f}s")
        
        self.results.append(result)
        return result
    
    def warmup(self):
        """Warm up the database cache by running a few queries"""
        print("Warming up database cache...")
        print("-" * 70)
        
        # Run a few queries to load data into cache
        self.test_prices("AAPL", "1d", days=30)
        self.test_latest_price("AAPL")
        self.test_list_symbols(limit=10)
        self.test_symbol_metadata("AAPL")
        
        print("Warmup complete.\n")
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("=" * 70)
        print("FastAPI Performance Test Suite")
        print("=" * 70)
        print()
        
        # Warm up database cache first
        self.warmup()
        
        # Basic health checks
        print("1. Basic Endpoints")
        print("-" * 70)
        self.test_health_check()
        self.test_list_symbols(limit=10)
        self.test_list_symbols(limit=100)
        print()
        
        # Symbol tests
        print("2. Symbol Endpoints")
        print("-" * 70)
        self.test_symbol_metadata("AAPL")
        self.test_symbol_metadata("MSFT")
        self.test_latest_price("AAPL")
        print()
        
        # Price data tests - different time ranges
        print("3. Price Data - Different Time Ranges")
        print("-" * 70)
        self.test_prices("AAPL", "1d", days=7)      # 1 week
        self.test_prices("AAPL", "1d", days=30)     # 1 month
        self.test_prices("AAPL", "1d", days=90)     # 3 months
        self.test_prices("AAPL", "1d", days=365)    # 1 year
        print()
        
        # Different intervals
        print("4. Price Data - Different Intervals")
        print("-" * 70)
        self.test_prices("AAPL", "1d", days=365)    # Daily
        self.test_prices("AAPL", "1w", days=365)    # Weekly
        self.test_prices("AAPL", "1m", days=365)    # Monthly
        print()
        
        # Different symbols
        print("5. Price Data - Different Symbols")
        print("-" * 70)
        test_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
        for symbol in test_symbols:
            self.test_prices(symbol, "1d", days=30)
        print()
        
        # Concurrent requests
        print("6. Concurrent Request Tests")
        print("-" * 70)
        self.test_concurrent_requests(
            "/symbols/AAPL/latest",
            {},
            num_requests=10
        )
        self.test_concurrent_requests(
            "/symbols/AAPL/prices",
            {"interval": "1d"},
            num_requests=5
        )
        print()
        
        # Generate report
        self.print_report()
    
    def print_report(self):
        """Print performance report"""
        print("=" * 70)
        print("Performance Report")
        print("=" * 70)
        print()
        
        # Filter successful requests
        successful = [r for r in self.results if r.get('success', False) and 'response_time' in r]
        
        if not successful:
            print("No successful requests to analyze.")
            return
        
        # Overall statistics
        response_times = [r['response_time'] for r in successful]
        print(f"Total Tests: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(self.results) - len(successful)}")
        print()
        
        print("Response Time Statistics:")
        print(f"  Average: {statistics.mean(response_times):.3f}s")
        print(f"  Median:  {statistics.median(response_times):.3f}s")
        print(f"  Min:     {min(response_times):.3f}s")
        print(f"  Max:     {max(response_times):.3f}s")
        print(f"  Std Dev: {statistics.stdev(response_times):.3f}s" if len(response_times) > 1 else "  Std Dev: N/A")
        print()
        
        # Slowest endpoints
        print("Slowest Endpoints:")
        slowest = sorted(successful, key=lambda x: x['response_time'], reverse=True)[:10]
        for i, result in enumerate(slowest, 1):
            print(f"  {i}. {result['name']}: {result['response_time']:.3f}s")
        print()
        
        # Failed requests
        failed = [r for r in self.results if not r.get('success', False)]
        if failed:
            print("Failed Requests:")
            for result in failed:
                print(f"  ✗ {result['name']}: {result.get('error', 'Unknown error')}")
            print()
        
        # Save detailed results to JSON
        with open('performance_test_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print("Detailed results saved to: performance_test_results.json")


if __name__ == "__main__":
    import sys
    
    # Allow custom base URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    tester = PerformanceTest(base_url)
    
    try:
        tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        tester.print_report()
    except Exception as e:
        print(f"\n\nError running tests: {e}")
        import traceback
        traceback.print_exc()
        tester.print_report()

