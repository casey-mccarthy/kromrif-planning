"""
Discord webhook handler for receiving and processing Discord events.
"""

import hmac
import hashlib
import json
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from ..discord_signals import discord_webhook_received
from ..permissions import DiscordWebhookPermission

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class DiscordWebhookView(View):
    """
    Handle incoming Discord webhooks.
    Validates webhook signatures and processes events.
    """
    
    def post(self, request, *args, **kwargs):
        """Process incoming Discord webhook."""
        try:
            # Verify webhook signature if secret is configured
            if hasattr(settings, 'DISCORD_WEBHOOK_SECRET'):
                if not self.verify_webhook_signature(request):
                    logger.warning("Invalid webhook signature")
                    return JsonResponse(
                        {'error': 'Invalid signature'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            
            # Parse webhook data
            try:
                data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook payload")
                return JsonResponse(
                    {'error': 'Invalid JSON'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract event type
            event_type = data.get('t')  # Discord event type
            event_data = data.get('d', {})  # Discord event data
            
            if not event_type:
                logger.warning("Webhook missing event type")
                return JsonResponse(
                    {'error': 'Missing event type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Log the webhook
            logger.info(f"Received Discord webhook: {event_type}")
            logger.debug(f"Webhook data: {json.dumps(data, indent=2)}")
            
            # Send signal for processing
            discord_webhook_received.send(
                sender=self.__class__,
                event_type=event_type,
                data=event_data
            )
            
            # Return success response
            return JsonResponse({'status': 'processed'})
            
        except Exception as e:
            logger.error(f"Error processing Discord webhook: {str(e)}", exc_info=True)
            return JsonResponse(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def verify_webhook_signature(self, request):
        """
        Verify Discord webhook signature.
        
        Args:
            request: HTTP request object
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Get signature from headers
            signature = request.headers.get('X-Signature-Ed25519')
            timestamp = request.headers.get('X-Signature-Timestamp')
            
            if not signature or not timestamp:
                return False
            
            # Verify signature using webhook secret
            webhook_secret = settings.DISCORD_WEBHOOK_SECRET
            message = timestamp + request.body.decode('utf-8')
            
            # Discord uses Ed25519 signatures
            # This is a placeholder - actual implementation would use PyNaCl
            # For now, we'll use HMAC as a simple example
            expected_signature = hmac.new(
                webhook_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False


class DiscordWebhookAPIView(APIView):
    """
    DRF-based webhook handler with additional features.
    """
    authentication_classes = []  # Webhooks don't use standard auth
    permission_classes = [DiscordWebhookPermission]  # Custom webhook permission
    
    def post(self, request):
        """Process Discord webhook with DRF."""
        # Webhook verification is handled by permission class
        
        event_type = request.data.get('t')
        event_data = request.data.get('d', {})
        
        # Process specific event types
        response_data = self.process_event(event_type, event_data)
        
        return Response(response_data)
    
    def verify_discord_webhook(self, request):
        """Verify the webhook is from Discord."""
        # Implementation depends on Discord's webhook security model
        # This is a placeholder
        webhook_token = request.headers.get('X-Webhook-Token')
        expected_token = getattr(settings, 'DISCORD_WEBHOOK_TOKEN', None)
        
        if expected_token and webhook_token != expected_token:
            return False
        
        return True
    
    def process_event(self, event_type, event_data):
        """
        Process specific Discord events.
        
        Args:
            event_type: Discord event type
            event_data: Event data
            
        Returns:
            dict: Response data
        """
        # Send signal for processing
        discord_webhook_received.send(
            sender=self.__class__,
            event_type=event_type,
            data=event_data
        )
        
        # Event-specific processing
        processors = {
            'GUILD_MEMBER_ADD': self.process_member_add,
            'GUILD_MEMBER_REMOVE': self.process_member_remove,
            'GUILD_MEMBER_UPDATE': self.process_member_update,
            'MESSAGE_CREATE': self.process_message_create,
            'INTERACTION_CREATE': self.process_interaction_create,
        }
        
        processor = processors.get(event_type)
        if processor:
            return processor(event_data)
        
        return {'status': 'processed', 'event_type': event_type}
    
    def process_member_add(self, data):
        """Process guild member add event."""
        user_data = data.get('user', {})
        logger.info(f"New member joined: {user_data.get('username')} ({user_data.get('id')})")
        return {'status': 'member_added'}
    
    def process_member_remove(self, data):
        """Process guild member remove event."""
        user_data = data.get('user', {})
        logger.info(f"Member left: {user_data.get('username')} ({user_data.get('id')})")
        return {'status': 'member_removed'}
    
    def process_member_update(self, data):
        """Process guild member update event."""
        user_data = data.get('user', {})
        logger.info(f"Member updated: {user_data.get('username')} ({user_data.get('id')})")
        return {'status': 'member_updated'}
    
    def process_message_create(self, data):
        """Process message create event."""
        # This would handle Discord messages if needed
        return {'status': 'message_processed'}
    
    def process_interaction_create(self, data):
        """Process interaction create event (slash commands, buttons, etc.)."""
        interaction_type = data.get('type')
        logger.info(f"Interaction received: type {interaction_type}")
        return {'status': 'interaction_processed'}