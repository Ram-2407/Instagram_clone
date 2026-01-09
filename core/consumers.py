import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async
from .models import MessageThread, Message

class NotificationsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user', AnonymousUser())
        if not user.is_authenticated:
            await self.close()
            return
        self.group_name = f'notif_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Listener only; no need to handle incoming messages.
        pass

    async def notif_message(self, event):
        await self.send(text_data=json.dumps({
            'title': event.get('title', 'Notification'),
            'text': event.get('text', ''),
            'created_at': event.get('created_at', ''),
        }))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group = f'chat_{self.thread_id}'
        user = self.scope.get('user', AnonymousUser())
        if not user.is_authenticated or not await self._is_participant(user.id, self.thread_id):
            await self.close()
            return
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data or '{}')
        text = data.get('text', '').strip()
        user = self.scope['user']
        if not text:
            return
        msg = await self._save_message(self.thread_id, user.id, text)
        await self.channel_layer.group_send(self.room_group, {
            'type': 'chat.message',
            'message_id': msg['id'],
            'sender': msg['sender'],
            'text': msg['text'],
            'created_at': msg['created_at'],
        })

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @sync_to_async
    def _is_participant(self, user_id, thread_id):
        try:
            t = MessageThread.objects.get(id=thread_id)
            return t.participants.filter(id=user_id).exists()
        except MessageThread.DoesNotExist:
            return False

    @sync_to_async
    def _save_message(self, thread_id, sender_id, text):
        thread = MessageThread.objects.get(id=thread_id)
        m = Message.objects.create(thread=thread, sender_id=sender_id, text=text)
        return {'id': m.id, 'sender': m.sender.username, 'text': m.text, 'created_at': m.created_at.isoformat()}