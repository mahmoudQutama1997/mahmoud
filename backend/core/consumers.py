from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services.eligibility import enforce_online_invariant


@database_sync_to_async
def captain_snapshot(user_id):
    from .models import CaptainProfile
    profile = CaptainProfile.objects.select_related("user").filter(user_id=user_id).first()
    if profile is None:
        return None
    return enforce_online_invariant(profile)


class OrderEventsConsumer(AsyncJsonWebsocketConsumer):
    """Order events for one authenticated user.

    Captains are NOT placed in a shared role group: order notifications reach a
    captain only through their private ``user_<id>`` group, and the publisher
    sends to it only when the central eligibility service approves.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not user.is_active:
            await self.close(code=4403)
            return
        self.user_group = f"user_{user.id}"
        self.role_group = f"role_{user.role}" if user.role == "admin" else None
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        if self.role_group:
            await self.channel_layer.group_add(self.role_group, self.channel_name)
        await self.accept()
        if user.role == "captain":
            snapshot = await captain_snapshot(user.id)
            if snapshot is not None:
                await self.send_json({"type": "captain.eligibility", "eligibility": snapshot})

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        if getattr(self, "role_group", None):
            await self.channel_layer.group_discard(self.role_group, self.channel_name)

    async def order_event(self, event):
        await self.send_json(event["payload"])
