#When Discord integration is completed:
#1. Verify sender is always present.
#2. Search logs for generic Discord fallback usage.
#3. Remove DISCORD_RESPONSES if never used.
Future

☐ Auto-discover GGUF models

☐ Offer to create profile

☐ Auto-detect provider

☐ Drag-and-drop model import


Purpose:
Start llama-server manually to simulate an externally managed provider.
Used to verify Rivet's ownership policy. When this server is already
running, Rivet should detect the conflict, refuse to adopt the process,
and display the managed ownership error.

D:\AICompanion\llama\llama-server.exe ^
  -m "D:\AICompanion\models\vision\qwen-vision.gguf" ^
  --mmproj "D:\AICompanion\models\vision\qwen-vision-mmproj.gguf" ^
  --host 127.0.0.1 ^
  --port 8080