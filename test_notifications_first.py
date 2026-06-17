"""Test if listener requires existing notifications"""
import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
from winsdk.windows.ui.notifications import NotificationKinds

async def test_get_notifications_then_subscribe():
    """Get existing notifications first, then try to subscribe."""
    listener = UserNotificationListener.current
    print(f"✓ Got listener: {listener}\n")
    
    # Check access
    status = listener.get_access_status()
    print(f"Access status: {status} (1=ALLOWED)\n")
    
    # Try to get existing notifications
    print(f"Getting existing notifications...")
    try:
        async_op = listener.get_notifications_async(NotificationKinds.TOAST)
        notifications = await async_op
        print(f"✓ Got IVectorView: {notifications}")
        print(f"  Type: {type(notifications)}")
        
        # Count notifications
        try:
            count = len(notifications)
            print(f"  Notification count: {count}")
            
            # List them
            for i, notif in enumerate(notifications):
                print(f"    [{i}] {notif}")
        except Exception as e:
            print(f"  Could not count: {e}")
    
    except Exception as e:
        print(f"✗ Error getting notifications: {e}\n")
    
    # Try to subscribe to changes
    print(f"\nAttempting add_notification_changed...")
    
    def handler(sender, args):
        print(f"Notification changed!")
    
    try:
        token = listener.add_notification_changed(handler)
        print(f"✓ Successfully subscribed! Token: {token}")
    except Exception as e:
        print(f"✗ Error: {e}")
        if hasattr(e, 'winerror'):
            print(f"  WinError: {e.winerror}")
            
            # Decode the error
            if e.winerror == -2147023728:
                print(f"\n  ERROR_NOT_FOUND (0x80070490)")
                print(f"  This can mean:")
                print(f"    - No notifications exist to listen to")
                print(f"    - Listener not initialized in notification system")
                print(f"    - Permission issue at system level")

# Run test
asyncio.run(test_get_notifications_then_subscribe())
