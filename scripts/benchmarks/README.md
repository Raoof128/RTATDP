# Performance Benchmarking Suite

Comprehensive performance benchmarking tools for the AI Threat Detection Pipeline.

## Overview

This directory contains scripts for:
- **Latency testing**: Measure P50, P95, P99 response times
- **Throughput testing**: Determine maximum requests/second
- **Concurrent load testing**: Test system under concurrent users
- **Batch performance**: Evaluate batch prediction efficiency
- **Resource monitoring**: Track CPU and memory usage under load
- **Stress testing**: Identify breaking points

## Quick Start

### 1. Prerequisites

```bash
# Install dependencies
pip install requests psutil locust

# Ensure API is running
curl http://localhost:8000/health
```

### 2. Run Quick Benchmark

```bash
# Quick benchmark (reduced iterations)
bash scripts/benchmarks/run_benchmark.sh quick
```

### 3. Run Full Benchmark

```bash
# Complete benchmark suite
bash scripts/benchmarks/run_benchmark.sh full
```

## Benchmark Types

### Quick Benchmark

Fast benchmark with reduced iterations for quick validation:

```bash
bash scripts/benchmarks/run_benchmark.sh quick
```

**Duration**: ~2 minutes
**Tests**: Basic latency and throughput

### Full Benchmark

Comprehensive benchmark suite:

```bash
bash scripts/benchmarks/run_benchmark.sh full
```

**Duration**: ~5-10 minutes
**Tests**:
- Single request latency (100 iterations)
- Throughput test (30 seconds)
- Concurrent requests (50 workers, 500 requests)
- Batch prediction (sizes: 10, 50, 100)
- Resource usage monitoring (30 seconds)

### Locust Load Test

Interactive or headless load testing:

```bash
# Web UI mode (interactive)
locust -f scripts/benchmarks/locustfile.py --host=http://localhost:8000

# Headless mode
bash scripts/benchmarks/run_benchmark.sh locust 100 10 5m
# Args: users=100, spawn-rate=10, duration=5m
```

**Features**:
- Realistic user behavior simulation
- Real-time metrics dashboard
- Customizable load patterns
- HTML reports

### Stress Test

High-load stress testing to find breaking points:

```bash
bash scripts/benchmarks/run_benchmark.sh stress
```

**Configuration**:
- 500 concurrent users
- 50 users spawned per second
- 10 minute duration
- Aggressive request patterns

### Realistic Usage Test

Simulates realistic production usage:

```bash
bash scripts/benchmarks/run_benchmark.sh realistic
```

**Configuration**:
- 50 concurrent users
- Natural wait times (2-10s between requests)
- 15 minute duration
- Mixed workload (single + batch predictions)

### Continuous Monitoring

Run benchmarks continuously for ongoing monitoring:

```bash
bash scripts/benchmarks/run_benchmark.sh continuous
```

**Behavior**:
- Runs quick benchmark every 5 minutes
- Saves timestamped results
- Useful for performance regression detection
- Press Ctrl+C to stop

## Python API

You can also use the benchmarking library directly:

```python
from scripts.benchmarks.performance_benchmark import PerformanceBenchmark

# Initialize
benchmark = PerformanceBenchmark(api_url="http://localhost:8000")

# Run specific benchmarks
latency_results = benchmark.benchmark_single_request_latency(iterations=100)
throughput_results = benchmark.benchmark_throughput(duration_seconds=30)
concurrent_results = benchmark.benchmark_concurrent_requests(
    concurrency=50,
    total_requests=500
)

# Run full suite
all_results = benchmark.run_full_benchmark()

# Save results
benchmark.save_results("my_benchmark.json")
```

## Understanding Results

### Latency Metrics

- **P50 (Median)**: 50% of requests faster than this
- **P95**: 95% of requests faster than this (SLA target: <100ms)
- **P99**: 99% of requests faster than this
- **Mean**: Average latency
- **Std Dev**: Latency variability

**Good values**:
- P50: <50ms
- P95: <100ms
- P99: <200ms

### Throughput Metrics

- **Requests/second**: Total successful requests per second
- **Success rate**: Percentage of successful requests

**Good values**:
- Throughput: >100 req/s (target: >500 req/s)
- Success rate: >99%

### Concurrent Request Metrics

Shows how the system handles parallel requests:

**Good values**:
- Success rate: >95% with 50 concurrent users
- P95 latency: Still <200ms under load

### Resource Usage

- **CPU usage**: Percentage of CPU consumed
- **Memory usage**: Percentage of RAM used

**Warning signs**:
- CPU >90% sustained
- Memory >85% sustained
- Increasing over time (memory leak)

## Output Files

Benchmark results are saved to `benchmark_results/`:

```
benchmark_results/
├── full_benchmark_20250115_143022.json      # Full benchmark JSON
├── quick_benchmark_20250115_142010.json     # Quick benchmark JSON
├── locust_report_20250115_144500.html       # Locust HTML report
├── locust_stats_20250115_144500.csv         # Locust CSV stats
├── stress_test_20250115_150000.html         # Stress test report
└── realistic_test_20250115_153000.html      # Realistic test report
```

### JSON Result Format

```json
{
  "timestamp": "2025-01-15T14:30:22",
  "api_url": "http://localhost:8000",
  "results": {
    "latency": {
      "mean": 45.3,
      "median": 42.1,
      "p95": 78.5,
      "p99": 95.2
    },
    "throughput": {
      "throughput_rps": 234.5,
      "success_rate": 99.8
    },
    "concurrent": {
      "success_rate": 98.2,
      "mean_latency": 156.3
    }
  }
}
```

## Customization

### Custom API URL

```bash
# Test production environment
API_URL=https://threat-detector.prod.example.com bash scripts/benchmarks/run_benchmark.sh full
```

### Custom Locust Parameters

```bash
# 200 users, spawn 20/sec, run for 10 minutes
bash scripts/benchmarks/run_benchmark.sh locust 200 20 10m
```

### Modify Test Scenarios

Edit `locustfile.py` to add custom scenarios:

```python
@task(10)
def custom_scenario(self):
    """Your custom test scenario"""
    # Your test logic here
    pass
```

## Performance Targets

Based on the system specifications:

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| P95 Latency | <100ms | <200ms | >500ms |
| Throughput | >500 req/s | >100 req/s | <50 req/s |
| Success Rate | >99.9% | >95% | <90% |
| CPU Usage | <70% | <85% | >95% |
| Memory Usage | <70% | <85% | >95% |

**Color coding in output**:
- ✅ Green: Meets target
- ⚠️  Yellow: Acceptable but needs attention
- ❌ Red: Critical, action required

## Troubleshooting

### "API not accessible" Error

```bash
# Check if API is running
curl http://localhost:8000/health

# Start the API if needed
uvicorn src.inference_server.api:app --reload
```

### "Models not loaded" Warning

The benchmark will skip tests if models aren't loaded:

```bash
# Train and save models first
jupyter notebook notebooks/01_model_training_demo.ipynb

# Or copy pre-trained models
cp -r /path/to/models/* models/
```

### High Latency Results

Potential causes:
1. **Cold start**: First requests slower (models loading)
2. **Insufficient resources**: Check CPU/memory limits
3. **Network latency**: Test on localhost for baseline
4. **Model complexity**: Expected for complex models

### Locust Import Errors

```bash
# Install locust if missing
pip install locust

# Verify installation
locust --version
```

## CI/CD Integration

Add benchmarks to your CI/CD pipeline:

```yaml
# .github/workflows/benchmark.yml
- name: Run performance benchmark
  run: |
    bash scripts/benchmarks/run_benchmark.sh quick

- name: Check performance regression
  run: |
    python -c "
    import json
    with open('benchmark_results/quick_benchmark_*.json') as f:
        results = json.load(f)
    assert results['results']['latency']['p95'] < 100, 'P95 latency SLA violated'
    "
```

## Best Practices

1. **Baseline first**: Run benchmark on clean system to establish baseline
2. **Warm up**: Discard first few requests (cold start)
3. **Consistent environment**: Same hardware, network, load for comparison
4. **Multiple runs**: Run 3-5 times and average results
5. **Monitor resources**: Watch CPU, memory, disk during tests
6. **Gradual load**: Ramp up slowly to identify breaking points

## Advanced Usage

### Profile Specific Endpoints

```python
# Test only batch endpoint
benchmark = PerformanceBenchmark()
results = benchmark.benchmark_batch_prediction(batch_sizes=[10, 50, 100, 200])
```

### Custom Load Patterns

```python
# Simulate traffic spike
for i in range(5):
    benchmark.benchmark_concurrent_requests(concurrency=100, total_requests=1000)
    time.sleep(60)  # Cool down
```

### Integration with Monitoring

```python
import prometheus_client

# Export metrics to Prometheus
latency_gauge = prometheus_client.Gauge('benchmark_latency_p95', 'P95 latency from benchmarks')
throughput_gauge = prometheus_client.Gauge('benchmark_throughput', 'Throughput from benchmarks')

results = benchmark.run_full_benchmark()
latency_gauge.set(results['latency']['p95'])
throughput_gauge.set(results['throughput']['throughput_rps'])
```

## Support

For issues or questions:
- Check [docs/troubleshooting.md](../../docs/troubleshooting.md)
- Review API logs: `docker-compose logs -f inference-server`
- Open an issue on GitHub

## License

Apache-2.0
