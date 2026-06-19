"""
Advanced Windows Notification Listener POC (with async support)
================================================================

More robust version that handles WinRT async operations properly.
Use this if the basic version has threading/event loop issues.

Usage:
    python test_windows_notifications_async.py
"""

import sys
import asyncio
from datetime import datetime
from typing import Optional

WINSDK_AVAILABLE = False
try:
    from winsdk.windows.ui.notifications.management import (
        UserNotificationListener,
    )
    WINSDK_AVAILABLE = True
    print("[✓] winsdk imported successfully")
except ImportError as e:
    print(f"[✗] Failed to import winsdk: {e}")
    print("\nInstall with: pip install winsdk")
    sys.exit(1)


class WindowsNotificationMonitor:
    """Async-safe Windows notification monitor."""
    
    def __init__(self):
        self.listener: Optional[UserNotificationListener] = None
        self.token = None
        self.running = False
    
    def __del__(self):
        """Clean up on exit."""
        if self.token is not None and self.listener is not None:
            try:
                self.listener.remove_notification_changed(self.token)
            except Exception:
                pass
    
    def initialize(self) -> bool:
        """Initialize the listener."""
        try:
            self.listener = UserNotificationListener.current
            print("[✓] UserNotificationListener initialized")
            return True
        except Exception as e:
            print(f"[✗] Failed to initialize listener: {e}")
            print("\nRequirements:")
            print("  - Windows 10 or later")
            print("  - User must have granted notification permissions")
            print("  - Notifications must be enabled in Settings > Notifications")
            return False
    
    def register_callback(self) -> bool:
        """Register notification changed callback."""
        try:
            if self.listener is None:
                return False
            
            # Bind event handler using add_notification_changed method
            self.token = self.listener.add_notification_changed(self._on_notification_changed)
            print("[✓] Notification callback registered")
            return True
        except Exception as e:
            print(f"[✗] Failed to register callback: {e}")
            return False
    
    def _on_notification_changed(self, sender, args):
        """Handle notification event."""
        try:
            if args is None or not hasattr(args, 'UserNotification'):
                return
            
            notification = args.UserNotification
            self._print_notification(notification)
        except Exception as e:
            print(f"[Error] {e}")
    
    def _print_notification(self, notification):
        """Format and print notification details."""
        app_name = self._get_app_name(notification)
        title = self._get_title(notification)
        body = self._get_body(notification)
        timestamp = self._get_timestamp(notification)
        
        print("\n" + "="*70)
        print(f"📬 Notification Received")
        print("="*70)
        print(f"Timestamp:  {timestamp}")
        print(f"App:        {app_name}")
        print(f"Title:      {title}")
        print(f"Body:       {body}")
        print("="*70)
        
        # Classification
        self._classify_notification(app_name)
    
    @staticmethod
    def _get_app_name(notification) -> str:
        """Extract app name."""
        try:
            if hasattr(notification, 'AppName') and notification.AppName:
                return notification.AppName
            if hasattr(notification, 'AppId') and notification.AppId:
                app_id = str(notification.AppId)
                if '!' in app_id:
                    return app_id.split('!')[0]
                return app_id
        except Exception:
            pass
        return "Unknown"
    
    @staticmethod
    def _get_title(notification) -> str:
        """Extract title."""
        try:
            if hasattr(notification, 'SummaryText') and notification.SummaryText:
                return notification.SummaryText
        except Exception:
            pass
        return ""
    
    @staticmethod
    def _get_body(notification) -> str:
        """Extract body."""
        try:
            for field in ['BodyText', 'MessageText', 'SubtitleText']:
                if hasattr(notification, field):
                    value = getattr(notification, field)
                    if value:
                        return value
        except Exception:
            pass
        return ""
    
    @staticmethod
    def _get_timestamp(notification) -> str:
        """Extract timestamp."""
        try:
            if hasattr(notification, 'CreatedTime'):
                ts = notification.CreatedTime
                return ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)
        except Exception:
            pass
        return datetime.now().isoformat()
    
    @staticmethod
    def _classify_notification(app_name: str):
        """Classify notification by app."""
        app_lower = app_name.lower()
        
        classifications = []
        if 'discord' in app_lower:
            classifications.append("✓ Discord detected")
        if 'telegram' in app_lower:
            classifications.append("✓ Telegram detected")
        if 'outlook' in app_lower or 'mail' in app_lower or 'gmail' in app_lower:
            classifications.append("✓ Email detected")
        if 'slack' in app_lower:
            classifications.append("✓ Slack detected")
        if 'teams' in app_lower:
            classifications.append("✓ Teams detected")
        
        if classifications:
            print("\nDetected:")
            for c in classifications:
                print(f"  {c}")


async def main_async():
    """Async main."""
    monitor = WindowsNotificationMonitor()
    
    # Initialize
    if not monitor.initialize():
        return
    
    # Register callback
    if not monitor.register_callback():
        return
    
    print("\n" + "="*70)
    print("Windows Notification Listener Active")
    print("="*70)
    print("\nMonitoring for notifications...")
    print("Try these to test:")
    print("  - Open Discord and receive a message")
    print("  - Open Telegram and receive a message")
    print("  - Receive an email while Outlook/Gmail is open")
    print("  - Trigger a system notification (Ctrl+Alt+N in some apps)")
    print("\nPress Ctrl+C to exit\n")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[*] Stopping listener...")


def main():
    """Main entry point."""
    print(f"\nPython: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    if sys.platform != "win32":
        print("[✗] This script only works on Windows")
        sys.exit(1)
    
    try:
        asyncio.run(main_async())
    except Exception as e:
        print(f"[✗] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
