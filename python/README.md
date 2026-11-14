# HPV Sample QR Scanner

This Arduino App Lab application reads the box temperature from an SHT30-compatible I2C sensor connected to the UNO Q and includes the live reading in each LLM prompt. The separate `qr_scanner.py` script scans QR codes on a camera; it is not yet connected to the App Lab workflow.

## Temperature sensor

The Arduino sketch in `sketch/sketch.ino` reads an SHT30-compatible sensor over the UNO Q's default I2C bus at address `0x44` or `0x45`. It returns `-99` if no valid sensor response is received. The Python app reads the live value through the App Lab Bridge before each LLM request; it does not use the test scenario's temperature. The existing 30 °C HPV limit is evaluated by the application logic and passed to the LLM with the measured temperature.

Connect the sensor's I2C SDA/SCL, power, and ground pins to the corresponding UNO Q pins. Verify the sensor module's voltage requirements before powering it. The exact sensor pinout and address depend on the breakout board.

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
