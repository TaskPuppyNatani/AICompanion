import requests
from config import NOTIFY_ENDPOINT_URL

requests.post(
    NOTIFY_ENDPOINT_URL,
    json={
        "message": "HEY PUP CHECK YO DAMN MESSAGES GIRLY"
    }
)

print("Notification sent!")