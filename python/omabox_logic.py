"""OmaBox core logic: plain Python, no Arduino imports.

Runs the same on your laptop and on the UNO Q. The only thing that differs
between the two is the `ask(prompt) -> str` function you pass in.
"""
import json
import os
import re
from datetime import datetime, timedelta

# Sample types and their rules. The LAB configures these; the box only enforces them.
#   deadline_h: max hours from drop-off until the sample must be at the lab
#   max_temp_c / min_temp_c: box temperature outside this range is flagged for kits of this type
#                            (None = no limit on that side)
# The box is NOT refrigerated: it is for room-temperature samples only. Cold-chain samples
# (e.g. swabs in transport medium at 2-8 C) and very short-lived ones (unpreserved urine, 2 h)
# were removed 14 Nov - they would be flagged urgent the moment they are dropped.
# To add a type: add a row here (with its source). Everything else follows automatically.
SAMPLE_TYPES = {
    # --- sourced (see CLAUDE.md "Key facts") ---
    # Fimlab HPV self-sampling pilot: mail within 24 h of collection, late samples are not analysed.
    # Dry swabs stay valid at 4-30 C in lab studies (Evalyn brush).
    "HPV": {"name": "HPV self-sample", "deadline_h": 24, "min_temp_c": 4.0, "max_temp_c": 30.0},
    # FIT: analyse within ~14 days at room temperature; heat (>30 C) degrades haemoglobin.
    # NOTE: an unsourced list (14 Nov) said 48 h at <=25 C / 7 days refrigerated - conflicts, not used.
    "FIT": {"name": "FIT stool kit", "deadline_h": 14 * 24, "min_temp_c": None, "max_temp_c": 30.0},

    # --- UNVERIFIED (from a team list 14 Nov, no source yet; find sources before using in the pitch) ---
    # Dry swab without medium (COVID-19/flu/RSV): 15-25 C, 24-48 h -> conservative 24 h.
    "DSW": {"name": "dry swab", "deadline_h": 24, "min_temp_c": 15.0, "max_temp_c": 25.0},
    # Cheek swab for DNA (pharmacogenetics): 15-30 C, "weeks to months" -> conservative 7 days.
    "DNA": {"name": "DNA cheek swab", "deadline_h": 7 * 24, "min_temp_c": 15.0, "max_temp_c": 30.0},
    # Dried blood spot on filter paper: 15-25 C, "weeks to months" -> conservative 7 days.
    # Also must avoid high humidity (Modulino Thermo measures it - not checked yet).
    "DBS": {"name": "dried blood spot", "deadline_h": 7 * 24, "min_temp_c": 15.0, "max_temp_c": 25.0},
}
# A type the lab has not configured: a fixed, cautious rule (24 h, 15-25 C) and a flag to the lab.
# (Not "the strictest of every limit": with cold-chain types that would be an impossible 15-8 C range.)
UNKNOWN_RULE = {"name": "unknown sample type", "deadline_h": 24, "min_temp_c": 15.0, "max_temp_c": 25.0}

QR_PATTERN = re.compile(r"^([A-Z][A-Z0-9]*)-(\d+)$")   # e.g. HPV-0001, FIT-0002

URGENT_LEFT_H = 4    # less time left than this -> urgent pickup
SOON_LEFT_H = 12     # less time left than this -> pickup soon

# Kept short on purpose: on the board, reading the prompt costs as much time as writing the answer.
SYSTEM_PROMPT = ("You rewrite status notes for a lab courier. Use only the given facts and numbers. "
                 "Never mention health, risk or test results. At most 2 short sentences.")

# The exact action the courier must read. Python decides it; the LLM only words the rest.
ACTION = {"empty": "No pickup needed, you can skip this stop.",
          "ok": "No pickup needed yet.",
          "soon": "Please collect today.",
          "urgent": "Please collect as soon as possible.",
          # Whether a late sample can still be used is the lab's call, never the box's.
          "overdue": "Please collect as soon as possible and tell the lab it is late."}

# Guardrails on the LLM text (case-insensitive regexes).
# MUST_SAY: every pattern must match, otherwise we append the exact action ourselves.
PICKUP = r"collect|pick ?up"
NO_PICKUP = r"no pickup|not needed"
MUST_SAY = {"urgent": (PICKUP,), "soon": (PICKUP,), "overdue": (PICKUP, r"\blab\b"),
            "ok": (NO_PICKUP,), "empty": (NO_PICKUP + "|skip",)}
TELL_LAB = "Please tell the lab it is late."
NOT_URGENT = r"urgent|as soon as possible|immediately|please collect"
MUST_NOT_SAY = {"urgent": NO_PICKUP + "|skip", "soon": NO_PICKUP + "|skip", "overdue": NO_PICKUP + "|skip",
                "ok": NOT_URGENT, "empty": NOT_URGENT}
# Words a courier message never needs (medical framing or made-up story). Ignored if they are in the facts,
# e.g. a location called "health centre".
BANNED = (r"risk|diagnos|result|positive|negative|cancer|disease|infect|abnormal|health|patient|"
          r"deliver|client|arriv|drop(?:ped)? off|skipped|was collected|has collected")

NO_THINK = "/no_think"   # Qwen3 switch: skip the <think> block (much faster on the board)
MAX_MESSAGE_CHARS = 300


def kit_type_from_qr(qr_text):
    """'HPV-0001' -> ('HPV-0001', 'HPV'). Returns None if the text is not a kit code.
    The type may still be unknown to SAMPLE_TYPES; rule_for() handles that."""
    m = QR_PATTERN.fullmatch((qr_text or "").strip().upper())
    return (m.group(0), m.group(1)) if m else None


# Courier QR codes: "COURIER-0001/BOX-12" = courier COURIER-0001 collects box BOX-12 (all kits out,
# cards reset). Both parts are checked: only known couriers, and only for THIS box, so a code printed
# for another box (or a random "COURIER-..." print) does not empty this one.
COURIER_PREFIX = "COURIER"
COURIER_CODES = {"COURIER-0001"}
COURIER_QR = re.compile(r"^(COURIER-\d+)/([A-Z0-9][A-Z0-9-]*)$")


def qr_code_of_interest(qr_text):
    """Normalised QR text if it is a kit code or a courier code, else None (used by camera.py)."""
    text = (qr_text or "").strip().upper()
    return text if (COURIER_QR.fullmatch(text) or kit_type_from_qr(text)) else None


def event_from_qr(code, time_iso, box_id):
    """QR text from the camera -> event, or None to ignore.
    'COURIER-0001/BOX-12' -> box_emptied (if it is this box), 'HPV-0001' -> kit_dropped."""
    text = (code or "").strip().upper()
    m = COURIER_QR.fullmatch(text)
    if m:
        courier, target = m.groups()
        if courier not in COURIER_CODES:
            print(f"camera: unknown courier {courier} ignored")
            return None
        if target != box_id.upper():
            print(f"camera: courier code is for {target}, this is {box_id}; ignored")
            return None
        return {"event": "box_emptied", "by": courier, "box_id": target, "time": time_iso}
    parsed = kit_type_from_qr(text)
    if not parsed:
        return None
    if parsed[1] == COURIER_PREFIX:
        print(f"camera: courier code {parsed[0]} has no box id (expected {parsed[0]}/{box_id}); ignored")
        return None
    return {"event": "kit_dropped", "kit_id": parsed[0], "time": time_iso}


def rule_for(kit_type):
    """(rule, known) for a sample type."""
    return (SAMPLE_TYPES[kit_type], True) if kit_type in SAMPLE_TYPES else (UNKNOWN_RULE, False)


def kit_status(kit, now):
    """Hours since drop-off and hours left before the kit's deadline (per its sample type)."""
    rule, known = rule_for(kit["kit_type"])
    age_h = (now - kit["dropped_at"]).total_seconds() / 3600
    left_h = rule["deadline_h"] - age_h
    return {**kit, "age_h": round(age_h, 1), "left_h": round(left_h, 1),
            "max_temp_c": rule.get("max_temp_c"), "min_temp_c": rule.get("min_temp_c"),
            "known_type": known}


def _join(parts):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def box_decision(box, now):
    """Decide what the box needs. Plain code, so the numbers are always correct.

    Levels: overdue > urgent > soon > ok, plus empty. Every problem found goes into the reason.
    """
    kits = sorted((kit_status(k, now) for k in box["kits"]), key=lambda k: k["left_h"])
    # Too warm / too cold = outside the limits of the most sensitive kit inside.
    temp = box["temp_c"]
    temp_limit = min((k["max_temp_c"] for k in kits if k["max_temp_c"] is not None), default=None)
    temp_min = max((k["min_temp_c"] for k in kits if k["min_temp_c"] is not None), default=None)
    too_hot = temp_limit is not None and temp is not None and temp > temp_limit
    too_cold = temp_min is not None and temp is not None and temp < temp_min
    unknown = [k for k in kits if not k["known_type"]]
    late = [k for k in kits if k["left_h"] < 0]
    urgent = [k for k in kits if 0 <= k["left_h"] < URGENT_LEFT_H]
    soon = [k for k in kits if URGENT_LEFT_H <= k["left_h"] < SOON_LEFT_H]

    problems = []
    if too_hot:
        problems.append(f"the box is too warm ({temp} C, limit {temp_limit} C)")
    if too_cold:
        problems.append(f"the box is too cold ({temp} C, minimum {temp_min} C)")
    for k in late[:2]:
        problems.append(f"kit {k['kit_id']} is {abs(k['left_h'])} h past its deadline")
    if urgent:
        problems.append(f"kit {urgent[0]['kit_id']} has {urgent[0]['left_h']} h left")
    elif soon and not (late or too_hot or too_cold):
        problems.append(f"kit {soon[0]['kit_id']} has {soon[0]['left_h']} h left")

    if not kits:
        level, reason = "empty", "no kits in the box"
    elif late:
        level = "overdue"
    elif urgent or too_hot or too_cold:
        level = "urgent"
    elif soon:
        level = "soon"
    else:
        level = "ok"
        reason = ("the kit is well within its deadline" if len(kits) == 1
                  else "all kits are well within their deadlines")
    if level in ("overdue", "urgent", "soon"):
        reason = _join(problems)

    # Extra sentences the courier/lab must read, whatever the level.
    notes = [f"Kit {k['kit_id']} has an unknown sample type ({k['kit_type']}), please check it with the lab."
             for k in unknown[:2]]

    light = {"empty": "off", "ok": "green", "soon": "yellow", "urgent": "red", "overdue": "red"}[level]
    return {"level": level, "reason": reason, "light": light,
            "pickup": level in ("soon", "urgent", "overdue"), "kits": kits,
            "temp_limit": temp_limit, "too_hot": too_hot,
            "temp_min": temp_min, "too_cold": too_cold, "notes": notes, "unknown_kits": [k["kit_id"] for k in unknown]}


def facts_text(box, decision):
    """The facts, already as a correct plain message. The LLM rewrites it; the checks compare against it."""
    n = len(decision["kits"])
    text = f"{box['box_id']} at {box['location']} has {n} kit{'' if n == 1 else 's'}"
    if decision["level"] != "empty":
        reason = decision["reason"]
        text += f". {reason[0].upper()}{reason[1:]}"
    return " ".join([f"{text}.", *decision["notes"], ACTION[decision["level"]]])


def temp_fact(box):
    """The measured box temperature as an extra fact (Dev 2, Thermo sensor); empty if no reading yet."""
    t = box.get("temp_c")
    return "" if t is None else f"Current measured box temperature: {float(t):.1f} C."


def build_prompt(box, decision):
    return (f"{facts_text(box, decision)}\n{temp_fact(box)}\n"
            "Any temperature warning is already in the facts above; do not invent another one. "
            f"Rewrite this as one short, friendly message for the courier. Keep every number. {NO_THINK}")


def clean_llm_text(text):
    """Remove Qwen thinking text and formatting; return just the message."""
    text = text or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)   # complete think blocks
    if "</think>" in text:                     # opening tag missing: drop everything before the close
        text = text.split("</think>")[-1]
    if "<think>" in text:                      # never closed (ran out of tokens): drop the rest
        text = text.split("<think>")[0]
    text = text.replace(NO_THINK, "")
    text = re.sub(r"^\s*(?:message|courier message|note|box)\s*:\s*", "", text, flags=re.I)  # leading label
    text = re.sub(r"[*_`#]+", "", text)        # markdown
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip()
    if len(text) > MAX_MESSAGE_CHARS:          # cut at the last full sentence that fits
        cut = text[:MAX_MESSAGE_CHARS]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[:end + 1] if end > 0 else cut
    return text


def invented_numbers(text, facts):
    """Numbers in the message that are not in the facts we gave the model."""
    allowed = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", facts)}   # "3.0" == "3"
    return [n for n in re.findall(r"\d+(?:\.\d+)?", text) if float(n) not in allowed]


def check_message(text, box, decision):
    """Return (fixed_text, None) if usable, or (text, reason) if it must be rejected."""
    facts = f"{facts_text(box, decision)} {temp_fact(box)}"
    level = decision["level"]
    if not text:
        return text, "empty after removing thinking text"
    extra = invented_numbers(text, facts)
    if extra:
        return text, f"numbers not in the facts: {extra}"
    n = len(decision["kits"])
    wrong_counts = [c for c in re.findall(r"(\d+)\s+kits?\b", text, flags=re.I) if int(c) != n]
    if wrong_counts:
        return text, f"wrong kit count {wrong_counts} (box has {n})"
    # Every problem in the decision must reach the courier: the kits named in it, and the heat.
    missing = [kit_id for kit_id in re.findall(r"\b[A-Z][A-Z0-9]*-\d+\b", decision["reason"])
               if kit_id.lower() not in text.lower()]
    if decision["too_hot"] and not re.search(r"warm|hot|heat|temperature", text, flags=re.I):
        missing.append("too warm")
    if decision["too_cold"] and not re.search(r"cold|temperature", text, flags=re.I):
        missing.append("too cold")
    if missing:
        return text, f"left out: {missing}"
    banned = [w for w in re.findall(BANNED, text, flags=re.I) if w.lower() not in facts.lower()]
    if banned:
        return text, f"banned words: {banned}"
    if re.search(MUST_NOT_SAY[level], text, flags=re.I):
        return text, f"contradicts the decision '{level}'"
    missing = [p for p in MUST_SAY[level] if not re.search(p, text, flags=re.I)]
    if missing:                                              # add the action ourselves
        add = TELL_LAB if missing == [r"\blab\b"] else ACTION[level]
        if len(text) + len(add) > MAX_MESSAGE_CHARS:
            return text, f"action for '{level}' missing"
        text = f"{text.rstrip('.!')}. {add}"
    for kit_id, note in zip(decision["unknown_kits"], decision["notes"]):
        if kit_id.lower() not in text.lower() or not re.search(r"\blab\b", text, flags=re.I):
            text = f"{text.rstrip('.!')}. {note}"            # unknown-type flag must reach the lab
    if len(text) > MAX_MESSAGE_CHARS + 120:
        return text, "too long"
    box_id = box["box_id"]
    text = re.sub(re.escape(box_id), box_id, text, flags=re.I)   # "Box-12" -> "BOX-12"
    if box_id not in text:
        text = f"{box_id}: {text}"                           # model forgot the box id
    return text, None


def template_message(box, decision):
    """Fallback if the LLM is slow, fails, or writes something unusable."""
    return facts_text(box, decision)


def notify(box, ask, now=None):
    """Make the courier message. `ask` is any function prompt -> text.

    Returns the decision plus: message, source ("llm" or "template"),
    raw (what the model said) and rejected (why the LLM text was not used, or None).
    ask=None: template only, at once (the LLM version comes later in the background).
    """
    now = now or datetime.now()
    decision = box_decision(box, now)
    if ask is None:
        return {**decision, "message": template_message(box, decision), "source": "template",
                "raw": "", "rejected": None}
    prompt = build_prompt(box, decision)
    raw, rejected = "", None
    try:
        raw = ask(prompt) or ""
        text, problem = check_message(clean_llm_text(raw), box, decision)
        if problem:
            raise ValueError(problem)
        source = "llm"
    except Exception as e:
        rejected = str(e) or type(e).__name__
        text, source = template_message(box, decision), "template"
    return {**decision, "message": text, "source": source, "raw": raw, "rejected": rejected}


def mock_box(now=None):
    """Fake box state for testing without hardware."""
    now = now or datetime.now()
    return {
        "box_id": "BOX-12",
        "location": "Kuopio library",
        "temp_c": 21.5,
        "kits": [
            {"kit_id": "HPV-0001", "kit_type": "HPV", "dropped_at": now - timedelta(hours=21)},
            {"kit_id": "FIT-0002", "kit_type": "FIT", "dropped_at": now - timedelta(days=2)},
            {"kit_id": "HPV-0003", "kit_type": "HPV", "dropped_at": now - timedelta(hours=3)},
        ],
    }


def _kit(kit_id, hours_ago, now):
    kit_id, kit_type = kit_type_from_qr(kit_id)
    return {"kit_id": kit_id, "kit_type": kit_type, "dropped_at": now - timedelta(hours=hours_ago)}


# Test scenarios shared by main.py (board) and run_laptop.py, so results are comparable.
# Each entry: name -> (location, temp_c, [(kit_id, hours_ago), ...]). Comment = expected level.
SCENARIO_DATA = {
    "normal":  ("Kuopio library", 21.5, [("FIT-0002", 48), ("HPV-0003", 3)]),           # ok / green
    "hpv_3h_left": ("Kuopio library", 21.5, [("HPV-0001", 21), ("FIT-0002", 48), ("HPV-0003", 3)]),  # urgent
    "warm":    ("Kuopio library", 33.0, [("HPV-0001", 21), ("FIT-0002", 48), ("HPV-0003", 3)]),  # urgent
    "empty":   ("Kuopio library", 21.5, []),                                         # empty / off
    "soon":    ("Tampere pharmacy", 22.0, [("HPV-0101", 15), ("FIT-0102", 5)]),        # yellow level
    "single":  ("Oulu pharmacy", 20.0, [("FIT-0201", 30)]),                            # "1 kit" grammar
    "overdue": ("Joensuu library", 21.0, [("HPV-0301", 26), ("HPV-0302", 2)]),         # past its deadline
    "hot_late": ("Rovaniemi library", 31.5, [("HPV-0401", 22)]),                       # too warm AND 2 h left
    "fit_old": ("Kotka pharmacy", 24.0, [("FIT-0501", 13 * 24 + 18)]),                 # FIT with 6 h left
    "health":  ("Lahti health centre", 21.0, [("HPV-0601", 4)]),                       # "health" is in the facts
    "unknown": ("Vantaa pharmacy", 21.0, [("UTI-0801", 2), ("HPV-0802", 5)]),         # type not in SAMPLE_TYPES
    "mixed":   ("Helsinki pharmacy", 22.0, [("DNA-1101", 30), ("DBS-1102", 50), ("DSW-1103", 3)]),  # ok
    "cold":    ("Oulu library", 2.5, [("HPV-1201", 2), ("FIT-1202", 5)]),             # urgent: too cold
    "full":    ("Espoo health centre", 23.0, [(f"{'HPV' if i % 2 else 'FIT'}-07{i:02d}", i * 1.5)
                                              for i in range(1, 9)]),                  # 8 kits
}
SCENARIOS = tuple(SCENARIO_DATA)


def scenario(name, now=None):
    """Fake box state for one named test scenario."""
    now = now or datetime.now()
    location, temp_c, kits = SCENARIO_DATA[name]
    return {"box_id": "BOX-12", "location": location, "temp_c": temp_c,
            "kits": [_kit(k, h, now) for k, h in kits]}


# ---------------------------------------------------------------------------
# Real box state, built from events (camera, sensors, chat commands).
# ---------------------------------------------------------------------------
# Events that always produce a courier notification. A plain temperature reading only does
# when it changes the decision level (otherwise a reading every 30 s would keep the LLM busy).
NOTIFY_EVENTS = {"kit_dropped", "box_emptied", "temp_alert", "pickup_requested", "status"}


def parse_time(value, now):
    """ISO time from an event -> naive local datetime. Missing/invalid -> now."""
    if not value:
        return now
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return now
    return t.astimezone().replace(tzinfo=None) if t.tzinfo else t


class BoxState:
    """Kits currently in the box + last temperature. Saved to a JSON file after every change,
    so a restart of the app does not forget the kits inside."""

    def __init__(self, box_id, location, path=None):
        self.box_id, self.location, self.path = box_id, location, path
        self.temp_c = None
        self.kits = []            # [{"kit_id", "kit_type", "dropped_at": datetime}]
        self.load()

    # -- the dict box_decision()/notify() expect --
    def as_box(self):
        return {"box_id": self.box_id, "location": self.location, "temp_c": self.temp_c,
                "kits": [dict(k) for k in self.kits]}

    def apply_event(self, event, now=None):
        """Update the state. Returns (changed, info) where info is a short human-readable line."""
        now = now or datetime.now()
        kind = event.get("event")
        if kind == "kit_detected":                 # name used by qr_scanner.py
            kind = "kit_dropped"
        if event.get("temp_c") is not None:        # any event may carry a temperature
            self.temp_c = round(float(event["temp_c"]), 1)

        if kind == "kit_dropped":
            parsed = kit_type_from_qr(event.get("kit_id", ""))
            if not parsed:
                return False, f"ignored: '{event.get('kit_id')}' is not a kit code"
            kit_id, kit_type = parsed
            if kit_type == COURIER_PREFIX:
                return False, f"ignored: {kit_id} is a courier code, not a kit"
            if any(k["kit_id"] == kit_id for k in self.kits):
                return False, f"ignored: {kit_id} is already in the box"
            self.kits.append({"kit_id": kit_id, "kit_type": kit_type,
                              "dropped_at": parse_time(event.get("time"), now)})
            info = f"{kit_id} dropped"
        elif kind == "box_emptied":
            n = len(self.kits)
            info = f"box emptied, {n} kit{'' if n == 1 else 's'} collected"
            if event.get("by"):
                info += f" by {event['by']}"
            self.kits = []
        elif kind in ("temp_reading", "temp_alert"):
            if self.temp_c is None:
                return False, "ignored: no temp_c in event"
            info = f"temperature {self.temp_c} C"
        elif kind == "tick":                       # periodic time check: deadlines move even without events
            return True, "time check"
        elif kind in ("pickup_requested", "status"):
            return True, kind.replace("_", " ")
        else:
            return False, f"ignored: unknown event '{kind}'"
        self.save()
        return True, info

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {"box_id": self.box_id, "location": self.location, "temp_c": self.temp_c,
                "kits": [{**k, "dropped_at": k["dropped_at"].isoformat(timespec="seconds")}
                         for k in self.kits]}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)                 # atomic: never a half-written file

    def load(self):
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.temp_c = data.get("temp_c")
            self.kits = [{**k, "dropped_at": datetime.fromisoformat(k["dropped_at"])}
                         for k in data.get("kits", [])]
        except (OSError, ValueError, KeyError) as e:
            print(f"BoxState: could not load {self.path} ({e}); starting empty")
            self.kits, self.temp_c = [], None


def _signature(decision):
    """What the courier cares about. Hours left change every minute, so they are not part of it."""
    return decision["level"], decision["too_hot"], decision["too_cold"]


def should_notify(event, before, after):
    kind = event.get("event")
    kind = "kit_dropped" if kind == "kit_detected" else kind
    return kind in NOTIFY_EVENTS or _signature(before) != _signature(after)


def handle_event(state, event, ask, now=None):
    """Apply one event and, if needed, make the courier notification.
    Returns (info, result) where result is notify()'s dict or None if no message was needed."""
    now = now or datetime.now()
    # "before" = what the box last announced (not the level a moment ago at the same clock time),
    # so time passing alone (tick / temp_reading every 30 s) moves a kit ok -> soon -> urgent -> overdue.
    announced = getattr(state, "announced", None)
    before = announced if announced is not None else box_decision(state.as_box(), now)
    changed, info = state.apply_event(event, now)
    if not changed:
        return info, None
    after = box_decision(state.as_box(), now)
    if not should_notify(event, before, after):
        return info, None
    state.announced = after
    return info, notify(state.as_box(), ask, now)


CHAT_HELP = ("Commands: drop <KIT-ID> [hours ago, e.g. 21h] | temp <C> | collected | pickup | status | "
             "or a test scenario name")


def parse_command(text, now=None):
    """Chat command -> event dict, or None if it is not a command. Lets us demo without hardware:
    'drop HPV-0001 21h', 'temp 33', 'collected', 'pickup', 'status'."""
    now = now or datetime.now()
    words = (text or "").strip().split()
    if not words:
        return None
    cmd, args = words[0].lower(), words[1:]
    if cmd == "drop" and args:
        hours = 0.0
        if len(args) > 1:
            try:
                hours = float(args[1].lower().rstrip("h"))
            except ValueError:
                return None
        return {"event": "kit_dropped", "kit_id": args[0],
                "time": (now - timedelta(hours=hours)).isoformat(timespec="seconds")}
    if cmd == "temp" and len(args) == 1:
        try:
            return {"event": "temp_reading", "temp_c": float(args[0])}
        except ValueError:
            return None
    if cmd in ("collected", "emptied"):
        return {"event": "box_emptied"}
    if cmd == "pickup":
        return {"event": "pickup_requested"}
    if cmd == "status":
        return {"event": "status"}
    return None
