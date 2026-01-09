"""
ASGI config for insta project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Configure Django settings **before** importing anything that uses Django models.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'insta.settings')

# Initialise the standard Django ASGI application so Django's setup() runs.
django_asgi_app = get_asgi_application()

# Import routing only after Django has been set up.
from core import routing as core_routing  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(core_routing.websocket_urlpatterns)
    ),
})