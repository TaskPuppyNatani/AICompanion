"""Test the correct event subscription API"""
from winsdk.windows.ui.notifications.management import UserNotificationListener

# Get listener
listener = UserNotificationListener.current
print(f"✓ Got listener: {listener}")

# Check if add_notification_changed exists
print(f"\nMethod exists: {hasattr(listener, 'add_notification_changed')}")

# Define callback
def on_notification_changed(sender, args):
    print(f"Notification event received. Sender: {sender}, Args: {args}")

# Try to register
print(f"\nTrying to register handler with add_notification_changed...")
try:
    token = listener.add_notification_changed(on_notification_changed)
    print(f"✓ Successfully registered handler!")
    print(f"Token type: {type(token)}")
    print(f"Token value: {token}")
except Exception as e:
    print(f"✗ Error: {e}")
    print(f"Error type: {type(e)}")
