"""Headless QR scanner for the board (Phase 3). No window, never blocks for long.

    scanner = KitScanner()
    code = scanner.scan_kit()      # "HPV-0001", or None (no code / no camera yet)
    scanner.release()              # frees the camera (main.py does this while the LLM runs)

Uses the cv2 that ships with the board (do NOT add opencv-python to requirements.txt).
Based on Dev 2's qr_scanner.py (same detector and frame size idea), minus the window and the JSONL file:
main.py turns each new code into a kit_dropped event.

Test on the board over SSH (stop the app in App Lab first, only one program can use the camera):
    python3 camera.py              # prints every kit code it sees, Ctrl+C to stop
    python3 camera.py photo.jpg    # decode a saved image
"""

import glob
import os
import sys
import time

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")   # hide OpenCV's per-index warnings

from omabox_logic import qr_code_of_interest

WIDTH, HEIGHT = 640, 480       # QR codes on kits are small; 320x240 missed them at arm's length
MAX_CAMERA_INDEX = 9           # the UNO Q also has non-camera video nodes; try until one gives a frame
REOPEN_AFTER_S = 5             # after a failure, wait this long before trying the camera again


def decode(cv2, detector, frame):
    """Frame -> kit code like 'HPV-0001', or None. Also courier codes ('COURIER-0001/BOX-12'); ignores other QR codes."""
    text, _, _ = detector.detectAndDecode(frame)
    return qr_code_of_interest(text) if text else None


class KitScanner:
    def __init__(self, index=None):
        self.index = index         # None = find the first camera that gives a frame
        self.cap = None
        self.cv2 = None
        self.detector = None
        self.next_try = 0.0
        self.warned = False

    def _open(self):
        if time.monotonic() < self.next_try:
            return False
        self.next_try = time.monotonic() + REOPEN_AFTER_S
        try:
            if self.cv2 is None:
                import cv2         # imported here so a missing cv2 only disables the camera
                self.cv2, self.detector = cv2, cv2.QRCodeDetector()
        except Exception as e:
            self._warn(f"camera disabled: cannot import cv2 ({e})")
            return False
        cv2 = self.cv2
        if self.index is not None:
            indexes = [self.index]
        else:                      # only devices that exist (no camera plugged in = nothing to try)
            indexes = sorted(int(p[len("/dev/video"):]) for p in glob.glob("/dev/video*")
                             if p[len("/dev/video"):].isdigit())
            indexes = [i for i in indexes if i <= MAX_CAMERA_INDEX] or []
        if not indexes:
            self._warn("camera: no /dev/video* devices; plug the USB camera into the UNO Q (powered USB-C hub)")
            return False
        for i in indexes:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, _ = cap.read()
                if ok:
                    self.cap, self.index = cap, i
                    print(f"camera: using /dev/video{i}")
                    self.warned = False
                    return True
            cap.release()
        self._warn("camera: no working camera found (is it plugged in? is another program using it?)")
        return False

    def _warn(self, text):
        if not self.warned:        # print once, not every half second
            print(text)
            self.warned = True

    def scan_kit(self):
        """One quick look. Returns a kit code or None."""
        if self.cap is None and not self._open():
            return None
        self.cap.grab()            # drop a possibly old buffered frame, so we see the box *now*
        ok, frame = self.cap.read()
        if not ok:
            print("camera: frame read failed, will reopen")
            self.release()
            return None
        try:
            return decode(self.cv2, self.detector, frame)
        except Exception as e:     # OpenCV can throw on odd frames; never kill the loop
            print(f"camera: decode error ({e})")
            return None

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None


if __name__ == "__main__":
    if len(sys.argv) > 1:                       # decode image files
        import cv2
        det = cv2.QRCodeDetector()
        for path in sys.argv[1:]:
            img = cv2.imread(path)
            print(path, "->", None if img is None else decode(cv2, det, img))
        sys.exit(0)
    scanner = KitScanner()
    print("Scanning, Ctrl+C to stop")
    try:
        while True:
            code = scanner.scan_kit()
            if code:
                print(time.strftime("%H:%M:%S"), code)
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        scanner.release()
