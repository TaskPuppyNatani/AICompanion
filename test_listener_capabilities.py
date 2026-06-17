"""Test if a Windows message dispatcher is required"""
import sys
import asyncio
from winsdk.windows.ui.notifications.management import UserNotificationListener

def test_synchronous_registration():
    """Test immediate synchronous registration without dispatcher."""
    listener = UserNotificationListener.current
    print(f"✓ Got listener: {listener}\n")
    
    def handler(sender, args):
        print(f"Event fired!")
    
    print(f"Attempting synchronous add_notification_changed...")
    try:
        token = listener.add_notification_changed(handler)
        print(f"✓ Success: {token}")
        return True
    except OSError as e:
        print(f"✗ OSError: {e}")
        print(f"  winerror: {e.winerror}")
        return False

def test_with_winui_dispatcher():
    """Test with WinUI/UWP dispatcher if available."""
    try:
        from winsdk.windows.ui.core import CoreDispatcher, DispatcherQueue
        print(f"✓ DispatcherQueue available")
    except ImportError:
        print(f"✗ DispatcherQueue not available (expected on desktop Python)")
        return False
    
    # This won't work on desktop Python without a running UWP app
    print(f"  (Dispatcher requires running UWP app context)")
    return False

def test_listener_notifications_capability():
    """Check listener properties and capabilities."""
    listener = UserNotificationListener.current
    print(f"\nInspecting listener object...")
    
    # List all methods and properties
    methods = [m for m in dir(listener) if not m.startswith('_')]
    print(f"\nAvailable on listener:")
    for method in sorted(methods):
        print(f"  - {method}")
    
    # Try to get notifications
    print(f"\nTrying get_notifications_async...")
    try:
        from winsdk.windows.ui.notifications import NotificationKinds
        async_op = listener.get_notifications_async(NotificationKinds.TOAST)
        print(f"✓ Got notifications async operation: {async_op}")
    except Exception as e:
        print(f"✗ Error: {e}")

def test_clear_notifications():
    """Test if clear_notifications works."""
    listener = UserNotificationListener.current
    print(f"\nTrying clear_notifications...")
    try:
        listener.clear_notifications()
        print(f"✓ clear_notifications succeeded")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

# Run tests
print("="*70)
print("Test 1: Synchronous registration")
print("="*70)
test_synchronous_registration()

print("\n" + "="*70)
print("Test 2: Dispatcher availability")
print("="*70)
test_with_winui_dispatcher()

print("\n" + "="*70)
print("Test 3: Listener capabilities")
print("="*70)
test_listener_notifications_capability()

print("\n" + "="*70)
print("Test 4: clear_notifications")
print("="*70)
test_clear_notifications()
