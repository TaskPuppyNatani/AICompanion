"""Check winsdk documentation and implementation details"""
import sys
import os
from winsdk.windows.ui.notifications.management import UserNotificationListener

# Check package location
import winsdk
print(f"winsdk package location: {winsdk.__file__}\n")

# Try to get the module file
management_module = sys.modules.get('winsdk.windows.ui.notifications.management')
if management_module:
    print(f"management module: {management_module.__file__}\n")

# Check if there's a .pyi stub we can read
venv_path = "E:\\AICompanion\\.venv\\Lib\\site-packages\\winsdk"
pyi_file = os.path.join(
    venv_path,
    "windows", "ui", "notifications", "management", "__init__.pyi"
)

print(f"Looking for type stub: {pyi_file}")
if os.path.exists(pyi_file):
    print(f"✓ Found type stub\n")
    with open(pyi_file, 'r') as f:
        content = f.read()
    
    # Find add_notification_changed signature
    for line in content.split('\n'):
        if 'add_notification_changed' in line or 'TypedEventHandler' in line:
            print(line)
else:
    print(f"✗ Type stub not found")

# Check UserNotificationListener class source/module
print(f"\n\nUserNotificationListener class info:")
print(f"  Module: {UserNotificationListener.__module__}")
print(f"  Name: {UserNotificationListener.__name__}")

# Check base classes
print(f"\n  Base classes: {UserNotificationListener.__bases__}")

# Check if there are any special methods
print(f"\n  All members:")
for attr in sorted(dir(UserNotificationListener)):
    if not attr.startswith('_'):
        print(f"    - {attr}")
