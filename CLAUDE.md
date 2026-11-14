# OmaBox — project context for Claude Code

Junction 2026 hackathon (Helsinki). Judging Sunday 15 Nov, 14:00. Submission deadline: check (assume Sun 10:00).
Team: 3 people — Dev 1 (UNO Q, LLM, Python logic), Dev 2 (sensors + camera), Business (data, mentors, pitch).

## What OmaBox is
A smart drop-off box for ALL home-collected lab samples (starting with HPV self-sampling kits and FIT stool
kits from national screening), placed in pharmacies, libraries or health centres where a lab courier already
stops. Sample types and their rules (deadline, max temperature) live in `SAMPLE_TYPES` in omabox_logic.py;
the lab configures them, the box enforces them. Unknown types get the strictest rule and are flagged.

Decision 14 Nov ~14:10: after mentor feedback (AstraZeneca said their real gap is waiting for doctor
appointments after results, so OmaBox is not their direction) and three explored pivots, the team chose to
continue OmaBox, generalised to all home samples, aimed mainly at the Arduino challenge. No more pivots.

- Camera reads the QR code on each kit (kit ID + type) and timestamps the drop-off.
- Modulino Thermo logs temperature/humidity inside the box.
- A small LLM running locally on the Arduino UNO Q writes short courier/lab messages and (stretch) acts as a
  pickup agent with tools.
- A dashboard shows live box status. (Regional participation map dropped from scope 14 Nov; sourced
  participation numbers go in the pitch instead.)

Pitch line: "A smart drop-off box for home cancer tests that makes sure no sample arrives too late,
and no courier drives to an empty box."

OmaBox NEVER analyses samples or gives a diagnosis or medical advice. Labs (e.g. Fimlab) do that.
Whether a late sample can still be used is always the lab's decision, never the box's.

## Challenge we target
Arduino "Green European Renaissance" (main): Edge AI / physical AI on the UNO Q, local, no cloud, green impact.
Must publish on Arduino Project Hub with tag "Junction Finland 2026".
Green angle: fewer wasted samples (each wasted sample = a new kit, new post, new lab run and maybe a person
giving up on screening), no courier trips to empty boxes, all AI local on a small board.
(AstraZeneca "Equal Care Across Finland" was the original second target; deprioritised after mentor feedback.)

## Key facts (with sources — keep claims to these)
- Cervical screening participation in Finland ~73% (2023), lower among younger invitees, regional variation.
  (Aaltonen, Aalto thesis 2026)
- Reminder letters + self-sampling raised participation 72.6% -> 79.2% -> 82.2% in a Finnish study.
  (Int J Cancer 2015;136(6):E677-E684)
- Fimlab HPV self-sampling pilot (Pirkanmaa, Kanta-Häme, Central Finland, Päijät-Häme, Ostrobothnia):
  sample must be mailed within 24 h of collection; late samples are not analysed. (fimlab.fi)
- Dry HPV self-samples are stable for weeks/months in lab studies (e.g. Evalyn brush up to 32 weeks at 4–30 °C),
  so the 24 h limit is a programme rule, not biology. Long delays/heat still raise invalid rates.
- FIT kits: analyse within ~14 days at room temperature; heat (>30 °C) and delay degrade haemoglobin.
- Colorectal screening is national since 2022, expanding to everyone aged 56–74 by 2031.
- Late/undated samples are a real loss: in one US lab, 14% of FIT samples were rejected for arriving >14 days
  after collection and 6% because the collection date was missing. (Federal Practitioner 2024;41(suppl 2):S42)
- In one dry-swab study, 24% of dry self-samples were invalid vs 2.7% wet, due to long collection-to-analysis delay.

## Hardware
- Arduino UNO Q, **2 GB RAM** (tight). Debian Linux on the MPU + STM32 MCU.
- Modulinos via Qwiic: Thermo, Knob, Buzzer (+ maybe Pixels for light/status). USB camera via USB-C hub.
- Board hostname `judi`, user `arduino`, IP on venue Wi-Fi was 192.168.29.228 (may change).

## LLM on the board (what actually works — measured 14 Nov)
- Model: `llamacpp:Qwen3.5-0.8B-Q4_0` via App Lab's LLM brick (llama.cpp server on the board).
- Brick API (printed on the board): `LargeLanguageModel(system_prompt, temperature=0.7, max_tokens=512,
  timeout, tools, model, **kwargs)`; `chat_stream(message, images)` / `chat(message, images)` take NO options.
  So options go in the constructor: we use `max_tokens=80, temperature=0.2` plus
  `extra_body={"chat_template_kwargs": {"enable_thinking": False}}` (auto-fallback if rejected),
  and still add `/no_think` + strip `<think>` text.
- Speed: ~9–12 s per message after warm-up (first call ~23 s incl. model load). About half is reading the
  prompt, so keep prompts short (no few-shot examples — they doubled the time and the model copied them).
- The prompt is the correct facts already written as a plain message ("BOX-12 at … has 3 kits. Kit … has
  3.0 h left. Please collect as soon as possible.") and the model only rewrites it.
- Rule: the LLM only WORDS messages. All numbers, deadlines and pickup decisions are computed in Python.
  `check_message()` rejects invented numbers, banned words (risk, result, cancer, deliver, …), and text that
  contradicts the decision; it adds the exact action / lab note if missing. Always keep the template fallback.
- `python/requirements.txt` must NOT list opencv-python: the board ships cv2, and a venv copy breaks the
  bricks (ImportError libGL.so.1). If the venv gets polluted: on the board, `rm -rf ~/ArduinoApps/omabox/.cache/.venv`.

## Code layout (Arduino App Lab app)
```
omabox/
├── CLAUDE.md
├── app.yaml              # App Lab descriptor (bricks: LLM, WebUI) — don't hand-edit unless needed
├── assets/               # web page (chat UI from the example; dashboard later)
├── python/
│   ├── main.py           # board entry point (Dev 1). Uses arduino.app_bricks — runs ONLY on the board
│   ├── omabox_logic.py   # plain Python, no Arduino imports (Dev 1): SAMPLE_TYPES, kit_type_from_qr(),
│   │                     #   decisions, prompt, cleanup, checks, template fallback, test SCENARIO_DATA
│   ├── run_laptop.py     # laptop-only test of omabox_logic (Dev 1), template or Ollama
│   ├── prompts.py, system_prompt.txt   # from the original example (unused)
│   ├── qr_scanner.py     # (Dev 2) QR scanner, desktop-style for now; to become scan_kit() for the board
│   └── requirements.txt  # intentionally empty (see opencv note above)
└── sketch/               # (Dev 2, coming) sketch.ino + sketch.yaml for Modulinos on the MCU
```
File ownership: Dev 1 edits main.py + omabox_logic.py + run_laptop.py; Dev 2 edits qr_scanner.py + sketch/.
Avoid editing the other's files — suggest changes instead.

## Decision levels (omabox_logic.box_decision)
| level | light | pickup | when |
|---|---|---|---|
| empty | off | no | no kits |
| ok | green | no | all kits ≥ 12 h left, box within limits |
| soon | yellow | yes ("collect today") | a kit has < 12 h left |
| urgent | red | yes ("as soon as possible") | a kit has < 4 h left, or box above the strictest kit's max_temp_c |
| overdue | red | yes + "tell the lab it is late" | a kit is past its deadline |
Unknown sample types (not in SAMPLE_TYPES) use the strictest rule and add a "check it with the lab" note.
Test scenarios: `SCENARIO_DATA` (normal=ok, hpv_3h_left=urgent, warm, empty, soon, single, overdue, hot_late,
fit_old, health, unknown, full) — shared by the board self-test and run_laptop.py.

## Event contract (between sensors/camera and the logic)
```json
{"box_id": "BOX-01", "event": "kit_dropped", "kit_id": "HPV-0001",
 "kit_type": "HPV", "time": "2026-11-14T10:32:00", "temp_c": 21.4}
```
Other events: `temp_alert`, `box_emptied`, `pickup_requested`. Kit QR codes look like `HPV-0001`, `FIT-0002`
(any `TYPE-NUMBER`; parse with `kit_type_from_qr()`).
Note: qr_scanner.py currently emits `"kit_detected"` with `temp_c: null` — to align in Phase 3.

## How we work (important)
- Editing: on the laptop, the board's app folder is mounted with sshfs at `~/omabox-board` and opened in VS Code.
  Mount with `sshfs arduino@<ip>:/home/arduino/ArduinoApps/omabox ~/omabox-board -o reconnect,ServerAliveInterval=15`.
  If `~/omabox-board` looks empty, the mount dropped — files are safe on the board; just remount.
- Running: press **Run** in Arduino App Lab. Code using `arduino.app_bricks` cannot run on the laptop;
  ask the user to run it and paste the App Lab console output (the console keeps old runs — read the newest).
- Laptop-only test of the logic (from `python/`): `python3 run_laptop.py --no-llm` (template path),
  `python3 run_laptop.py [--model qwen3:0.6b]` (Ollama), scenario names as args to run a subset.
- Git: the user commits and pushes themselves, ON THE BOARD over SSH in `~/ArduinoApps/omabox`
  (git refuses to run through the sshfs mount). Claude Code never commits or pushes.
  Repo: github.com/ElizavetaBykova/omabox.
- NEVER suggest `rm -r` on a mount point. Unmount with `fusermount -u` (or `-uz`). Run sshfs only on the laptop.
  (We already lost the working copy once this way and restored it from GitHub.)

## Plan (phases, one small tested step at a time)
0. [x] Laptop test harness (run_laptop.py) + this CLAUDE.md
1. [x] LLM reliably answers (`source=llm`); 5 decision levels; guardrails; shared test scenarios;
       generalised to all home samples (SAMPLE_TYPES, kit_type_from_qr, unknown types flagged,
       per-sample temperature limits) — last board run of the generalised version still to confirm
2. [ ] Real box state (BoxState.apply_event) replacing mock data, persisted to a small JSON file
3. [ ] Camera on the board: headless non-blocking scan_kit(), `kit_dropped` events; LLM in background
       (template shown at once, LLM text replaces it); camera paused while the LLM runs (RAM)
4. [ ] Sensors over Bridge (Thermo temp, Knob = emptied, Buzzer/Pixels = status)
5. [ ] Pickup agent tools: request_pickup(urgency), set_status_light(color), notify_staff(message)
6. [ ] Dashboard: live box status only (kits, hours left, temp, light, last message)
7. [ ] Polish: demo mode (fast clock), Project Hub page, submission, demo video

## Timetable (updated Sat 14 Nov 14:25)
| when | Dev 1 (logic/LLM) | Dev 2 (camera/sensors) | Business |
|---|---|---|---|
| Sat 14:30–15:00 | confirm Phase 1 on board, commit | headless scan_kit() on board | Project Hub outline, pitch with new framing |
| Sat 15:00–16:00 | Phase 2 BoxState | sketch: Thermo + Knob over Bridge | sourced numbers for slides |
| Sat 16:00–17:30 | Phase 3 wire camera + background LLM | help wire camera | demo video script |
| **Sat ~17:30** | **checkpoint: real QR drop -> LLM message on the board** | | |
| Sat 17:30–19:00 | Phase 4 Bridge events into BoxState | Buzzer/Pixels status | |
| Sat 19:00–20:30 | Phase 6 dashboard (live status) | box enclosure / mounting | |
| **Sat ~20:30** | **checkpoint: full flow box -> decision -> LLM -> dashboard** | | |
| Sat 20:30–22:30 | Phase 5 agent tools (stretch) / bug fixes | bug fixes | Project Hub draft |
| Sun 08:00–09:30 | freeze code, demo mode, record video | | publish Project Hub, submit |
| **Sun 10:00** | **submission (verify the real deadline!)** | | |
| Sun 10:00–14:00 | rehearse pitch + live demo | | |
| **Sun 14:00** | **judging** | | |
Rule: if a checkpoint slips by > 1 h, cut the stretch items (agent tools first), not the end-to-end demo.

## Style for Claude Code
- Keep code simple and hackathon-robust; prefer small, testable changes.
- Respect the 2 GB RAM limit: no heavy libraries; don't run the LLM and heavy vision at the same moment.
- Never add medical advice or diagnosis features. Health-related text in the app comes only from approved,
  sourced content.
