"""Test operations on existing notifications"""
import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener
from winsdk.windows.ui.notifications import NotificationKinds

async def test_notification_operations():
    """Try various operations on the listener."""
    listener = UserNotificationListener.current
    print(f"✓ Got listener\n")
    
    # Get existing notifications
    print("1. Getting existing notifications...")
    async_op = listener.get_notifications_async(NotificationKinds.TOAST)
    notifications = await async_op
    
    notif_list = list(notifications)
    print(f"✓ Found {len(notif_list)} notifications\n")
    
    # Try to get notification by ID
    if notif_list:
        first_notif = notif_list[0]
        print(f"2. Inspecting first notification...")
        
        # Try to get properties
        try:
            # Try to extract ID if available
            if hasattr(first_notif, 'Id'):
                notif_id = first_notif.Id
                print(f"   Has Id: {notif_id}")
            
            # Get it again by ID
            print(f"\n3. Trying to get_notification by ID...")
            retrieved = listener.get_notification(notif_id)
            print(f"   ✓ Retrieved: {retrieved}")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    
    # Try remove_notification (destructive - only try if safe)
    print(f"\n4. Testing remove_notification...")
    try:
        if notif_list and hasattr(notif_list[0], 'Id'):
            test_id = notif_list[0].Id
            print(f"   Attempting to remove notification {test_id}...")
            listener.remove_notification(test_id)
            print(f"   ✓ Removed successfully")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Now try add_notification_changed after performing other operations
    print(f"\n5. Attempting add_notification_changed after other operations...")
    
    def handler(sender, args):
        print(f"Event!")
    
    try:
        token = listener.add_notification_changed(handler)
        print(f"✓ Success!")
    except Exception as e:
        print(f"✗ Error: {e}")

asyncio.run(test_notification_operations())
