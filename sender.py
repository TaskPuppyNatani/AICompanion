import requests

requests.post(
    "http://127.0.0.1:5000/notify",
    json={
        "message": "HEY PUP CHECK YO DAMN MESSAGES GIRLY"
    }
)

print("Notification sent!")