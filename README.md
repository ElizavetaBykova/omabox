# LähiLab: a smart drop-off box for home lab samples

> A smart drop-off box for home cancer tests that makes sure no sample arrives too late,
> and no courier drives to an empty box.

Built at **Junction 2026 (Helsinki)** for the Arduino challenge *Green European Renaissance*.
Tag: **Junction Finland 2026**.

LähiLab is a drop-off box for home-collected lab samples. It starts with HPV self-sampling kits and FIT
stool kits from national screening. The box goes in a pharmacy, library or health centre where a lab
courier already stops. It runs on an **Arduino UNO Q**, and all AI runs **locally on the board**, with no cloud.

- A **camera** reads the QR code on each kit (kit ID + sample type) and timestamps the drop-off.
- A **Modulino Thermo** checks the temperature inside the box.
- Python logic works out every kit's deadline and decides whether a courier is needed:
  *no pickup*, *collect today*, *as soon as possible*, or *late, tell the lab*.
- A **small LLM on the board** (Qwen3.5 0.8B through llama.cpp) writes the short message for the
  courier or lab. Guardrails check it, and a fixed template is used if the check fails.
- A **web dashboard** on the board shows live box status, the messages, and a map of a demo box network.

> **LähiLab never analyses samples or gives a diagnosis or medical advice.** Labs (e.g. Fimlab) do that.
> Whether a late sample can still be used is always the lab's decision, never the box's.

## Why

- Fimlab's HPV self-sampling pilot requires the sample to be mailed within **24 h** of collection;
  late samples are not analysed (fimlab.fi).
- In one US lab, **14 %** of FIT samples were rejected for arriving more than 14 days after collection, and
  **6 %** because the collection date was missing (Federal Practitioner 2024;41(suppl 2):S42).
- Self-sampling and reminders raised cervical screening participation in a Finnish study from
  72.6 % → 79.2 % → 82.2 % (Int J Cancer 2015;136(6):E677–E684).

**Green angle:** a wasted sample means a new kit, new post, a new lab run, and sometimes a person who
gives up on screening. Couriers also skip trips to empty boxes, and the AI runs on a small low-power board.

## How it works

```
 kit QR ──► camera.py ──┐
                        ├─► BoxState + box_decision()  ──► template message ──► dashboard card (at once)
 Thermo ──► sketch.ino ─┘     (Python: all numbers,          │
          (Bridge)             deadlines, pickup)            └─► local LLM rewords it ──► check_message()
                                                                   ──► card updated (or template kept)
```

1. A kit QR code (`HPV-0001`, `FIT-0002`, any `TYPE-NUMBER`) becomes a `kit_dropped` event.
   A courier QR code (`COURIER-0001/BOX-12`) empties the box. A courier code for another box is refused.
2. `omabox_logic.py` updates the saved box state (`data/box_state.json`) and computes the decision level:

   | level | light | pickup | when |
   |---|---|---|---|
   | empty | off | no | no kits |
   | ok | green | no | all kits have ≥ 12 h left, box within limits |
   | soon | yellow | yes, "collect today" | a kit has < 12 h left |
   | urgent | red | yes, "as soon as possible" | a kit has < 4 h left, or the box is too warm/cold for a kit in it |
   | overdue | red | yes, plus "tell the lab it is late" | a kit is past its deadline |

3. The correct message is first written as plain facts by a template and shown right away.
   The LLM then only **rewords** it (about 10 s on the board). `check_message()` rejects invented numbers,
   wrong kit counts, medical words, and text that contradicts the decision.
4. The temperature is read every 30 s. A new message is sent only when the level changes.

### Sample types

The lab configures the rules in `SAMPLE_TYPES` (`python/omabox_logic.py`), and the box enforces them.
The box is **not refrigerated**, so it accepts room-temperature samples only.

| code | sample | deadline | temperature |
|---|---|---|---|
| HPV | HPV self-sample | 24 h | 4–30 °C |
| FIT | FIT stool kit | 14 days | ≤ 30 °C |
| DSW, DNA, DBS | dry swab, DNA cheek swab, dried blood spot | 24 h / 7 d / 7 d | *examples, not yet sourced* |
| anything else | unknown type | 24 h | 15–25 °C, flagged "check it with the lab" |

## Hardware

- Arduino UNO Q (2 GB RAM)
- Modulino Thermo on the Qwiic connector (I2C `Wire1`, address `0x45`/`0x44`)
- USB webcam through a USB-C hub
- Printed kit / courier QR codes: see `qr_codes/`

## Run it

### On the board (Arduino App Lab)

1. Copy this folder to the board as an App Lab app (`~/ArduinoApps/omabox`).
2. Press **Run** in Arduino App Lab. The first LLM message takes about 25 s while the model loads.
3. Open the dashboard at `http://<UNO-Q-IP>:7000`.
4. Show a kit QR code to the camera, or type chat commands on the page:

   ```
   drop HPV-0001 21h     # a kit dropped 21 h ago
   temp 33               # pretend the box is 33 °C
   pickup | status       # ask for a pickup / the current status
   collected             # the courier emptied the box
   hpv_3h_left           # load a test scenario (see SCENARIO_DATA)
   ```

> Do **not** add `opencv-python` to `python/requirements.txt`. The board already ships `cv2`, and a pip copy
> breaks the bricks (`ImportError: libGL.so.1`). If that happens, delete `~/ArduinoApps/omabox/.cache/.venv`
> on the board and run again.

### On a laptop (logic only, no Arduino needed)

From `python/`:

```bash
python3 run_laptop.py --no-llm                                     # all test scenarios, template messages
python3 run_laptop.py --no-llm normal overdue                      # only some scenarios
python3 run_laptop.py --no-llm --chat "drop HPV-0001 21h" "temp 33" collected
python3 run_laptop.py --model qwen3:0.6b                           # use a local Ollama model as the LLM
python3 camera.py                                                  # test the QR camera
```

## Project layout

```
├── app.yaml               # App Lab descriptor (bricks: llm, web_ui)
├── assets/                # dashboard: index.html, app.js (live box + messages), network.js (demo map)
├── python/
│   ├── main.py            # board entry point: LLM brick, web UI, camera / sensor / LLM threads
│   ├── omabox_logic.py    # plain Python: sample rules, decisions, prompt, guardrails, BoxState, scenarios
│   ├── camera.py          # headless QR scanner (KitScanner.scan_kit)
│   ├── run_laptop.py      # laptop test harness (template or Ollama)
│   └── qr_scanner.py      # early desktop QR scanner (not used by the app)
├── sketch/sketch.ino      # MCU: reads the Thermo, exposes read_temperature_c over the Bridge
└── qr_codes/              # printable test QR codes
```

The boxes on the dashboard map, other than the live board (`BOX-12`, Kuopio library), are **simulated
demo data**.

## Team

Junction 2026: two developers (board, logic & LLM / sensors & camera) and one business lead
(data, mentors, pitch).
