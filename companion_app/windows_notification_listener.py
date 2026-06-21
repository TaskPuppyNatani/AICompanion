import asyncio
import sys
import threading
from collections import deque
from datetime import datetime

import requests

from config import NOTIFY_ENDPOINT_URL
from companion_app.notification_filters import should_process_notification


POLL_INTERVAL_SECONDS = 1.0
POST_TIMEOUT_SECONDS = 3.0
MAX_TRACKED_NOTIFICATION_IDS = 1000
TRIM_COUNT_ON_OVERFLOW = 100


class WindowsNotificationListenerThread(threading.Thread):
    def __init__(self, notify_endpoint_url=NOTIFY_ENDPOINT_URL, poll_interval_seconds=POLL_INTERVAL_SECONDS):
        super().__init__(daemon=True)
        self.notify_endpoint_url = notify_endpoint_url
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._listener = None
        self._seen_notification_ids = set()
        self._seen_notification_order = deque()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            print(f"Windows notification listener stopped with error: {e}")

    async def _run_async(self):
        if sys.platform != "win32":
            print("Windows notification listener is disabled on non-Windows platforms.")
            return

        try:
            from winsdk.windows.ui.notifications.management import UserNotificationListener
            from winsdk.windows.ui.notifications import NotificationKinds
        except Exception as e:
            print(f"Windows notification listener unavailable (winsdk import failed): {e}")
            return

        try:
            self._listener = UserNotificationListener.current
            access_status = await self._listener.request_access_async()
        except Exception as e:
            print(f"Windows notification listener initialization failed: {e}")
            return

        if int(access_status) != 1:
            print(f"Windows notification listener permission not granted. Status: {access_status}")
            return

        try:
            existing = await self._listener.get_notifications_async(NotificationKinds.TOAST)
            for notification in existing:
                notification_id = self._extract_notification_id(notification)
                if notification_id is not None:
                    self._remember_notification_id(notification_id)
        except Exception as e:
            print(f"Windows notification listener initial poll failed: {e}")
            return

        while not self._stop_event.is_set():
            try:
                notifications = await self._listener.get_notifications_async(NotificationKinds.TOAST)
            except Exception as e:
                print(f"Windows notification listener poll failed: {e}")
                await asyncio.sleep(self.poll_interval_seconds)
                continue

            for notification in notifications:
                notification_id = self._extract_notification_id(notification)

                if notification_id is None:
                    continue

                if notification_id in self._seen_notification_ids:
                    continue

                self._remember_notification_id(notification_id)
                app_name = self._extract_app_name(notification)
                title, body = self._extract_title_and_body(notification)
                print(f"[NOTIFY] App='{app_name}' Title='{title}'")

                if not should_process_notification(app_name):
                    print(f"[NOTIFY FILTERED] App='{app_name}'")
                    continue

                payload = self._normalize_payload(notification, notification_id)
                self._post_notification(payload)

            await asyncio.sleep(self.poll_interval_seconds)

    @staticmethod
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

    @staticmethod
    def _to_text(value):
        if value is None:
            return ""
        return str(value).strip()

    def _extract_notification_id(self, notification):
        value = self._safe_getattr(notification, ["id", "Id"], default=None)
        if value is None:
            return None
        return str(value)

    def _extract_timestamp(self, notification):
        created_time = self._safe_getattr(notification, ["created_time", "CreatedTime"], default=None)
        if created_time is None:
            return datetime.now().isoformat()

        try:
            if hasattr(created_time, "isoformat"):
                return created_time.isoformat()
        except Exception:
            pass

        text = self._to_text(created_time)
        if text:
            return text

        return datetime.now().isoformat()

    def _extract_app_name(self, notification):
        app_name = self._safe_getattr(notification, ["app_name", "AppName"], default=None)
        if app_name:
            return self._to_text(app_name)

        app_info = self._safe_getattr(notification, ["app_info", "AppInfo"], default=None)
        if app_info is not None:
            display_info = self._safe_getattr(app_info, ["display_info", "DisplayInfo"], default=None)
            if display_info is not None:
                display_name = self._safe_getattr(display_info, ["display_name", "DisplayName"], default=None)
                if display_name:
                    return self._to_text(display_name)

        app_id = self._safe_getattr(notification, ["app_id", "AppId"], default=None)
        if app_id:
            app_id_text = self._to_text(app_id)
            if "!" in app_id_text:
                return app_id_text.split("!")[0]
            return app_id_text

        return "Unknown"

    def _extract_text_elements(self, notification):
        notification_content = self._safe_getattr(notification, ["notification", "Notification"], default=None)
        if notification_content is None:
            return []

        visual = self._safe_getattr(notification_content, ["visual", "Visual"], default=None)
        if visual is None:
            return []

        bindings = self._safe_getattr(visual, ["bindings", "Bindings"], default=None)
        if not bindings:
            return []

        try:
            for binding in bindings:
                get_text_elements = self._safe_getattr(binding, ["get_text_elements", "GetTextElements"], default=None)

                if callable(get_text_elements):
                    elements = get_text_elements()
                else:
                    elements = self._safe_getattr(binding, ["text_elements", "TextElements"], default=[])

                if not elements:
                    continue

                values = []
                for element in elements:
                    text = self._safe_getattr(element, ["text", "Text"], default="")
                    text = self._to_text(text)
                    if text:
                        values.append(text)

                if values:
                    return values
        except Exception:
            return []

        return []

    def _extract_title_and_body(self, notification):
        title = self._to_text(self._safe_getattr(notification, ["summary_text", "SummaryText"], default=""))
        body = self._to_text(
            self._safe_getattr(notification, ["body_text", "BodyText", "message_text", "MessageText"], default="")
        )

        if title and body:
            return title, body

        text_elements = self._extract_text_elements(notification)
        if not title and len(text_elements) >= 1:
            title = text_elements[0]
        if not body and len(text_elements) >= 2:
            body = text_elements[1]

        return title, body

    @staticmethod
    def _source_from_app_name(app_name):
        app_lower = app_name.lower()

        if "discord" in app_lower:
            return "discord"
        if "telegram" in app_lower:
            return "telegram"
        if any(token in app_lower for token in ["outlook", "mail", "gmail", "email"]):
            return "email"

        return "system"

    def _normalize_payload(self, notification, notification_id):
        timestamp = self._extract_timestamp(notification)
        app_name = self._extract_app_name(notification)
        title, body = self._extract_title_and_body(notification)
        source = self._source_from_app_name(app_name)

        sender = title
        summary = body or title

        return {
            "source": source,
            "sender": sender,
            "summary": summary,
            "timestamp": timestamp,
            "app_name": app_name,
            "title": title,
            "body": body,
            "notification_id": notification_id,
        }

    def _remember_notification_id(self, notification_id):
        self._seen_notification_ids.add(notification_id)
        self._seen_notification_order.append(notification_id)

        if len(self._seen_notification_ids) <= MAX_TRACKED_NOTIFICATION_IDS:
            return

        removed = 0
        while removed < TRIM_COUNT_ON_OVERFLOW and self._seen_notification_order:
            oldest_id = self._seen_notification_order.popleft()
            if oldest_id in self._seen_notification_ids:
                self._seen_notification_ids.remove(oldest_id)
                removed += 1

    def _post_notification(self, payload):
        try:
            response = requests.post(
                self.notify_endpoint_url,
                json=payload,
                timeout=POST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            status_code = "unknown"
            if e.response is not None:
                status_code = e.response.status_code
            print(f"Windows notification listener POST HTTP error ({status_code}): {e}")
        except Exception as e:
            print(f"Windows notification listener POST failed: {e}")


_listener_thread = None
_listener_lock = threading.Lock()


def start_windows_notification_listener(notify_endpoint_url=NOTIFY_ENDPOINT_URL, poll_interval_seconds=POLL_INTERVAL_SECONDS):
    global _listener_thread

    with _listener_lock:
        if _listener_thread is not None and _listener_thread.is_alive():
            return _listener_thread

        _listener_thread = WindowsNotificationListenerThread(
            notify_endpoint_url=notify_endpoint_url,
            poll_interval_seconds=poll_interval_seconds,
        )
        _listener_thread.start()
        return _listener_thread


def stop_windows_notification_listener(timeout_seconds=3):
    global _listener_thread

    with _listener_lock:
        thread = _listener_thread

    if thread is None:
        return

    thread.stop()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        print(
            "Windows notification listener stop timeout elapsed; "
            "listener thread is still running."
        )
        return

    with _listener_lock:
        if _listener_thread is thread:
            _listener_thread = None