import requests
from config import NOTIFY_ENDPOINT_URL

requests.post(
    NOTIFY_ENDPOINT_URL,
    json={
        "message": "Test notification from Rivet."
    }
)

print("Notification sent!")
