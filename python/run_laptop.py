"""Laptop-only test of the OmaBox logic (no Arduino imports).

    python run_laptop.py --no-llm               # template messages only
    python run_laptop.py                        # use a local Ollama model
    python run_laptop.py --model qwen3:0.6b     # pick the Ollama model
    python run_laptop.py warm empty             # run only some scenarios
    python run_laptop.py --no-llm --chat "drop HPV-0001 21h" "temp 33" collected
                                                # feed chat commands into a real BoxState
"""
import argparse
import json
import time
import urllib.request

from omabox_logic import (SCENARIOS, SYSTEM_PROMPT, BoxState, handle_event, notify, parse_command,
                          scenario)

def no_llm(_prompt):
    raise RuntimeError("LLM disabled (--no-llm)")


def ollama_ask(model, url):
    def ask(prompt):
        body = json.dumps({
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": prompt}],
            "options": {"num_predict": 120},
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["message"]["content"]
    return ask


def main():
    p = argparse.ArgumentParser(description="Run the OmaBox scenarios on the laptop.")
    p.add_argument("scenarios", nargs="*", help="any of: " + ", ".join(SCENARIOS) + " (default: all)")
    p.add_argument("--no-llm", action="store_true", help="skip the LLM, use template messages")
    p.add_argument("--model", default="qwen3:0.6b", help="Ollama model name")
    p.add_argument("--url", default="http://localhost:11434/api/chat", help="Ollama chat URL")
    p.add_argument("--chat", nargs="+", metavar="CMD", help="chat commands to apply to a BoxState, in order")
    p.add_argument("--state", help="JSON file to keep the box state in (default: in memory only)")
    args = p.parse_args()

    bad = [n for n in args.scenarios if n not in SCENARIOS]
    if bad:
        p.error(f"unknown scenario(s): {', '.join(bad)}; choose from {', '.join(SCENARIOS)}")

    ask = no_llm if args.no_llm else ollama_ask(args.model, args.url)

    if args.chat:
        state = BoxState("BOX-12", "Kuopio library", args.state)
        for cmd in args.chat:
            event = parse_command(cmd)
            if event is None:
                print(f"> {cmd}\n  not a command\n")
                continue
            info, r = handle_event(state, event, ask)
            print(f"> {cmd}\n  {info}")
            if r:
                print(f"  level={r['level']} light={r['light']} pickup={r['pickup']} source={r['source']}"
                      f"\n  {r['message']}")
            print()
        return
    for name in args.scenarios or SCENARIOS:
        start = time.time()
        r = notify(scenario(name), ask)
        secs = round(time.time() - start, 1)
        if not args.no_llm:
            print(f"[{name}] raw LLM output: {r['raw']!r}")
        if r["rejected"] and not args.no_llm:
            print(f"[{name}] LLM text rejected: {r['rejected']}")
        print(f"[{name}] level={r['level']} light={r['light']} pickup={r['pickup']} "
              f"source={r['source']} ({secs}s)\n{r['message']}\n")


if __name__ == "__main__":
    main()
