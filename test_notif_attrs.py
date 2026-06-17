"""Inspect properties of notification objects"""
import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener
from winsdk.windows.ui.notifications import NotificationKinds

async def inspect_notifications():
    """Inspect actual properties of notification objects."""
    listener = UserNotificationListener.current
    
    # Get notifications
    async_op = listener.get_notifications_async(NotificationKinds.TOAST)
    notifications = await async_op
    notif_list = list(notifications)
    
    if notif_list:
        notif = notif_list[0]
        print(f"Notification object: {notif}")
        print(f"Type: {type(notif)}")
        print(f"\nAvailable attributes:")
        
        for attr in sorted(dir(notif)):
            if not attr.startswith('_'):
                try:
                    value = getattr(notif, attr)
                    if not callable(value):
                        print(f"  {attr}: {value}")
                except Exception as e:
                    print(f"  {attr}: [Error: {e}]")

asyncio.run(inspect_notifications())
