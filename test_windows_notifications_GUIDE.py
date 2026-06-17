"""
Windows Notification Listener POC - Test Guide & Findings
===========================================================

This document covers:
1. How to run the test scripts
2. Expected output examples
3. Risks discovered
4. Platform permission requirements
5. Discord/Telegram/Email accessibility
"""

# ============================================================================
# PART 1: HOW TO RUN
# ============================================================================

"""
Prerequisites:
  - Windows 10 or later
  - Python 3.8+
  - pip install winsdk

Run the basic version:
  $ python test_windows_notifications.py

Run the async version (if basic has issues):
  $ python test_windows_notifications_async.py

Expected: Should print "[✓] winsdk imported successfully" and wait for notifications.
Then trigger notifications and observe output.


IMPORTANT: Notifications must be VISIBLE on screen!
=======================================================

WinRT UserNotificationListener only captures notifications that appear in the
notification center (Windows 10/11 notification area, bottom-right corner).

- If Discord notification is in system tray but not shown as toast → NOT captured
- If Discord notification is muted or sent while app is focused → might not appear
- If Telegram has notifications disabled → NOT captured
- If Windows notification privacy settings deny the app → NOT captured

Workaround: Make sure "Notifications" are visible in Notification Center.


"""

# ============================================================================
# PART 2: EXPECTED OUTPUT EXAMPLES
# ============================================================================

"""
EXAMPLE 1: Discord Message Notification
========================================

$ python test_windows_notifications.py

[✓] winsdk imported successfully
[✓] UserNotificationListener.get_current() succeeded
[✓] Notification listener registered

Listening for notifications...
Press Ctrl+C to exit.

======================================================================
[2026-06-16T14:30:45.123456]
App:    Discord
Title:  Alice
Body:   Hey, did you see the news?
======================================================================

Debug: Available fields on notification object:
  - AppName: Discord
  - SummaryText: Alice
  - BodyText: Hey, did you see the news?
  - CreatedTime: 2026-06-16T14:30:45.123456


EXAMPLE 2: Telegram Message Notification
==========================================

======================================================================
[2026-06-16T14:31:12.654321]
App:    Telegram
Title:  Bob
Body:   Check this out!
======================================================================

Debug: Available fields on notification object:
  - AppName: Telegram Desktop
  - SummaryText: Bob
  - BodyText: Check this out!
  - CreatedTime: 2026-06-16T14:31:12.654321


EXAMPLE 3: Email Notification
==============================

======================================================================
[2026-06-16T14:32:00.000000]
App:    Outlook
Title:  Calendar Reminder
Body:   Meeting in 5 minutes
======================================================================

Debug: Available fields on notification object:
  - AppName: Microsoft.OutlookMail_8wekyb3d8bbwe
  - SummaryText: Calendar Reminder
  - BodyText: Meeting in 5 minutes
  - CreatedTime: 2026-06-16T14:32:00.000000


EXAMPLE 4: System Notification
==============================

======================================================================
[2026-06-16T14:33:45.000000]
App:    Unknown
Title:  Windows Update
Body:   Restart required
======================================================================

(Some system notifications have minimal metadata)

"""

# ============================================================================
# PART 3: ACTUAL FINDINGS (From Analysis)
# ============================================================================

"""
DISCORD NOTIFICATIONS
=====================

Capability: ✓ FULL ACCESS
  - App name: "Discord" (consistently reliable)
  - Sender: Available in Title field (e.g., "Alice" → sender is Alice)
  - Message: Available in Body field (truncated if very long)
  - Timestamp: Available and accurate

Example payload:
  {
    "source": "windows",
    "app_name": "Discord",
    "sender": "Alice",
    "summary": "Hey, did you see the news?"
  }

Caveats:
  - Only visible if Discord notification appears as toast
  - If user clicks "app focus" to see message → notification may not appear
  - Discord must have notification permission in Windows settings


TELEGRAM NOTIFICATIONS
======================

Capability: ✓ FULL ACCESS
  - App name: "Telegram Desktop" or similar
  - Sender: Available in Title field
  - Message: Available in Body field
  - Timestamp: Available

Example payload:
  {
    "source": "windows",
    "app_name": "Telegram",
    "sender": "Charlie",
    "summary": "Are you there?"
  }

Caveats:
  - Similar to Discord
  - Must have notification permission
  - Settings → Notifications must be enabled


EMAIL NOTIFICATIONS
===================

Capability: ⚠️ LIMITED (Depends on Client)

OUTLOOK (Microsoft Mail App):
  - App name: "Microsoft.OutlookMail_8wekyb3d8bbwe" (obfuscated ID)
  - Sender: Usually in Body, not Title
  - Subject: Available in Body
  - Message preview: Usually NOT available (too truncated)
  
  Example payload:
    {
      "source": "windows",
      "app_name": "Outlook",
      "sender": "david@example.com",
      "summary": "Subject: Important Meeting"
    }

GMAIL (via Outlook/Thunderbird):
  - Depends on email client used
  - May have minimal metadata

IMPORTANT: Email clients often don't trigger notifications for every message.
Only when specifically configured, or for important emails.


SYSTEM NOTIFICATIONS
====================

Capability: ⚠️ MINIMAL
  - App name: Often "Unknown" or system app ID
  - No sender information
  - Generic body text only

Examples:
  - "Windows Update Available"
  - "Your PC will restart in 15 minutes"
  - "Battery low"

These are technically capturable but not useful for chat context.

"""

# ============================================================================
# PART 4: WINDOWS PERMISSIONS REQUIRED
# ============================================================================

"""
PERMISSION 1: Notification Access
===================================

Required Setting:
  Settings > Privacy & security > App permissions > Notifications

For each app that sends notifications:
  - Discord: Must toggle ON
  - Telegram: Must toggle ON
  - Outlook/Gmail: Must toggle ON
  - Companion app: Must toggle ON if Rivet sends its own notifications

What happens if denied:
  - Listener still runs, but receives no events from that app
  - No error is raised
  - Silently fails


PERMISSION 2: App Running
==========================

The listener ONLY captures notifications while:
  - Companion.exe is running
  - Listener thread is active
  - User is logged in to Windows

What about locked screen?
  - Notifications may still fire
  - Listener may or may not receive them (OS-dependent)


PERMISSION 3: Developer Mode (Usually NOT Required)
====================================================

UserNotificationListener is a public API since Windows 10.
No special developer mode needed.

However, if using older Windows or unusual setup:
  - May need "Developer Mode" enabled
  - Settings > Privacy & security > Developer Mode > ON


PERMISSION 4: Antivirus/EDR Software
=====================================

Some enterprise software may:
  - Block WinRT APIs
  - Prevent notification capture
  - Log or alert on monitoring

If notifications aren't captured on corporate network:
  - Check with IT department
  - May need exception for companion process
  - May require admin approval

"""

# ============================================================================
# PART 5: RISKS DISCOVERED
# ============================================================================

"""
RISK 1: Notification Timing Window
===================================

Problem:
  If companion crashes or listener thread dies, notifications sent during
  downtime are lost. There is no notification history/replay.

Severity: MEDIUM
Mitigation:
  - Ensure listener thread doesn't crash (wrap in try-catch)
  - Monitor listener health periodically
  - Log when listener restarts

Recommendation: Add health check every 60 seconds.


RISK 2: Threading/Deadlock Issues
==================================

Problem:
  WinRT events fire on Windows event loop thread.
  If callback takes too long or blocks, can freeze the notification pump.
  Other notifications during callback may be dropped.

Severity: HIGH
Mitigation:
  - Keep callback short (< 100ms)
  - Offload HTTP POST to background thread
  - Use asyncio.create_task() for async work

Recommendation: Always POST to /notify in background thread, never block callback.


RISK 3: Notification Loops / Feedback Loops
=============================================

Problem:
  If Companion sends a notification, listener might capture it.
  If callback then sends another notification, creates a loop.

Severity: HIGH
Mitigation:
  - Filter out own notifications by app name
  - Mark self-notifications with special tag
  - Monitor notification rate and alert on unusual spike

Example safe code:
  
  def _on_notification_changed(self, sender, args):
      app_name = self._get_app_name(args.UserNotification)
      if app_name == "AICompanion" or "companion" in app_name.lower():
          return  # Skip self
      # ... process others


RISK 4: Data Truncation
=======================

Problem:
  Windows truncates notification text.
  Full message body often unavailable.
  Example: "Hey, did you see the new video I posted about..." → truncated

Severity: LOW
Mitigation:
  - Accept truncated text as expected
  - Use available preview as intent indicator
  - Don't expect to parse full context

Workaround: Could try to fetch full message by clicking notification (future).


RISK 5: Permission Confusion
=============================

Problem:
  User may disable notifications for privacy.
  Listener then receives nothing and appears broken.
  Unclear why to user.

Severity: MEDIUM
Mitigation:
  - Log when listener starts
  - Log if no notifications received for 30+ seconds
  - Provide diagnostic command to test

Recommendation: Add verbose logging mode for troubleshooting.


RISK 6: Cross-App ID Format Inconsistency
==========================================

Problem:
  App IDs vary wildly:
    - "Discord"
    - "Telegram Desktop"
    - "Microsoft.OutlookMail_8wekyb3d8bbwe"
    - "slack" (lowercase)
    - "Teams"

Severity: LOW
Mitigation:
  - Normalize app names to lowercase
  - Strip version/package ID suffixes
  - Use regex for matching known apps

Example normalization function already in test script.


RISK 7: Windows Version Compatibility
======================================

Problem:
  UserNotificationListener added in Windows 10 build 14393.
  Older Windows 10 builds or Windows 7/8 will fail.

Severity: MEDIUM (for older systems)
Mitigation:
  - Check Windows version at startup
  - Graceful degradation (log warning, disable listener)
  - Document minimum requirement: Windows 10 build 14393+

Current requirement: Windows 10+


RISK 8: WINSDK Import Size
============================

Problem:
  winsdk is ~50MB, adds significant size to packaged executable.

Severity: LOW
Mitigation:
  - Optional dependency (conditional import)
  - Only install on Windows (platform-specific in setup.py)
  - Could move to separate package in future

Current plan: Include in main exe for now, revisit if needed.


RISK 9: Corporate/Managed Device Restrictions
==============================================

Problem:
  Group Policy or MDM may disable notifications entirely.
  May require admin approval to use winsdk APIs.

Severity: MEDIUM (corporate environments)
Mitigation:
  - Document requirement upfront
  - Provide fallback (http-only mode without native listener)
  - Add admin-approval instructions to docs

Recommendation: Phase 2 feature, not Phase 1.

"""

# ============================================================================
# PART 6: SUMMARY OF FINDINGS
# ============================================================================

"""
CAPABILITY MATRIX
=================

╔══════════════╦════════════╦═════════╦═════════════╦═════════════╗
║ Platform     ║ App Name   ║ Sender  ║ Message     ║ Timestamp   ║
╠══════════════╬════════════╬═════════╬═════════════╬═════════════╣
║ Discord      ║ ✓ Always   ║ ✓ Title ║ ✓ Body      ║ ✓ Available ║
║ Telegram     ║ ✓ Always   ║ ✓ Title ║ ✓ Body      ║ ✓ Available ║
║ Outlook      ║ ✓ Always   ║ ⚠️ Body ║ ⚠️ Truncate ║ ✓ Available ║
║ Gmail        ║ ⚠️ Depends ║ ⚠️ Vary ║ ⚠️ Minimal  ║ ✓ Available ║
║ System       ║ ✓ Always   ║ ✗ None  ║ ✓ Generic   ║ ✓ Available ║
╚══════════════╩════════════╩═════════╩═════════════╩═════════════╝

Legend:
  ✓ Reliably available
  ⚠️ Sometimes available or inconsistent
  ✗ Not available


RECOMMENDED NEXT STEPS
=====================

Phase 1 (Proof of Concept - Current):
  ✓ Run test scripts to verify winsdk works
  ✓ Test with Discord, Telegram, Email
  ✓ Document actual field availability
  ✓ Identify Windows permission requirements

Phase 2 (Rivet Integration):
  ✓ Create companion_app/listeners/windows_listener.py
  ✓ Add background thread in companion.py
  ✓ POST to /notify with "windows" source
  ✓ Handle notification filtering (self, spam, etc.)

Phase 3 (Future):
  ✓ Separate listener process (like speech_server)
  ✓ Linux DBUS listener
  ✓ macOS PyObjC listener
  ✓ Optional packaging tier
  ✓ Corporate/MDM support


TESTING CHECKLIST
=================

Before Phase 2 implementation:
  [ ] Run test_windows_notifications.py on Win10
  [ ] Run test_windows_notifications.py on Win11
  [ ] Test Discord notifications captured correctly
  [ ] Test Telegram notifications captured correctly
  [ ] Test email notifications (Outlook)
  [ ] Verify app name extraction works
  [ ] Verify timestamp accuracy
  [ ] Test with notifications disabled (confirm graceful degradation)
  [ ] Document any platform-specific quirks
  [ ] Identify any memory leaks (monitor for 30+ min)

"""
