from django.urls import re_path
from .consumers import OrderEventsConsumer

websocket_urlpatterns = [
    re_path(r"ws/orders/$", OrderEventsConsumer.as_asgi()),
]
