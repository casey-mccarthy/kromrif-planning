"""
Retry utilities and error handling for Discord API interactions.
Implements exponential backoff and comprehensive error handling.
"""

import time
import logging
import random
from functools import wraps
from typing import Callable, Any, Optional, Union, Type, Tuple
from django.conf import settings
import requests
from rest_framework import status

logger = logging.getLogger(__name__)


class DiscordAPIError(Exception):
    """Base exception for Discord API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(message)


class DiscordRateLimitError(DiscordAPIError):
    """Raised when Discord API rate limit is exceeded."""
    
    def __init__(self, retry_after: float, message: str = None):
        self.retry_after = retry_after
        message = message or f"Rate limited. Retry after {retry_after} seconds"
        super().__init__(message, status_code=429)


class DiscordConnectionError(DiscordAPIError):
    """Raised when connection to Discord API fails."""
    pass


class DiscordServerError(DiscordAPIError):
    """Raised when Discord API returns a server error."""
    pass


class DiscordClientError(DiscordAPIError):
    """Raised when Discord API returns a client error."""
    pass


def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (DiscordConnectionError, DiscordServerError, DiscordRateLimitError)
):
    """
    Decorator that implements exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for delay between retries
        jitter: Add random jitter to prevent thundering herd
        retry_on: Tuple of exception types to retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries. "
                            f"Last error: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    # Special handling for rate limit errors
                    if isinstance(e, DiscordRateLimitError):
                        delay = max(delay, e.retry_after)
                    
                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}. "
                        f"Retrying in {delay:.2f} seconds. Error: {str(e)}"
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    # Don't retry on other types of exceptions
                    logger.error(f"Function {func.__name__} failed with non-retryable error: {str(e)}")
                    raise
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def handle_discord_response(response: requests.Response) -> dict:
    """
    Handle Discord API response and raise appropriate exceptions.
    
    Args:
        response: requests.Response object
        
    Returns:
        Parsed JSON response data
        
    Raises:
        DiscordRateLimitError: If rate limited
        DiscordClientError: If client error (4xx)
        DiscordServerError: If server error (5xx)
        DiscordAPIError: For other API errors
    """
    try:
        response_data = response.json() if response.content else {}
    except ValueError:
        response_data = {}
    
    if response.status_code == 429:
        # Rate limited
        retry_after = response_data.get('retry_after', 1.0)
        raise DiscordRateLimitError(
            retry_after=retry_after,
            message=f"Discord API rate limited. Retry after {retry_after} seconds"
        )
    
    elif 400 <= response.status_code < 500:
        # Client error
        error_message = response_data.get('message', f'Client error: {response.status_code}')
        raise DiscordClientError(
            message=error_message,
            status_code=response.status_code,
            response_data=response_data
        )
    
    elif 500 <= response.status_code < 600:
        # Server error
        error_message = response_data.get('message', f'Server error: {response.status_code}')
        raise DiscordServerError(
            message=error_message,
            status_code=response.status_code,
            response_data=response_data
        )
    
    elif not response.ok:
        # Other HTTP errors
        raise DiscordAPIError(
            message=f"Discord API error: {response.status_code}",
            status_code=response.status_code,
            response_data=response_data
        )
    
    return response_data


@exponential_backoff(max_retries=3)
def make_discord_request(
    method: str,
    url: str,
    headers: Optional[dict] = None,
    data: Optional[dict] = None,
    json_data: Optional[dict] = None,
    timeout: Optional[float] = None
) -> dict:
    """
    Make a request to Discord API with error handling and retries.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Discord API URL
        headers: Request headers
        data: Form data
        json_data: JSON data
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response
        
    Raises:
        DiscordConnectionError: If connection fails
        DiscordRateLimitError: If rate limited
        DiscordClientError: If client error
        DiscordServerError: If server error
    """
    timeout = timeout or getattr(settings, 'DISCORD_API_TIMEOUT', 30)
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            data=data,
            json=json_data,
            timeout=timeout
        )
        
        return handle_discord_response(response)
        
    except requests.exceptions.ConnectTimeout:
        raise DiscordConnectionError("Connection to Discord API timed out")
    
    except requests.exceptions.ReadTimeout:
        raise DiscordConnectionError("Discord API request timed out")
    
    except requests.exceptions.ConnectionError as e:
        raise DiscordConnectionError(f"Failed to connect to Discord API: {str(e)}")
    
    except requests.exceptions.RequestException as e:
        raise DiscordConnectionError(f"Discord API request failed: {str(e)}")


class DiscordErrorHandler:
    """
    Context manager for handling Discord API errors with consistent logging.
    """
    
    def __init__(self, operation_name: str, log_errors: bool = True):
        self.operation_name = operation_name
        self.log_errors = log_errors
        self.error = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.error = exc_val
            
            if self.log_errors:
                if isinstance(exc_val, DiscordRateLimitError):
                    logger.warning(
                        f"Discord operation '{self.operation_name}' rate limited. "
                        f"Retry after {exc_val.retry_after} seconds"
                    )
                elif isinstance(exc_val, DiscordClientError):
                    logger.error(
                        f"Discord operation '{self.operation_name}' failed with client error: "
                        f"{exc_val.message} (Status: {exc_val.status_code})"
                    )
                elif isinstance(exc_val, DiscordServerError):
                    logger.error(
                        f"Discord operation '{self.operation_name}' failed with server error: "
                        f"{exc_val.message} (Status: {exc_val.status_code})"
                    )
                elif isinstance(exc_val, DiscordConnectionError):
                    logger.error(
                        f"Discord operation '{self.operation_name}' failed with connection error: "
                        f"{exc_val.message}"
                    )
                else:
                    logger.error(
                        f"Discord operation '{self.operation_name}' failed with unexpected error: "
                        f"{str(exc_val)}"
                    )
        
        # Don't suppress exceptions, let them propagate
        return False
    
    @property
    def success(self) -> bool:
        """True if no error occurred."""
        return self.error is None
    
    @property
    def failed(self) -> bool:
        """True if an error occurred."""
        return self.error is not None


def safe_discord_operation(operation_name: str, default_return: Any = None):
    """
    Decorator that safely executes Discord operations with error handling.
    Returns default_return if operation fails.
    
    Args:
        operation_name: Name of the operation for logging
        default_return: Value to return if operation fails
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with DiscordErrorHandler(operation_name) as error_handler:
                try:
                    return func(*args, **kwargs)
                except Exception:
                    # Error is already logged by error handler
                    return default_return
            
        return wrapper
    return decorator


# Circuit breaker pattern for Discord API
class CircuitBreaker:
    """
    Circuit breaker implementation for Discord API to prevent cascade failures.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = DiscordAPIError
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if self.state == 'OPEN':
                if time.time() - self.last_failure_time < self.recovery_timeout:
                    raise DiscordAPIError("Circuit breaker is OPEN")
                else:
                    self.state = 'HALF_OPEN'
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except self.expected_exception as e:
                self._on_failure()
                raise
            
        return wrapper
    
    def _on_success(self):
        """Reset circuit breaker on successful operation."""
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        """Handle failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures. "
                f"Will retry in {self.recovery_timeout} seconds"
            )


# Pre-configured circuit breaker for Discord webhook operations
discord_webhook_circuit_breaker = CircuitBreaker(
    failure_threshold=getattr(settings, 'DISCORD_CIRCUIT_BREAKER_THRESHOLD', 5),
    recovery_timeout=getattr(settings, 'DISCORD_CIRCUIT_BREAKER_TIMEOUT', 60.0)
)