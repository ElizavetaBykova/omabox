# OmaBox main.py for the UNO Q (App Lab) - TEST VERSION
#
# Put this file and omabox_logic.py in the app's python/ folder.
# Use a copy of the chatbot example so the LLM + WebUI bricks and its chat page exist.
#
# How to test:
#   1. Press Run and watch the App Lab console: a self-test runs the SELF_TEST scenarios once.
#   2. Open the web page: notifications appear on the left. In the chat, type a command
#      (drop HPV-0001 21h | temp 33 | collected | pickup | status) or a test scenario name.
#      The courier message appears as the chat answer.
#   3. Paste the console output (incl. "brick API" and "raw LLM output" lines) back to Claude.

import inspect
import itertools
import math
import os
import queue
import threading
import time
from datetime import datetime

from arduino.app_bricks.llm import LargeLanguageModel
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge

from camera import KitScanner
from omabox_logic import (CHAT_HELP, SCENARIOS, SYSTEM_PROMPT, BoxState, event_from_qr, handle_event,
                          notify, parse_command, scenario)

ui = WebUI()

# Brick options (from the "brick API" line): max_tokens and temperature go in the constructor.
LLM_OPTIONS = {"max_tokens": 80, "temperature": 0.2}
# Try to switch Qwen thinking off in llama.cpp itself (it may think silently even if we never see <think>).
# Passed through the brick's **kwargs; if the brick or server rejects it we fall back without it.
NO_THINK_OPTIONS = {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}

llm = None
llm_config = ""


def make_llm(thinking_off):
    """Create the LLM brick. No memory: each message stands alone (we clear it before every call)."""
    global llm, llm_config
    opts = {**LLM_OPTIONS, **(NO_THINK_OPTIONS if thinking_off else {})}
    try:
        llm = LargeLanguageModel(system_prompt=SYSTEM_PROMPT, **opts)
    except TypeError as e:
        if not thinking_off:
            raise
        print(f"LLM: thinking-off option rejected at start ({e}); using defaults")
        return make_llm(False)
    llm_config = f"{LLM_OPTIONS} thinking_off={thinking_off}"
    print(f"LLM config: {llm_config}")
    return thinking_off


_thinking_off = make_llm(True)


def show_brick_api():
    """Print the LLM brick's signatures once, so we know which options it really takes."""
    for name in ("__init__", "chat_stream", "chat"):
        fn = getattr(LargeLanguageModel, name, None)
        try:
            print(f"brick API: LargeLanguageModel.{name}{inspect.signature(fn)}" if fn
                  else f"brick API: LargeLanguageModel.{name} not found")
        except (TypeError, ValueError):
            print(f"brick API: LargeLanguageModel.{name} (signature not available)")


last_timing = ""


def _stream(prompt):
    """Collect the streamed answer and time it: first chunk = reading the prompt (+ any hidden thinking),
    the rest = writing the answer. Chunks are roughly tokens."""
    global last_timing
    llm.clear_memory()
    start = time.time()
    first, chunks = None, []
    for c in llm.chat_stream(prompt):
        if first is None:
            first = time.time() - start
        chunks.append(str(c))
    total = time.time() - start
    first = total if first is None else first
    last_timing = (f"prompt {len(SYSTEM_PROMPT) + len(prompt)} chars | first chunk after {first:.1f}s | "
                   f"{len(chunks)} chunks in {total - first:.1f}s")
    return "".join(chunks)


def ask(prompt):
    global _thinking_off
    try:
        return _stream(prompt)
    except Exception as e:
        if not _thinking_off:
            raise
        print(f"LLM: call failed with thinking-off option ({type(e).__name__}: {e}); retrying without it")
        _thinking_off = make_llm(False)
        return _stream(prompt)


# Notifications shown on the web page. Newest last; the page gets the whole list when it (re)connects,
# so it also shows what happened before it was opened. Each card has an id: a card sent again with the
# same id REPLACES the old one (template first, LLM text a few seconds later).
notifications = []
MAX_NOTIFICATIONS = 50
llm_lock = threading.Lock()      # one LLM call at a time (self-test, LLM worker). Camera pauses while held.
state_lock = threading.Lock()    # the real box state (chat, camera, sensor threads)
card_ids = itertools.count(1)
latest_box_card = None           # id of the newest real-box card; older ones don't get an LLM rewrite
llm_jobs = queue.Queue()
SENSOR_ERROR_C = -99.0          # this or lower = sensor error (sketch sends -999)


cleared_up_to = 0                # cards with id <= this were cleared by a pickup; never show them again


def clear_cards(keep_from_id):
    """Pickup made: remove every card on the page (also late LLM rewrites of old cards)."""
    global cleared_up_to
    cleared_up_to = keep_from_id - 1
    notifications.clear()
    try:
        ui.send_message("notifications", [])
    except Exception as e:
        print(f"(web page not updated: {e})")


def publish(item):
    if isinstance(item.get("id"), int) and item["id"] <= cleared_up_to:
        return
    for i, old in enumerate(notifications):
        if old.get("id") == item.get("id"):
            notifications[i] = item
            break
    else:
        notifications.append(item)
        del notifications[:-MAX_NOTIFICATIONS]
    try:
        ui.send_message("notification", item)
    except Exception as e:      # page not connected yet: it will get the list on connect
        print(f"(web page not updated: {e})")


def read_temperature_c():
    """Live box temperature from the Thermo sensor via the MCU sketch (Dev 2), or None if unavailable.
    The sketch returns -999 when the sensor does not answer (older code used -99)."""
    try:
        value = Bridge.call("read_temperature_c", timeout=2)
    except Exception as error:
        print(f"(temperature sensor not available: {error})")
        return None
    if not isinstance(value, (int, float)):
        print(f"(temperature sensor returned an invalid value: {value!r})")
        return None
    temperature_c = float(value)
    if not math.isfinite(temperature_c) or temperature_c <= SENSOR_ERROR_C:
        print("(temperature sensor read failed; check the sensor and I2C wiring)")
        return None
    if not -40.0 <= temperature_c <= 125.0:
        print(f"(temperature sensor out of range: {temperature_c})")
        return None
    return round(temperature_c, 1)


# The real box. Its state is saved in data/ (git-ignored) so a restart keeps the kits inside.
BOX_ID, BOX_LOCATION = "BOX-12", "Kuopio library"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "box_state.json")
state = BoxState(BOX_ID, BOX_LOCATION, STATE_FILE)


def report(card_id, label, box, result, secs, timing=None, pending=False):
    """Print to the console and publish (or replace) a card on the web page."""
    if timing:
        print(f"[{label}] LLM timing: {timing}")
    if result["raw"]:
        print(f"[{label}] raw LLM output: {result['raw']!r}")
    if result["rejected"]:
        print(f"[{label}] LLM text rejected: {result['rejected']}")
    print(f"[{label}] level={result['level']} light={result['light']} pickup={result['pickup']} "
          f"source={result['source']}{' (LLM writing...)' if pending else ''} ({secs}s)\n{result['message']}")
    publish({"id": card_id, "time": datetime.now().strftime("%H:%M:%S"), "scenario": label,
             "box_id": box["box_id"], "location": box["location"], "temp_c": box["temp_c"],
             "kits": len(result["kits"]), "level": result["level"], "light": result["light"],
             "pickup": result["pickup"], "source": result["source"], "secs": secs, "pending": pending,
             "message": result["message"], "rejected": result["rejected"]})


def run(name):
    """Test scenario (fake box) -> notification. Waits for the LLM (used by the self-test and chat)."""
    box = scenario(name)
    with llm_lock:
        start = time.time()
        result = notify(box, ask)
        secs, timing = round(time.time() - start, 1), last_timing
    report(next(card_ids), f"test: {name}", box, result, secs, timing)
    return result


def on_event(event, quiet=False):
    """Any event for the REAL box: chat command, camera (kit_dropped), sensor (temp_reading).
    Fast: decides and shows the template message at once; the LLM rewrite runs in llm_worker.
    Returns (info, template-result-or-None)."""
    global latest_box_card
    with state_lock:
        info, result = handle_event(state, event, None)     # ask=None -> template only, no LLM here
        box = state.as_box()
        if result:
            card_id = latest_box_card = next(card_ids)
    if result or not quiet:                                 # periodic checks: only log when something changed
        print(f"[event] {event.get('event')}: {info}")
    if result and event.get("event") == "box_emptied":
        clear_cards(card_id)                                # page starts fresh: only the "0 kits" card
    if result:
        label = f"event: {info}"
        report(card_id, label, box, result, 0, pending=True)
        llm_jobs.put((card_id, label, box, result))
    return info, result


def llm_worker():
    """Rewrites real-box cards with the LLM, one at a time. Only the newest card is worth it:
    if more events came in meanwhile, older cards keep their (correct) template text."""
    while True:
        card_id, label, box, template = llm_jobs.get()
        if card_id != latest_box_card:
            report(card_id, label, box, {**template, "rejected": "skipped, a newer message exists"}, 0)
            continue
        try:
            with llm_lock:
                start = time.time()
                result = notify(box, ask)
                secs, timing = round(time.time() - start, 1), last_timing
            report(card_id, label, box, result, secs, timing)
        except Exception as e:
            print(f"[{label}] LLM worker ERROR: {e}")
            report(card_id, label, box, {**template, "rejected": f"LLM error: {e}"}, 0)


# Chat page: a command for the real box, or a test scenario name.
def on_prompt(_, data):
    text_in = (data.get("prompt", "") or "").strip()
    try:
        event = parse_command(text_in)
        if event:
            info, result = on_event(event)
            text = (f"{info}\n\n{result['message']}\n\n(the LLM version will replace the card in a few seconds)"
                    if result else f"{info} (no new message needed)")
        elif text_in.lower() in SCENARIOS:
            text = run(text_in.lower())["message"]
        else:
            text = CHAT_HELP + ": " + ", ".join(SCENARIOS)
    except Exception as e:
        text = f"Error: {e}"
    ui.send_message("response", text)
    ui.send_message("stream_end", {})


def on_get_notifications(_, data):
    ui.send_message("notifications", notifications)


def on_command(_, data):
    # The page's "Reset chat" / stop buttons: nothing to stop on our side, just confirm.
    ui.send_message("command_ok", {"command": (data or {}).get("command", "")})


ui.on_message("prompt", on_prompt)
ui.on_message("get_notifications", on_get_notifications)
ui.on_message("commands", on_command)

# ~10 s per LLM call. Set RUN_SELF_TEST = False for the demo, so the page starts with the real box only
# (the camera is paused while the self-test uses the LLM).
RUN_SELF_TEST = False
SELF_TEST = ("normal", "soon", "hpv_3h_left", "overdue", "empty", "unknown")   # one of each level


def self_test():
    on_event({"event": "status"})          # the real box first (kits restored from data/ after a restart)
    if not RUN_SELF_TEST:
        return
    print("=== OmaBox self-test ===")
    for n in SELF_TEST:
        try:
            run(n)
        except Exception as e:
            print(f"[{n}] ERROR: {e}")
    print("=== self-test done, now try the chat page or show a kit QR code to the camera ===")


SENSOR_PERIOD_S = 30


def sensor_loop():
    """Every 30 s: live temperature + deadline check for the REAL box (hours left are recomputed on
    every event). Without a sensor value it still sends a 'tick', so deadlines are checked anyway.
    handle_event only notifies when the level (ok/soon/urgent/overdue) or too-warm/cold state changes."""
    while True:
        t = read_temperature_c()
        try:
            on_event({"event": "temp_reading", "temp_c": t} if t is not None else {"event": "tick"},
                     quiet=True)
        except Exception as e:
            print(f"[sensor] ERROR: {e}")
        time.sleep(SENSOR_PERIOD_S)


CAMERA_ENABLED = True
SCAN_PERIOD_S = 0.5              # about 2 looks per second is plenty for a hand dropping a kit
SAME_CODE_GAP_S = 10             # a code must be out of sight this long before it counts again


def camera_loop():
    """Camera -> kit_dropped events. Paused (camera released) while the LLM runs, to save RAM and CPU."""
    scanner = KitScanner()
    last_seen = {}                   # kit code -> last time the camera saw it
    paused = False
    while True:
        try:
            if llm_lock.locked():
                if not paused:
                    print("camera: paused while the LLM runs")
                    scanner.release()
                    paused = True
                time.sleep(SCAN_PERIOD_S)
                continue
            if paused:
                print("camera: resumed")
                paused = False
            code = scanner.scan_kit()
            now = time.monotonic()
            if code:
                fresh = now - last_seen.get(code, -SAME_CODE_GAP_S) >= SAME_CODE_GAP_S
                last_seen[code] = now    # still in view -> keeps it from firing again
                if fresh:
                    print(f"camera: saw {code}")
                    event = event_from_qr(code, datetime.now().isoformat(timespec="seconds"), BOX_ID)
                    if event:                # kit -> kit_dropped, courier code -> box_emptied
                        on_event(event)
        except Exception as e:           # never let the camera thread die
            print(f"camera: ERROR {e}")
            scanner.release()
            time.sleep(2)
        time.sleep(SCAN_PERIOD_S)


def show_i2c_scan():
    """Debug: which I2C devices the MCU sees (Modulino Thermo = 0x44)."""
    try:
        print("I2C scan:", Bridge.call("i2c_scan", timeout=5))
    except Exception as e:
        print(f"(I2C scan not available: {e})")


# Background threads, so the web page is available right away and shows notifications as they come in.
show_brick_api()
show_i2c_scan()
threading.Thread(target=llm_worker, daemon=True).start()
threading.Thread(target=self_test, daemon=True).start()
threading.Thread(target=sensor_loop, daemon=True).start()
if CAMERA_ENABLED:
    threading.Thread(target=camera_loop, daemon=True).start()

App.run()
