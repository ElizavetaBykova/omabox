"""Read sample IDs from QR codes and append detection events to JSONL."""

import argparse
import json
import re
import sys
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
        "--events-file",
        type=Path,
        default=Path(__file__).with_name("events.jsonl"),
        help="JSONL event output path (default: camera/events.jsonl).",
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
        "event": "kit_detected",
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

            if isinstance(event, dict) and event.get("event") == "kit_detected":
                kit_id = event.get("kit_id")
                if isinstance(kit_id, str):
                    registered_ids.add(kit_id)

    return registered_ids


def run_scanner(camera_index: int, events_file: Path) -> int:
    """Read camera frames, display them, and log newly detected kit IDs."""
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
    detector = cv2.QRCodeDetector()
    detector = cv2.QRCodeDetector()

    print("Scanner running. Press q in the camera window to quit.")
    try:
        while True:
            frame_read, frame = capture.read()
            if not frame_read:
                print("Error: failed to read a frame from the camera.", file=sys.stderr)
                return 1

            # QRCodeDetector returns an empty string when no QR code is decoded.
            qr_text, points, _ = detector.detectAndDecode(frame)
            if points is not None:
                corners = points.astype(int).reshape((-1, 1, 2))
                cv2.polylines(frame, [corners], True, (0, 255, 0), 2)

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
                    status_text = f"NEW SAMPLE: {kit_id}"
                    status_color = (0, 255, 0)
                else:
                    status_text = f"ALREADY REGISTERED: {kit_id}"
                    status_color = (0, 165, 255)
            elif points is not None:
                status_text = "INVALID QR SAMPLE ID"
                status_color = (0, 165, 255)
            else:
                status_text = "Waiting for QR code..."
                status_color = (255, 255, 255)

            # Keep QR detection at full resolution, but show a half-size preview.
            cv2.putText(
                frame,
                status_text,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                status_color,
                2,
            )
            preview = cv2.resize(frame, None, fx=0.5, fy=0.5)
            cv2.imshow("HPV Sample QR Scanner", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                return 0
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main() -> int:
    """Validate settings and start the camera scanner."""
    args = parse_args()
    if args.camera_index < 0:
        print("Error: --camera-index must be zero or greater.", file=sys.stderr)
        return 2
    return run_scanner(args.camera_index, args.events_file)


if __name__ == "__main__":
    raise SystemExit(main())