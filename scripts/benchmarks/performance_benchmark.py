#!/usr/bin/env python3
"""
Performance benchmarking script for AI Threat Detection Pipeline

Tests:
- Single request latency
- Throughput (requests/second)
- Concurrent request handling
- Batch prediction performance
- Memory and CPU usage under load
"""

import asyncio
import time
import statistics
import psutil
import requests
import concurrent.futures
from typing import List, Dict, Tuple
from datetime import datetime
import json
import sys
import argparse

# Add project root to path
sys.path.insert(0, '/home/user/RTATDP')
from tests.fixtures.sample_data import SampleDataGenerator


class PerformanceBenchmark:
    """Performance benchmarking suite"""

    def __init__(self, api_url: str = "http://localhost:8000", verbose: bool = False):
        self.api_url = api_url
        self.verbose = verbose
        self.generator = SampleDataGenerator()
        self.results = {}

    def print_header(self, text: str):
        """Print formatted header"""
        print("\n" + "=" * 80)
        print(f"  {text}")
        print("=" * 80)

    def print_result(self, metric: str, value: str):
        """Print formatted result"""
        print(f"  {metric:<40} {value}")

    def check_api_health(self) -> bool:
        """Check if API is accessible"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ API not accessible: {e}")
            return False

    def benchmark_single_request_latency(self, iterations: int = 100) -> Dict:
        """Benchmark single request latency"""
        self.print_header("Single Request Latency Benchmark")

        events = self.generator.generate_network_events(count=iterations, threat_ratio=0.3)
        latencies = []

        print(f"  Running {iterations} single predictions...")

        for i, event in enumerate(events):
            if self.verbose and i % 10 == 0:
                print(f"  Progress: {i}/{iterations}")

            start = time.perf_counter()
            try:
                response = requests.post(
                    f"{self.api_url}/predict",
                    json={"event": event.model_dump(mode='json')},
                    timeout=10
                )
                latency = (time.perf_counter() - start) * 1000  # Convert to ms

                if response.status_code == 200:
                    latencies.append(latency)
                elif response.status_code == 503:
                    print("  ⚠️  Models not loaded, skipping benchmark")
                    return {}
            except Exception as e:
                if self.verbose:
                    print(f"  Error: {e}")

        if not latencies:
            return {}

        # Calculate statistics
        results = {
            "mean": statistics.mean(latencies),
            "median": statistics.median(latencies),
            "p50": statistics.quantiles(latencies, n=100)[49],
            "p95": statistics.quantiles(latencies, n=100)[94],
            "p99": statistics.quantiles(latencies, n=100)[98],
            "min": min(latencies),
            "max": max(latencies),
            "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0
        }

        # Print results
        self.print_result("Mean Latency:", f"{results['mean']:.2f} ms")
        self.print_result("Median Latency:", f"{results['median']:.2f} ms")
        self.print_result("P50 Latency:", f"{results['p50']:.2f} ms")
        self.print_result("P95 Latency:", f"{results['p95']:.2f} ms")
        self.print_result("P99 Latency:", f"{results['p99']:.2f} ms")
        self.print_result("Min Latency:", f"{results['min']:.2f} ms")
        self.print_result("Max Latency:", f"{results['max']:.2f} ms")
        self.print_result("Std Dev:", f"{results['stdev']:.2f} ms")

        # Check SLA (P95 < 100ms)
        sla_met = results['p95'] < 100
        self.print_result("SLA Status (P95 < 100ms):", "✅ PASS" if sla_met else "❌ FAIL")

        self.results['latency'] = results
        return results

    def benchmark_throughput(self, duration_seconds: int = 30) -> Dict:
        """Benchmark maximum throughput"""
        self.print_header(f"Throughput Benchmark ({duration_seconds}s)")

        events = self.generator.generate_network_events(count=1000, threat_ratio=0.3)
        event_index = 0
        success_count = 0
        error_count = 0

        print(f"  Sending requests for {duration_seconds} seconds...")

        start_time = time.time()
        end_time = start_time + duration_seconds

        while time.time() < end_time:
            event = events[event_index % len(events)]
            event_index += 1

            try:
                response = requests.post(
                    f"{self.api_url}/predict",
                    json={"event": event.model_dump(mode='json')},
                    timeout=5
                )
                if response.status_code == 200:
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        elapsed = time.time() - start_time
        total_requests = success_count + error_count
        throughput = success_count / elapsed

        results = {
            "duration_seconds": elapsed,
            "total_requests": total_requests,
            "successful_requests": success_count,
            "failed_requests": error_count,
            "throughput_rps": throughput,
            "success_rate": (success_count / total_requests * 100) if total_requests > 0 else 0
        }

        # Print results
        self.print_result("Duration:", f"{elapsed:.2f} seconds")
        self.print_result("Total Requests:", f"{total_requests:,}")
        self.print_result("Successful:", f"{success_count:,}")
        self.print_result("Failed:", f"{error_count:,}")
        self.print_result("Throughput:", f"{throughput:.2f} requests/sec")
        self.print_result("Success Rate:", f"{results['success_rate']:.2f}%")

        self.results['throughput'] = results
        return results

    def benchmark_concurrent_requests(self, concurrency: int = 50, total_requests: int = 500) -> Dict:
        """Benchmark concurrent request handling"""
        self.print_header(f"Concurrent Requests Benchmark ({concurrency} concurrent)")

        events = self.generator.generate_network_events(count=total_requests, threat_ratio=0.3)

        def make_request(event):
            start = time.perf_counter()
            try:
                response = requests.post(
                    f"{self.api_url}/predict",
                    json={"event": event.model_dump(mode='json')},
                    timeout=30
                )
                latency = (time.perf_counter() - start) * 1000
                return {
                    "success": response.status_code == 200,
                    "latency": latency,
                    "status_code": response.status_code
                }
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                return {
                    "success": False,
                    "latency": latency,
                    "error": str(e)
                }

        print(f"  Sending {total_requests} requests with {concurrency} concurrent workers...")

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            results_list = list(executor.map(make_request, events))
        elapsed = time.time() - start_time

        # Analyze results
        success_count = sum(1 for r in results_list if r["success"])
        latencies = [r["latency"] for r in results_list if r["success"]]

        results = {
            "concurrency": concurrency,
            "total_requests": total_requests,
            "successful_requests": success_count,
            "failed_requests": total_requests - success_count,
            "duration_seconds": elapsed,
            "throughput_rps": total_requests / elapsed,
            "success_rate": (success_count / total_requests * 100),
            "mean_latency": statistics.mean(latencies) if latencies else 0,
            "p95_latency": statistics.quantiles(latencies, n=100)[94] if latencies else 0
        }

        # Print results
        self.print_result("Concurrency:", str(concurrency))
        self.print_result("Total Requests:", f"{total_requests:,}")
        self.print_result("Successful:", f"{success_count:,}")
        self.print_result("Failed:", f"{total_requests - success_count:,}")
        self.print_result("Duration:", f"{elapsed:.2f} seconds")
        self.print_result("Throughput:", f"{results['throughput_rps']:.2f} requests/sec")
        self.print_result("Success Rate:", f"{results['success_rate']:.2f}%")
        self.print_result("Mean Latency:", f"{results['mean_latency']:.2f} ms")
        self.print_result("P95 Latency:", f"{results['p95_latency']:.2f} ms")

        self.results['concurrent'] = results
        return results

    def benchmark_batch_prediction(self, batch_sizes: List[int] = [10, 50, 100]) -> Dict:
        """Benchmark batch prediction endpoint"""
        self.print_header("Batch Prediction Benchmark")

        results = {}

        for batch_size in batch_sizes:
            events = self.generator.generate_network_events(count=batch_size, threat_ratio=0.3)
            events_json = [e.model_dump(mode='json') for e in events]

            print(f"\n  Testing batch size: {batch_size}")

            start = time.perf_counter()
            try:
                response = requests.post(
                    f"{self.api_url}/batch_predict",
                    json=events_json,
                    timeout=60
                )
                latency = (time.perf_counter() - start) * 1000

                if response.status_code == 200:
                    data = response.json()
                    results[batch_size] = {
                        "total_latency_ms": latency,
                        "per_item_latency_ms": latency / batch_size,
                        "successful": data.get("successful", 0),
                        "failed": data.get("failed", 0)
                    }

                    self.print_result(f"  Batch {batch_size} - Total Latency:", f"{latency:.2f} ms")
                    self.print_result(f"  Batch {batch_size} - Per Item:", f"{latency/batch_size:.2f} ms")
                    self.print_result(f"  Batch {batch_size} - Success Rate:",
                                     f"{(data.get('successful', 0) / batch_size * 100):.1f}%")
            except Exception as e:
                print(f"  ❌ Error with batch size {batch_size}: {e}")

        self.results['batch'] = results
        return results

    def benchmark_resource_usage(self, duration_seconds: int = 30) -> Dict:
        """Monitor resource usage during load"""
        self.print_header(f"Resource Usage Benchmark ({duration_seconds}s load test)")

        # Start load in background
        events = self.generator.generate_network_events(count=1000, threat_ratio=0.3)
        stop_flag = False

        def send_requests():
            event_index = 0
            while not stop_flag:
                event = events[event_index % len(events)]
                event_index += 1
                try:
                    requests.post(
                        f"{self.api_url}/predict",
                        json={"event": event.model_dump(mode='json')},
                        timeout=5
                    )
                except Exception:
                    pass

        # Monitor resources
        cpu_samples = []
        memory_samples = []

        print(f"  Monitoring resources for {duration_seconds} seconds...")

        # Start load
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            load_future = executor.submit(send_requests)

            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_info = psutil.virtual_memory()

                cpu_samples.append(cpu_percent)
                memory_samples.append(memory_info.percent)

            stop_flag = True

        results = {
            "cpu_mean": statistics.mean(cpu_samples),
            "cpu_max": max(cpu_samples),
            "memory_mean": statistics.mean(memory_samples),
            "memory_max": max(memory_samples)
        }

        # Print results
        self.print_result("Mean CPU Usage:", f"{results['cpu_mean']:.1f}%")
        self.print_result("Peak CPU Usage:", f"{results['cpu_max']:.1f}%")
        self.print_result("Mean Memory Usage:", f"{results['memory_mean']:.1f}%")
        self.print_result("Peak Memory Usage:", f"{results['memory_max']:.1f}%")

        self.results['resources'] = results
        return results

    def run_full_benchmark(self) -> Dict:
        """Run complete benchmark suite"""
        print("\n" + "=" * 80)
        print("  AI THREAT DETECTION PIPELINE - PERFORMANCE BENCHMARK")
        print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 80)

        # Check API health
        if not self.check_api_health():
            print("\n❌ API is not accessible. Exiting.")
            return {}

        print("✅ API is accessible\n")

        # Run benchmarks
        self.benchmark_single_request_latency(iterations=100)
        self.benchmark_throughput(duration_seconds=30)
        self.benchmark_concurrent_requests(concurrency=50, total_requests=500)
        self.benchmark_batch_prediction(batch_sizes=[10, 50, 100])
        self.benchmark_resource_usage(duration_seconds=30)

        # Print summary
        self.print_summary()

        return self.results

    def print_summary(self):
        """Print benchmark summary"""
        self.print_header("BENCHMARK SUMMARY")

        if 'latency' in self.results:
            self.print_result("✓ Latency P95:", f"{self.results['latency']['p95']:.2f} ms")

        if 'throughput' in self.results:
            self.print_result("✓ Throughput:", f"{self.results['throughput']['throughput_rps']:.2f} req/s")

        if 'concurrent' in self.results:
            self.print_result("✓ Concurrent (50 workers):",
                             f"{self.results['concurrent']['success_rate']:.1f}% success")

        if 'resources' in self.results:
            self.print_result("✓ Peak CPU:", f"{self.results['resources']['cpu_max']:.1f}%")
            self.print_result("✓ Peak Memory:", f"{self.results['resources']['memory_max']:.1f}%")

        # Overall assessment
        print("\n  Overall Assessment:")

        checks_passed = 0
        total_checks = 0

        if 'latency' in self.results:
            total_checks += 1
            if self.results['latency']['p95'] < 100:
                print("  ✅ Latency SLA met (P95 < 100ms)")
                checks_passed += 1
            else:
                print("  ❌ Latency SLA not met (P95 < 100ms)")

        if 'throughput' in self.results:
            total_checks += 1
            if self.results['throughput']['throughput_rps'] > 100:
                print("  ✅ Throughput acceptable (>100 req/s)")
                checks_passed += 1
            else:
                print("  ❌ Throughput below target (>100 req/s)")

        if 'concurrent' in self.results:
            total_checks += 1
            if self.results['concurrent']['success_rate'] > 95:
                print("  ✅ Concurrent handling good (>95% success)")
                checks_passed += 1
            else:
                print("  ❌ Concurrent handling needs improvement (>95% success)")

        print(f"\n  Score: {checks_passed}/{total_checks} checks passed")
        print("=" * 80 + "\n")

    def save_results(self, output_file: str):
        """Save benchmark results to JSON file"""
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "api_url": self.api_url,
                "results": self.results
            }, f, indent=2)
        print(f"✅ Results saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Performance benchmark for AI Threat Detection Pipeline")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--output", default="benchmark_results.json", help="Output file for results")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--quick", action="store_true", help="Run quick benchmark (reduced iterations)")

    args = parser.parse_args()

    benchmark = PerformanceBenchmark(api_url=args.url, verbose=args.verbose)

    if args.quick:
        print("Running quick benchmark...\n")
        benchmark.benchmark_single_request_latency(iterations=20)
        benchmark.benchmark_throughput(duration_seconds=10)
    else:
        benchmark.run_full_benchmark()

    benchmark.save_results(args.output)


if __name__ == "__main__":
    main()
