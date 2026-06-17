"""Test if we need permission before subscribing"""
from winsdk.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus

listener = UserNotificationListener.current
print(f"✓ Got listener: {listener}")

# Check access status
print(f"\nChecking access status...")
status = listener.get_access_status()
print(f"Access status: {status}")
print(f"Status type: {type(status)}")

# Map status to name
status_names = {
    UserNotificationListenerAccessStatus.UNSPECIFIED: "UNSPECIFIED",
    UserNotificationListenerAccessStatus.ALLOWED: "ALLOWED",
    UserNotificationListenerAccessStatus.DENIED: "DENIED",
}
print(f"Status name: {status_names.get(status, 'UNKNOWN')}")

# Try request_access_async
print(f"\nTrying request_access_async...")
try:
    async_op = listener.request_access_async()
    print(f"✓ Got async operation: {async_op}")
    print(f"Type: {type(async_op)}")
except Exception as e:
    print(f"✗ Error: {e}")
