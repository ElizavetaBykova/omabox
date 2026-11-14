"""Read sample IDs from QR codes and append detection events to JSONL."""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2


BOX_ID = "BOX-01"
KIT_ID_PATTERN = re.compile(r"^(?P<kit_type>[A-Z][A-Z0-9]*)-(?P<sample_number>\d+)$")


def parse_args() -> argparse.Namespace:
    """Parse scanner settings supplied at launch."""
    parser = argparse.ArgumentParser(description="Scan sample QR codes using a webcam.")
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index to open (default: 0).",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=320,
        help="Requested camera frame width (default: 320).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=240,
        help="Requested camera frame height (default: 240).",
    )
    parser.add_argument(
        "--scan-every-frames",
        type=int,
        default=5,
        help="Run QR detection every Nth captured frame (default: 5).",
    )
    parser.add_argument(
        "--scan-interval-ms",
        type=int,
        default=300,
        help="Minimum delay between QR scans in milliseconds (default: 300).",
    )
    parser.add_argument(
        "--events-file",
        type=Path,
        default=Path(__file__).with_name("events.jsonl"),
        help="JSONL event output path (default: python/events.jsonl).",
    )
    return parser.parse_args()


def parse_kit_id(qr_text: str) -> tuple[str, str] | None:
    """Return (kit_id, kit_type) for IDs such as HPV-0001."""
    match = KIT_ID_PATTERN.fullmatch(qr_text.strip())
    if match is None:
        return None

    return qr_text.strip(), match.group("kit_type")


def make_event(kit_id: str, kit_type: str) -> dict[str, str | None]:
    """Build the JSON event using the laptop's current local timezone."""
    return {
        "box_id": BOX_ID,
        "event": "kit_dropped",
        "kit_id": kit_id,
        "kit_type": kit_type,
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "temp_c": None,
    }


def append_event(events_file: Path, event: dict[str, str | None]) -> None:
    """Append one event as a JSON object on its own line."""
    events_file.parent.mkdir(parents=True, exist_ok=True)
    with events_file.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(event) + "\n")


def load_registered_kit_ids(events_file: Path) -> set[str]:
    """Load IDs already present in the event file to prevent duplicate events."""
    registered_ids: set[str] = set()
    if not events_file.exists():
        return registered_ids

    with events_file.open("r", encoding="utf-8") as event_log:
        for line_number, line in enumerate(event_log, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {events_file} on line {line_number}: {error}"
                ) from error

            if isinstance(event, dict) and event.get("event") == "kit_dropped":
                kit_id = event.get("kit_id")
                if isinstance(kit_id, str):
                    registered_ids.add(kit_id)

    return registered_ids


def run_scanner(
    camera_index: int,
    events_file: Path,
    width: int,
    height: int,
    scan_every_frames: int,
    scan_interval_ms: int,
) -> int:
    """Read frames one at a time and scan only on the configured schedule."""
    try:
        registered_kit_ids = load_registered_kit_ids(events_file)
    except (OSError, ValueError) as error:
        print(f"Error: could not read event log: {error}", file=sys.stderr)
        return 1

    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        print(
            f"Error: could not open camera index {camera_index}. "
            "Check the camera connection and --camera-index.",
            file=sys.stderr,
        )
        capture.release()
        return 1

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if not capture.set(cv2.CAP_PROP_BUFFERSIZE, 1):
        print(
            "Warning: camera backend did not accept a one-frame buffer limit; "
            "the scanner will still process frames one at a time.",
            file=sys.stderr,
        )

    detector = cv2.QRCodeDetector()
    frame_number = 0
    last_scan_at = float("-inf")
    scan_interval_seconds = scan_interval_ms / 1000.0

    print(
        f"Scanner running at {width}x{height}; QR scans are limited to every "
        f"{scan_every_frames} frames and at least {scan_interval_ms} ms apart. "
        "Press Ctrl+C to stop."
    )
    try:
        while True:
            frame_read, frame = capture.read()
            if not frame_read:
                print("Error: failed to read a frame from the camera.", file=sys.stderr)
                return 1

            frame_number += 1
            now = time.monotonic()
            scan_due = (
                frame_number % scan_every_frames == 0
                and now - last_scan_at >= scan_interval_seconds
            )
            if scan_due:
                last_scan_at = now
                # Resize only frames being scanned if the camera ignored the
                # requested dimensions.
                if frame.shape[1] != width or frame.shape[0] != height:
                    scan_frame = cv2.resize(frame, (width, height))
                else:
                    scan_frame = frame

                qr_text, points, straight_qrcode = detector.detectAndDecode(scan_frame)

                parsed_kit = parse_kit_id(qr_text) if qr_text else None
                if parsed_kit is not None:
                    kit_id, kit_type = parsed_kit
                    if kit_id not in registered_kit_ids:
                        event = make_event(kit_id, kit_type)
                        try:
                            append_event(events_file, event)
                        except OSError as error:
                            print(f"Error: could not write event log: {error}", file=sys.stderr)
                            return 1
                        registered_kit_ids.add(kit_id)
                        print(json.dumps(event))
                del qr_text, points, straight_qrcode, scan_frame

            # Release each captured image before reading another frame.
            del frame
    except KeyboardInterrupt:
        print("\nScanner stopped.")
        return 0
    finally:
        capture.release()


def main() -> int:
    """Validate settings and start the camera scanner."""
    args = parse_args()
    if args.camera_index < 0:
        print("Error: --camera-index must be zero or greater.", file=sys.stderr)
        return 2
    if args.width <= 0 or args.height <= 0:
        print("Error: --width and --height must be greater than zero.", file=sys.stderr)
        return 2
    if args.scan_every_frames < 1:
        print("Error: --scan-every-frames must be at least 1.", file=sys.stderr)
        return 2
    if args.scan_interval_ms < 0:
        print("Error: --scan-interval-ms cannot be negative.", file=sys.stderr)
        return 2

    return run_scanner(
        args.camera_index,
        args.events_file,
        args.width,
        args.height,
        args.scan_every_frames,
        args.scan_interval_ms,
    )


if __name__ == "__main__":
    raise SystemExit(main())