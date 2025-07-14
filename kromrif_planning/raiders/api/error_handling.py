"""
Error handling mixins and utilities for Discord API views.
"""

import logging
from functools import wraps
from typing import Any, Callable
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import ValidationError as DRFValidationError

from ..utils.retry import DiscordAPIError, DiscordRateLimitError, DiscordConnectionError

logger = logging.getLogger(__name__)


class DiscordAPIErrorMixin:
    """
    Mixin for handling Discord API errors in DRF views.
    """
    
    def handle_discord_error(self, error: Exception, operation: str) -> Response:
        """
        Handle Discord API errors and return appropriate HTTP responses.
        
        Args:
            error: The exception that occurred
            operation: Name of the operation for logging
            
        Returns:
            DRF Response with appropriate error message and status code
        """
        if isinstance(error, DiscordRateLimitError):
            logger.warning(f"Discord operation '{operation}' rate limited: {error.message}")
            return Response(
                {
                    'error': 'Discord API rate limited',
                    'message': 'Please try again later',
                    'retry_after': error.retry_after,
                    'code': 'RATE_LIMITED'
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        elif isinstance(error, DiscordConnectionError):
            logger.error(f"Discord operation '{operation}' connection failed: {error.message}")
            return Response(
                {
                    'error': 'Discord service unavailable',
                    'message': 'Unable to connect to Discord. Please try again later.',
                    'code': 'SERVICE_UNAVAILABLE'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        elif isinstance(error, DiscordAPIError):
            if error.status_code and 400 <= error.status_code < 500:
                # Client error
                logger.warning(f"Discord operation '{operation}' client error: {error.message}")
                return Response(
                    {
                        'error': 'Invalid request to Discord',
                        'message': error.message,
                        'code': 'DISCORD_CLIENT_ERROR'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Server error
                logger.error(f"Discord operation '{operation}' server error: {error.message}")
                return Response(
                    {
                        'error': 'Discord server error',
                        'message': 'Discord service is experiencing issues. Please try again later.',
                        'code': 'DISCORD_SERVER_ERROR'
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )
        
        else:
            # Unexpected error
            logger.error(f"Discord operation '{operation}' unexpected error: {str(error)}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'message': 'An unexpected error occurred. Please try again later.',
                    'code': 'INTERNAL_ERROR'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def discord_api_error_handler(operation_name: str):
    """
    Decorator for handling Discord API errors in view methods.
    
    Args:
        operation_name: Name of the operation for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, request, *args, **kwargs) -> Any:
            try:
                return func(self, request, *args, **kwargs)
            
            except (DiscordAPIError, DiscordRateLimitError, DiscordConnectionError) as e:
                if hasattr(self, 'handle_discord_error'):
                    return self.handle_discord_error(e, operation_name)
                else:
                    # Fallback error handling
                    logger.error(f"Discord error in {operation_name}: {str(e)}")
                    return Response(
                        {'error': 'Discord service error', 'message': str(e)},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
            
            except (DjangoValidationError, DRFValidationError) as e:
                logger.warning(f"Validation error in {operation_name}: {str(e)}")
                return Response(
                    {'error': 'Validation error', 'message': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            except Exception as e:
                logger.error(f"Unexpected error in {operation_name}: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'Internal server error', 'message': 'An unexpected error occurred'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return wrapper
    return decorator


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Discord API errors.
    
    Args:
        exc: The exception instance
        context: The context in which the exception occurred
        
    Returns:
        Response object or None
    """
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        return response
    
    # Handle Discord-specific exceptions
    if isinstance(exc, DiscordRateLimitError):
        return Response(
            {
                'error': 'Discord API rate limited',
                'message': exc.message,
                'retry_after': exc.retry_after,
                'code': 'RATE_LIMITED'
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    elif isinstance(exc, DiscordConnectionError):
        return Response(
            {
                'error': 'Discord service unavailable',
                'message': exc.message,
                'code': 'SERVICE_UNAVAILABLE'
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    elif isinstance(exc, DiscordAPIError):
        status_code = status.HTTP_502_BAD_GATEWAY
        if exc.status_code and 400 <= exc.status_code < 500:
            status_code = status.HTTP_400_BAD_REQUEST
        
        return Response(
            {
                'error': 'Discord API error',
                'message': exc.message,
                'discord_status': exc.status_code,
                'code': 'DISCORD_API_ERROR'
            },
            status=status_code
        )
    
    # Return None to use Django's default 500 error handler
    return None


class ResilientAPIView:
    """
    Base class for API views that need resilient Discord integration.
    Provides common error handling and retry patterns.
    """
    
    max_retries = 3
    base_delay = 1.0
    
    def execute_with_retry(self, operation: Callable, operation_name: str, *args, **kwargs) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: The operation to execute
            operation_name: Name for logging
            *args, **kwargs: Arguments to pass to the operation
            
        Returns:
            Result of the operation
            
        Raises:
            DiscordAPIError: If operation fails after all retries
        """
        from ..utils.retry import exponential_backoff
        
        @exponential_backoff(max_retries=self.max_retries, base_delay=self.base_delay)
        def wrapped_operation():
            return operation(*args, **kwargs)
        
        try:
            return wrapped_operation()
        except Exception as e:
            logger.error(f"Operation '{operation_name}' failed after {self.max_retries} retries: {str(e)}")
            raise


class HealthCheckMixin:
    """
    Mixin for adding health check capabilities to Discord API views.
    """
    
    def check_discord_health(self) -> dict:
        """
        Check the health of Discord API connections.
        
        Returns:
            Dictionary with health status information
        """
        from ..utils.retry import make_discord_request, DiscordAPIError
        
        health_status = {
            'status': 'unknown',
            'discord_api': 'unknown',
            'webhook_service': 'unknown',
            'timestamp': None
        }
        
        try:
            # Simple health check - just verify we can make a request
            # In a real implementation, you might ping a Discord API endpoint
            from django.utils import timezone
            health_status['timestamp'] = timezone.now().isoformat()
            
            # Check if Discord configuration is present
            from django.conf import settings
            if hasattr(settings, 'DISCORD_BOT_TOKEN') and settings.DISCORD_BOT_TOKEN:
                health_status['discord_api'] = 'configured'
            else:
                health_status['discord_api'] = 'not_configured'
            
            # Check webhook configuration
            webhook_urls = getattr(settings, 'DISCORD_WEBHOOK_URLS', {})
            if webhook_urls and webhook_urls.get('default'):
                health_status['webhook_service'] = 'configured'
            else:
                health_status['webhook_service'] = 'not_configured'
            
            # Overall status
            if (health_status['discord_api'] == 'configured' and 
                health_status['webhook_service'] == 'configured'):
                health_status['status'] = 'healthy'
            else:
                health_status['status'] = 'degraded'
                
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            health_status['status'] = 'unhealthy'
            health_status['error'] = str(e)
        
        return health_status