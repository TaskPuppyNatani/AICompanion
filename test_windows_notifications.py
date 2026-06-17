"""
Minimal Windows Notification Listener POC
==========================================

Test script to verify winsdk UserNotificationListener capabilities.
- Windows only
- No Rivet integration
- No HTTP
- No Qt

Usage:
    python test_windows_notifications.py

Then trigger notifications in Discord, Telegram, etc. and observe output.

Press Ctrl+C to exit.
"""

import sys
import json
from datetime import datetime

# Test: Can we import winsdk?
try:
    from winsdk.windows.ui.notifications.management import (
        UserNotificationListener,
    )
    from winsdk.windows.ui.notifications import (
        NotificationKinds,
    )
    WINSDK_AVAILABLE = True
    print("[✓] winsdk imported successfully")
except ImportError as e:
    print(f"[✗] Failed to import winsdk: {e}")
    print("\nInstall with: pip install winsdk")
    sys.exit(1)

# Test: Can we access the UserNotificationListener?
try:
    listener = UserNotificationListener.current
    print("[✓] UserNotificationListener.get_current() succeeded")
except Exception as e:
    print(f"[✗] Failed to get listener: {e}")
    print("\nThis usually means:")
    print("  - Windows version < 10 (need Win10+)")
    print("  - Notifications disabled in Settings")
    print("  - App doesn't have permission to read notifications")
    sys.exit(1)


def format_timestamp(notification):
    """Extract and format timestamp from notification."""
    try:
        # WinRT notifications have CreatedTime property
        if hasattr(notification, 'CreatedTime'):
            ts = notification.CreatedTime
            return ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
    except Exception:
        pass
    return datetime.now().isoformat()


def extract_app_name(notification):
    """Extract application name from notification."""
    try:
        # Try standard properties
        if hasattr(notification, 'AppName') and notification.AppName:
            return notification.AppName
        
        if hasattr(notification, 'AppId') and notification.AppId:
            app_id = notification.AppId
            # Parse app identity from full app ID if present
            if '!' in str(app_id):
                return str(app_id).split('!')[0]
            return str(app_id)
    except Exception:
        pass
    return "Unknown"


def extract_title(notification):
    """Extract notification title."""
    try:
        if hasattr(notification, 'SummaryText') and notification.SummaryText:
            return notification.SummaryText
    except Exception:
        pass
    return ""


def extract_body(notification):
    """Extract notification body/message preview."""
    try:
        # Try multiple possible fields
        if hasattr(notification, 'BodyText') and notification.BodyText:
            return notification.BodyText
        
        if hasattr(notification, 'MessageText') and notification.MessageText:
            return notification.MessageText
    except Exception:
        pass
    return ""


def on_notification_changed(sender, args):
    """Callback invoked when a notification is received."""
    try:
        if args is None or not hasattr(args, 'UserNotification'):
            return
        
        notification = args.UserNotification
        
        # Extract fields
        app_name = extract_app_name(notification)
        title = extract_title(notification)
        body = extract_body(notification)
        timestamp = format_timestamp(notification)
        
        # Print in structured format
        print("\n" + "="*70)
        print(f"[{timestamp}]")
        print(f"App:    {app_name}")
        print(f"Title:  {title}")
        print(f"Body:   {body}")
        print("="*70)
        
        # Debug: dump all available properties
        print_available_properties(notification, app_name)
        
    except Exception as e:
        print(f"[Error processing notification] {e}")


def print_available_properties(notification, app_name):
    """Debug helper: print all accessible properties of a notification."""
    print("\nDebug: Available fields on notification object:")
    
    # Common expected properties
    property_names = [
        'AppName', 'AppId', 'SummaryText', 'BodyText', 'MessageText',
        'CreatedTime', 'Kind', 'Priority', 'Tag', 'Group',
        'BadgeContent', 'Sound', 'ActivationToken',
    ]
    
    for prop_name in property_names:
        try:
            if hasattr(notification, prop_name):
                value = getattr(notification, prop_name)
                if value:
                    print(f"  - {prop_name}: {value}")
        except Exception:
            pass


def is_discord_notification(app_name):
    """Check if notification is from Discord."""
    return "discord" in app_name.lower()


def is_telegram_notification(app_name):
    """Check if notification is from Telegram."""
    return "telegram" in app_name.lower()


def main():
    """Main entry point."""
    print("\n" + "="*70)
    print("Windows Notification Listener Test")
    print("="*70)
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    print("\nListening for notifications...")
    print("Trigger notifications from Discord, Telegram, Email, etc.")
    print("Press Ctrl+C to exit\n")
    
    # Register callback
    try:
        # Register event handler using add_notification_changed method
        token = listener.add_notification_changed(on_notification_changed)
        print("[✓] Notification listener registered\n")
    except Exception as e:
        print(f"[✗] Failed to register listener: {e}")
        sys.exit(1)
    
    # Keep script alive
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[*] Exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
