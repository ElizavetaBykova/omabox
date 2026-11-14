"""Laptop-only test of the OmaBox logic (no Arduino imports).

    python run_laptop.py --no-llm               # template messages only
    python run_laptop.py                        # use a local Ollama model
    python run_laptop.py --model qwen3:0.6b     # pick the Ollama model
    python run_laptop.py warm empty             # run only some scenarios
"""
import argparse
import json
import time
import urllib.request

from omabox_logic import SCENARIOS, SYSTEM_PROMPT, notify, scenario

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
    args = p.parse_args()

    bad = [n for n in args.scenarios if n not in SCENARIOS]
    if bad:
        p.error(f"unknown scenario(s): {', '.join(bad)}; choose from {', '.join(SCENARIOS)}")

    ask = no_llm if args.no_llm else ollama_ask(args.model, args.url)
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
