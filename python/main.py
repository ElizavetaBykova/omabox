# OmaBox main.py for the UNO Q (App Lab) - TEST VERSION
#
# Put this file and omabox_logic.py in the app's python/ folder.
# Use a copy of the chatbot example so the LLM + WebUI bricks and its chat page exist.
#
# How to test:
#   1. Press Run and watch the App Lab console: a self-test runs all 4 scenarios once.
#   2. Open the chat page and type a scenario name: normal, warm, empty, fine
#      The courier message appears as the chat answer.

from datetime import timedelta
import time

from arduino.app_bricks.llm import LargeLanguageModel
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

from omabox_logic import SYSTEM_PROMPT, mock_box, notify

llm = LargeLanguageModel(system_prompt=SYSTEM_PROMPT)   # no memory: each message stands alone
ui = WebUI()


def ask(prompt):
    llm.clear_memory()
    return "".join(str(chunk) for chunk in llm.chat_stream(prompt))


def scenario(name):
    box = mock_box()
    if name == "warm":
        box["temp_c"] = 33.0
    elif name == "empty":
        box["kits"] = []
    elif name == "fine":
        box["kits"] = box["kits"][1:]          # drop the kit that is close to its deadline
    return box


def run(name):
    start = time.time()
    result = notify(scenario(name), ask)
    secs = round(time.time() - start, 1)
    line = (f"[{name}] level={result['level']} light={result['light']} "
            f"pickup={result['pickup']} source={result['source']} ({secs}s)\n{result['message']}")
    print(line)
    return line


# Chat page: type a scenario name, get the courier message back as the "answer".
def on_prompt(_, data):
    name = (data.get("prompt", "") or "").strip().lower()
    if name not in ("normal", "warm", "empty", "fine"):
        text = "Type one of: normal, warm, empty, fine"
    else:
        text = run(name)
    ui.send_message("response", text)
    ui.send_message("stream_end", {})


ui.on_message("prompt", on_prompt)

# Self-test once at startup: results show in the App Lab console.
print("=== OmaBox self-test ===")
for n in ("normal", "warm", "empty", "fine"):
    try:
        run(n)
    except Exception as e:
        print(f"[{n}] ERROR: {e}")
print("=== self-test done, now try the chat page ===")

App.run()