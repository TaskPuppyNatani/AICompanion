# Known Issues

## Windows notification listener known limitation

### Confirmed behavior

* Discord notifications are successfully detected through Windows toast polling.
* Snip & Sketch notifications are detected and can be filtered.
* Rivet can react to Telegram-shaped notifications sent directly to the `/notify` endpoint, so Rivet-side notification handling for Telegram payloads is functional.

### Current limitation

* Telegram Desktop visually displays Windows toast notifications, but those notifications were **not observed** by Rivet’s current WinSDK `UserNotificationListener` polling implementation during testing.

### Open question

* It is currently unresolved whether Telegram Desktop notifications are inaccessible through the WinSDK notification history API used by Rivet, or whether a different retrieval approach is required.

### Current takeaway

* Rivet’s Windows notification listener should currently be considered **confirmed for Discord**, **working for some Windows notifications**, and **not yet confirmed for Telegram Desktop**.
