"""
Utility functions for the threat detection system
"""

import time
import functools
import logging
from typing import Callable, Any, Optional
from datetime import datetime
import structlog


logger = structlog.get_logger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        def unreliable_function():
            # ... code that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            "function_failed_retrying",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=delay,
                            error=str(e)
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            "function_failed_max_retries_exceeded",
                            function=func.__name__,
                            max_retries=max_retries,
                            error=str(e)
                        )

            raise last_exception

        return wrapper
    return decorator


def timing_decorator(func: Callable) -> Callable:
    """
    Decorator to measure function execution time

    Example:
        @timing_decorator
        def slow_function():
            time.sleep(1)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = (time.time() - start_time) * 1000  # ms

        logger.debug(
            "function_timing",
            function=func.__name__,
            elapsed_ms=round(elapsed_time, 2)
        )

        return result
    return wrapper


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default on division by zero

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if denominator is zero

    Returns:
        Result of division or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def timestamp_to_datetime(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to datetime

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        datetime object
    """
    return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convert datetime to Unix timestamp

    Args:
        dt: datetime object

    Returns:
        Unix timestamp (seconds since epoch)
    """
    return dt.timestamp()


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to maximum length

    Args:
        text: Input string
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def sanitize_ip(ip: str) -> Optional[str]:
    """
    Sanitize and validate IP address

    Args:
        ip: IP address string

    Returns:
        Sanitized IP or None if invalid
    """
    try:
        # Basic validation
        parts = ip.strip().split('.')
        if len(parts) != 4:
            return None

        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return None

        return ip.strip()

    except (ValueError, AttributeError):
        return None


def calculate_percentage(value: float, total: float, decimals: int = 2) -> float:
    """
    Calculate percentage safely

    Args:
        value: Value
        total: Total
        decimals: Number of decimal places

    Returns:
        Percentage (0-100)
    """
    if total == 0:
        return 0.0

    percentage = (value / total) * 100
    return round(percentage, decimals)


def batch_iterator(items: list, batch_size: int):
    """
    Yield successive batches from a list

    Args:
        items: List of items
        batch_size: Size of each batch

    Yields:
        Batches of items
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm
    """

    def __init__(self, max_calls: int, time_window: float):
        """
        Initialize rate limiter

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    def is_allowed(self) -> bool:
        """
        Check if a call is allowed

        Returns:
            True if allowed, False otherwise
        """
        current_time = time.time()

        # Remove old calls outside the time window
        self.calls = [
            call_time for call_time in self.calls
            if current_time - call_time < self.time_window
        ]

        # Check if we can make another call
        if len(self.calls) < self.max_calls:
            self.calls.append(current_time)
            return True

        return False

    def wait_time(self) -> float:
        """
        Calculate time to wait before next call is allowed

        Returns:
            Time to wait in seconds
        """
        if not self.calls:
            return 0.0

        current_time = time.time()
        oldest_call = self.calls[0]
        time_since_oldest = current_time - oldest_call

        if time_since_oldest >= self.time_window:
            return 0.0

        return self.time_window - time_since_oldest


def setup_logging(
    log_level: str = "INFO",
    structured: bool = True,
    log_format: str = "json"
) -> None:
    """
    Setup application logging

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        structured: Use structured logging
        log_format: Format (json or text)
    """
    if structured:
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
        ]

        if log_format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(
                logging.getLevelName(log_level.upper())
            ),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True
        )
    else:
        logging.basicConfig(
            level=logging.getLevelName(log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


# Example usage
if __name__ == "__main__":
    # Setup logging
    setup_logging(log_level="DEBUG", structured=True, log_format="json")

    # Test retry decorator
    @retry_with_backoff(max_retries=3, initial_delay=0.1)
    def flaky_function(succeed_on_attempt: int = 3):
        flaky_function.attempt = getattr(flaky_function, 'attempt', 0) + 1
        if flaky_function.attempt < succeed_on_attempt:
            raise ValueError(f"Attempt {flaky_function.attempt} failed")
        return "Success!"

    result = flaky_function(succeed_on_attempt=2)
    print(f"Result: {result}")

    # Test timing decorator
    @timing_decorator
    def slow_function():
        time.sleep(0.1)
        return "Done"

    slow_function()

    # Test rate limiter
    limiter = RateLimiter(max_calls=5, time_window=1.0)
    for i in range(10):
        if limiter.is_allowed():
            print(f"Call {i+1}: Allowed")
        else:
            print(f"Call {i+1}: Rate limited (wait {limiter.wait_time():.2f}s)")
