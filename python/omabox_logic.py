"""OmaBox core logic: plain Python, no Arduino imports.

Runs the same on your laptop and on the UNO Q. The only thing that differs
between the two is the `ask(prompt) -> str` function you pass in.
"""
from datetime import datetime, timedelta

# How long a kit may wait before it must be at the lab (hours).
# HPV: Fimlab asks people to mail the sample within 24 h of taking it.
# FIT: manufacturers advise analysis within ~14 days at room temperature.
DEADLINE_H = {"HPV": 24, "FIT": 14 * 24}

TEMP_MAX_C = 30.0    # above this, flag the box as too warm
URGENT_LEFT_H = 4    # less time left than this -> urgent pickup
SOON_LEFT_H = 12     # less time left than this -> pickup soon

SYSTEM_PROMPT = (
    "You write short status messages for a lab courier about a sample drop-off box. "
    "Use only the facts given. Do not invent numbers. Do not give medical advice. "
    "Answer in at most 2 short sentences."
)


def kit_status(kit, now):
    """Hours since drop-off and hours left before the kit's deadline."""
    age_h = (now - kit["dropped_at"]).total_seconds() / 3600
    left_h = DEADLINE_H[kit["kit_type"]] - age_h
    return {**kit, "age_h": round(age_h, 1), "left_h": round(left_h, 1)}


def box_decision(box, now):
    """Decide what the box needs. Plain code, so the numbers are always correct."""
    kits = sorted((kit_status(k, now) for k in box["kits"]), key=lambda k: k["left_h"])
    too_hot = box["temp_c"] > TEMP_MAX_C

    if not kits:
        level, reason = "empty", "no kits in the box, the courier can skip this stop"
    elif kits[0]["left_h"] < URGENT_LEFT_H or too_hot:
        level = "urgent"
        reason = (f"box is too warm ({box['temp_c']} C)" if too_hot
                  else f"kit {kits[0]['kit_id']} has {kits[0]['left_h']} h left")
    elif kits[0]["left_h"] < SOON_LEFT_H:
        level, reason = "soon", f"kit {kits[0]['kit_id']} has {kits[0]['left_h']} h left"
    else:
        level, reason = "ok", "all kits are well within their deadlines"

    light = {"empty": "off", "ok": "green", "soon": "yellow", "urgent": "red"}[level]
    return {"level": level, "reason": reason, "light": light,
            "pickup": level in ("soon", "urgent"), "kits": kits}


def build_prompt(box, decision):
    lines = [f"Box: {box['box_id']} at {box['location']}",
             f"Kits inside: {len(decision['kits'])}",
             f"Temperature: {box['temp_c']} C",
             f"Decision: {decision['level']}, because {decision['reason']}"]
    for k in decision["kits"][:3]:
        lines.append(f"- {k['kit_id']} ({k['kit_type']}): waited {k['age_h']} h, {k['left_h']} h left")
    return "\n".join(lines) + "\nWrite the courier message."


def template_message(box, decision):
    """Fallback if the LLM is slow, fails, or writes something unusable."""
    action = {"empty": "No pickup needed.", "ok": "No pickup needed yet.",
              "soon": "Please collect today.", "urgent": "Please collect as soon as possible."}
    return (f"{box['box_id']} ({box['location']}): {len(decision['kits'])} kits, "
            f"{decision['reason']}. {action[decision['level']]}")


def notify(box, ask, now=None):
    """Make the courier message. `ask` is any function prompt -> text."""
    now = now or datetime.now()
    decision = box_decision(box, now)
    try:
        text = (ask(build_prompt(box, decision)) or "").strip()
        # Basic guardrail: must be short and mention the right box.
        if not text or len(text) > 300 or box["box_id"] not in text:
            raise ValueError("unusable LLM answer")
        source = "llm"
    except Exception:
        text, source = template_message(box, decision), "template"
    return {**decision, "message": text, "source": source}


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
