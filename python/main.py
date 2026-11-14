# OmaBox main.py for the UNO Q (App Lab) - TEST VERSION
#
# Put this file and omabox_logic.py in the app's python/ folder.
# Use a copy of the chatbot example so the LLM + WebUI bricks and its chat page exist.
#
# How to test:
#   1. Press Run and watch the App Lab console: a self-test runs the SELF_TEST scenarios once.
#   2. Open the chat page and type any scenario name from omabox_logic.SCENARIOS (or 'list').
#      The courier message appears as the chat answer.
#   3. Paste the console output (incl. "brick API" and "raw LLM output" lines) back to Claude.

import inspect
import math
import threading
import time
from datetime import datetime

from arduino.app_bricks.llm import LargeLanguageModel
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge

from omabox_logic import SCENARIOS, SYSTEM_PROMPT, notify, scenario

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
# so it also shows what happened before it was opened.
notifications = []
MAX_NOTIFICATIONS = 50
llm_lock = threading.Lock()      # one LLM call at a time (self-test thread + chat page)
SENSOR_ERROR_C = -99.0


def publish(item):
    notifications.append(item)
    del notifications[:-MAX_NOTIFICATIONS]
    try:
        ui.send_message("notification", item)
    except Exception as e:      # page not connected yet: it will get the list on connect
        print(f"(web page not updated: {e})")


def read_temperature_c():
    """Read and validate the current temperature reported by the MCU sensor."""
    try:
        value = Bridge.call("read_temperature_c", timeout=2)
    except Exception as error:
        raise RuntimeError(f"Could not read the temperature sensor: {error}") from error

    if not isinstance(value, (int, float)):
        raise RuntimeError(f"Temperature sensor returned an invalid value: {value!r}")

    temperature_c = float(value)
    if not math.isfinite(temperature_c) or temperature_c == SENSOR_ERROR_C:
        raise RuntimeError("Temperature sensor read failed; check the sensor and I2C wiring.")
    if not -40.0 <= temperature_c <= 125.0:
        raise RuntimeError(f"Temperature sensor returned an out-of-range value: {temperature_c}")

    return round(temperature_c, 1)


def run(name):
    box = scenario(name)
    with llm_lock:
        # Replace test-scenario temperature with the live hardware reading.
        box["temp_c"] = read_temperature_c()
        print(f"[{name}] live temperature: {box['temp_c']:.1f} C")
        start = time.time()
        result = notify(box, ask)
        secs = round(time.time() - start, 1)
        timing = last_timing
    line = (f"[{name}] level={result['level']} light={result['light']} "
            f"pickup={result['pickup']} source={result['source']} ({secs}s)\n{result['message']}")
    print(f"[{name}] LLM timing: {timing}")
    print(f"[{name}] raw LLM output: {result['raw']!r}")
    if result["rejected"]:
        print(f"[{name}] LLM text rejected: {result['rejected']}")
    print(line)
    publish({"time": datetime.now().strftime("%H:%M:%S"), "scenario": name,
             "box_id": box["box_id"], "location": box["location"], "temp_c": box["temp_c"],
             "kits": len(result["kits"]), "level": result["level"], "light": result["light"],
             "pickup": result["pickup"], "source": result["source"], "secs": secs,
             "message": result["message"], "rejected": result["rejected"]})
    return result


# Chat page: type a scenario name, get the courier message back as the answer
# (it also appears in the notifications list).
def on_prompt(_, data):
    name = (data.get("prompt", "") or "").strip().lower()
    if name not in SCENARIOS:
        text = "Type one of: " + ", ".join(SCENARIOS)
    else:
        try:
            text = run(name)["message"]
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

# ~10 s per LLM call, so the startup self-test runs a few; the rest can be typed on the chat page.
SELF_TEST = ("normal", "soon", "hpv_3h_left", "overdue", "empty", "unknown")   # one of each level


def self_test():
    print("=== OmaBox self-test ===")
    for n in SELF_TEST:
        try:
            run(n)
        except Exception as e:
            print(f"[{n}] ERROR: {e}")
    print("=== self-test done, now try the chat page ===")


# Run the self-test in the background so the web page is available right away
# and shows the notifications as they come in.
show_brick_api()
threading.Thread(target=self_test, daemon=True).start()

App.run()
