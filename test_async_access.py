"""Test if request_access_async must be awaited before add_notification_changed"""
import asyncio
from winsdk.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)

async def test_with_async_access():
    """Test event registration after awaiting request_access_async."""
    listener = UserNotificationListener.current
    print(f"✓ Got listener: {listener}\n")
    
    # Check current access status
    status = listener.get_access_status()
    print(f"Initial access status: {status} (1=ALLOWED, 2=DENIED)")
    
    # Call request_access_async and await result
    print(f"\nCalling request_access_async()...")
    async_op = listener.request_access_async()
    print(f"Got IAsyncOperation: {async_op}")
    
    # Try to await it
    try:
        result = await async_op
        print(f"✓ Awaited result: {result}")
    except Exception as e:
        print(f"✗ Error awaiting: {e}")
        result = None
    
    # Check access status again
    status_after = listener.get_access_status()
    print(f"\nAccess status after request: {status_after}")
    
    # Now try add_notification_changed
    def on_notification(sender, args):
        print(f"Notification event!")
    
    print(f"\nTrying add_notification_changed after await...")
    try:
        token = listener.add_notification_changed(on_notification)
        print(f"✓ Success! Token: {token}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        print(f"Error code: {e.errno if hasattr(e, 'errno') else 'N/A'}")
        import ctypes
        if hasattr(e, 'winerror'):
            print(f"WinError: {e.winerror}")
        return False

# Run test
asyncio.run(test_with_async_access())
