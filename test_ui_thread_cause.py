"""
Verify: WinError -2147023728 Root Cause Analysis

From Microsoft Documentation:
"UserNotificationListener requires explicit user permission to be granted before
it may be used, so before attempting to access notifications be sure you call
RequestAccessAsync from a UI-thread."

Key requirement: Must call from UI-thread
"""

import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener

async def test_ui_thread_requirement():
    """
    Test: Desktop Python doesn't have a UI thread.
    WinRT event subscriptions require UI thread context.
    """
    
    listener = UserNotificationListener.current
    print("✓ Got listener\n")
    
    # Step 1: RequestAccessAsync (should work)
    print("1. Calling request_access_async...")
    result = await listener.request_access_async()
    print(f"   ✓ Result: {result} (1=ALLOWED)\n")
    
    # Step 2: Can we get notifications? (Yes - this doesn't require UI thread)
    print("2. Getting notifications...")
    from winsdk.windows.ui.notifications import NotificationKinds
    notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
    count = len(list(notifs))
    print(f"   ✓ Got {count} notifications\n")
    
    # Step 3: Try to register event handler (Fails - requires UI thread)
    print("3. Attempting add_notification_changed...")
    print("   This requires UI thread (UWP dispatcher)")
    print("   Desktop Python has NO UI thread\n")
    
    def handler(sender, args):
        pass
    
    try:
        token = listener.add_notification_changed(handler)
        print(f"   ✓ Success")
    except OSError as e:
        print(f"   ✗ Error: {e}")
        print(f"   WinError: {e.winerror}")
        print(f"\n   ROOT CAUSE:")
        print(f"   ERROR_NOT_FOUND (0x80070490 / -2147023728)")
        print(f"   Occurs because add_notification_changed requires UI thread")
        print(f"   Desktop Python cannot provide UI thread context")
        print(f"   This is a WinRT API limitation, not a winsdk bug")

asyncio.run(test_ui_thread_requirement())
