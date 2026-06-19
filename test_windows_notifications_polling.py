"""
Standalone Windows Notification Polling POC
===========================================

Validation-only script based on the latest WinSDK findings:
- Uses polling via get_notifications_async(NotificationKinds.TOAST)
- Does not use event subscription callbacks
- Tracks notification IDs and prints newly observed notifications only
- No Rivet integration and no HTTP calls

Usage:
    .venv\\Scripts\\python.exe test_windows_notifications_polling.py
"""

import asyncio
import sys
from datetime import datetime


try:
    from winsdk.windows.ui.notifications.management import UserNotificationListener
    from winsdk.windows.ui.notifications import NotificationKinds
except ImportError as exc:
    print(f"[ERROR] Failed to import winsdk: {exc}")
    print("Install with: .venv\\Scripts\\pip.exe install winsdk")
    sys.exit(1)


POLL_INTERVAL_SECONDS = 1.0


def _safe_getattr(obj, names, default=None):
    for name in names:
        try:
            if hasattr(obj, name):
                value = getattr(obj, name)
                if value is not None:
                    return value
        except Exception:
            continue
    return default


def _safe_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _extract_notification_id(notification):
    notification_id = _safe_getattr(notification, ["id", "Id"], default=None)
    if notification_id is None:
        return None
    return str(notification_id)


def _extract_timestamp(notification):
    created_time = _safe_getattr(notification, ["created_time", "CreatedTime"], default=None)
    if created_time is None:
        return datetime.now().isoformat()

    try:
        if hasattr(created_time, "isoformat"):
            return created_time.isoformat()
    except Exception:
        pass

    return _safe_text(created_time) or datetime.now().isoformat()


def _extract_app_name(notification):
    app_name = _safe_getattr(notification, ["app_name", "AppName"], default=None)
    if app_name:
        return _safe_text(app_name)

    app_info = _safe_getattr(notification, ["app_info", "AppInfo"], default=None)
    if app_info is not None:
        display_info = _safe_getattr(app_info, ["display_info", "DisplayInfo"], default=None)
        if display_info is not None:
            display_name = _safe_getattr(display_info, ["display_name", "DisplayName"], default=None)
            if display_name:
                return _safe_text(display_name)

    app_id = _safe_getattr(notification, ["app_id", "AppId"], default=None)
    if app_id:
        app_id_text = _safe_text(app_id)
        if "!" in app_id_text:
            return app_id_text.split("!")[0]
        return app_id_text

    return "Unknown"


def _extract_text_elements(notification):
    notification_content = _safe_getattr(notification, ["notification", "Notification"], default=None)
    if notification_content is None:
        return []

    visual = _safe_getattr(notification_content, ["visual", "Visual"], default=None)
    if visual is None:
        return []

    bindings = _safe_getattr(visual, ["bindings", "Bindings"], default=None)
    if not bindings:
        return []

    try:
        for binding in bindings:
            text_elements = _safe_getattr(binding, ["get_text_elements", "GetTextElements"], default=None)
            if callable(text_elements):
                elements = text_elements()
            else:
                elements = _safe_getattr(binding, ["text_elements", "TextElements"], default=[])

            if elements:
                collected = []
                for element in elements:
                    text = _safe_getattr(element, ["text", "Text"], default="")
                    text = _safe_text(text)
                    if text:
                        collected.append(text)
                if collected:
                    return collected
    except Exception:
        return []

    return []


def _extract_title_and_body(notification):
    title = _safe_text(_safe_getattr(notification, ["summary_text", "SummaryText"], default=""))
    body = _safe_text(
        _safe_getattr(notification, ["body_text", "BodyText", "message_text", "MessageText"], default="")
    )

    if title and body:
        return title, body

    text_elements = _extract_text_elements(notification)
    if not title and len(text_elements) >= 1:
        title = text_elements[0]
    if not body and len(text_elements) >= 2:
        body = text_elements[1]

    return title, body


def _classify_source(app_name):
    app_lower = app_name.lower()
    if "discord" in app_lower:
        return "DISCORD"
    if "telegram" in app_lower:
        return "TELEGRAM"
    if any(token in app_lower for token in ["outlook", "mail", "gmail", "email"]):
        return "EMAIL"
    return "OTHER"


class PollingNotificationMonitor:
    def __init__(self, poll_interval_seconds=POLL_INTERVAL_SECONDS):
        self.poll_interval_seconds = poll_interval_seconds
        self.listener = None
        self.seen_notification_ids = set()

    async def initialize(self):
        try:
            self.listener = UserNotificationListener.current
        except Exception as exc:
            print(f"[ERROR] Failed to get UserNotificationListener.current: {exc}")
            print("This may indicate unsupported Windows version or WinRT availability issues.")
            return False

        try:
            access_status = await self.listener.request_access_async()
            access_text = _safe_text(access_status).lower()
        except Exception as exc:
            print(f"[ERROR] request_access_async failed: {exc}")
            return False

        if int(access_status) != 1:
            print(f"[ERROR] Notification access not granted. Status: {access_status}")
            print("Enable notification access in Windows Settings and try again.")
            return False

        try:
            existing_notifications = await self.listener.get_notifications_async(NotificationKinds.TOAST)
        except Exception as exc:
            print(f"[ERROR] Initial get_notifications_async failed: {exc}")
            return False

        for notification in existing_notifications:
            notification_id = _extract_notification_id(notification)
            if notification_id is not None:
                self.seen_notification_ids.add(notification_id)

        print("[OK] Listener initialized with polling mode.")
        print(f"[OK] Poll interval: {self.poll_interval_seconds:.1f}s")
        print(f"[OK] Baseline notifications tracked: {len(self.seen_notification_ids)}")
        return True

    async def run(self):
        print("\nPolling for new Windows toast notifications...")
        print("Focus validation: Discord, Telegram, and Email")
        print("Press Ctrl+C to exit.\n")

        while True:
            try:
                notifications = await self.listener.get_notifications_async(NotificationKinds.TOAST)
            except Exception as exc:
                print(f"[WARN] Poll failed: {exc}")
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            for notification in notifications:
                notification_id = _extract_notification_id(notification)

                if notification_id is None:
                    continue

                if notification_id in self.seen_notification_ids:
                    continue

                self.seen_notification_ids.add(notification_id)
                self._print_notification(notification)

            await asyncio.sleep(self.poll_interval_seconds)

    @staticmethod
    def _print_notification(notification):
        timestamp = _extract_timestamp(notification)
        app_name = _extract_app_name(notification)
        title, body = _extract_title_and_body(notification)
        source_type = _classify_source(app_name)

        print("=" * 70)
        print(f"timestamp: {timestamp}")
        print(f"app name:  {app_name}")
        print(f"title:     {title}")
        print(f"body:      {body}")
        print(f"source:    {source_type}")
        print("=" * 70)


async def _main_async():
    monitor = PollingNotificationMonitor(poll_interval_seconds=POLL_INTERVAL_SECONDS)
    is_ready = await monitor.initialize()
    if not is_ready:
        return 1

    try:
        await monitor.run()
    except KeyboardInterrupt:
        print("\nExiting notification polling monitor.")
        return 0

    return 0


def main():
    if sys.platform != "win32":
        print("[ERROR] This script only runs on Windows.")
        return 1

    try:
        return asyncio.run(_main_async())
    except KeyboardInterrupt:
        print("\nExiting notification polling monitor.")
        return 0
    except Exception as exc:
        print(f"[ERROR] Fatal runtime error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())