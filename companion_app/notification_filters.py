ALLOWED_APPS = {
    "Discord",
    "Telegram",
}


def should_process_notification(app_name: str) -> bool:
    return app_name in ALLOWED_APPS