# HPV Sample QR Scanner

This Windows Python application reads sample QR codes from a USB camera using OpenCV. It records sample events in `events.jsonl`.

## Install

From the repository root in PowerShell:

```powershell
py -m pip install -r python\requirements.txt
```

## Run

```powershell
py python\qr_scanner.py --camera-index 0
```

By default, the scanner requests a `320x240` camera resolution, checks every fifth captured frame, and waits at least `300` milliseconds between QR detection attempts. It runs in the background without opening a camera preview window. If the camera ignores the requested dimensions, only frames selected for QR scanning are resized to the configured resolution. The application reads and processes one frame at a time and does not create its own frame queue. Press `Ctrl+C` in PowerShell to stop the scanner.

The settings can be changed from the command line:

```powershell
py python\qr_scanner.py --camera-index 0 --width 320 --height 240 --scan-every-frames 5 --scan-interval-ms 300
```

Events are appended to `python\events.jsonl` by default. Run `py python\qr_scanner.py --help` to see all options.
