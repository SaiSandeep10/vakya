"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 4 | mcp_servers/utility_server.py

Utility MCP Tool Server.
Provides timers, reminders, date/time, calculations, and unit conversion.
All tools run locally — no internet needed.
"""

import math
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent to path so we can import memory
sys.path.append(str(Path(__file__).parent.parent))
from core.memory import Memory

# ──────────────────────────────────────────────
# ACTIVE TIMERS — in-memory (not persisted)
# ──────────────────────────────────────────────

_active_timers: dict[str, threading.Timer] = {}
_timer_callback = None    # set by main.py: a function(label) that speaks the alert


def set_timer_callback(callback):
    """main.py calls this to register the TTS callback."""
    global _timer_callback
    _timer_callback = callback


# ──────────────────────────────────────────────
# TOOL FUNCTIONS
# ──────────────────────────────────────────────

def get_current_time() -> dict:
    """Return the current date and time."""
    now = datetime.now()
    return {
        "success": True,
        "message": now.strftime("It is %I:%M %p on %A, %B %d, %Y."),
        "time":    now.strftime("%H:%M"),
        "date":    now.strftime("%Y-%m-%d"),
        "day":     now.strftime("%A"),
    }


def set_timer(duration_seconds: int, label: str = "Timer") -> dict:
    """
    Set a countdown timer.
    duration_seconds: how long to wait
    label: name of the timer (spoken when it fires)
    """
    if duration_seconds <= 0:
        return {"success": False, "message": "Duration must be greater than zero."}

    label = label.strip() or "Timer"

    def _fire():
        msg = f"{label} is done."
        print(f"\n[VAKYA Timer] {msg}")
        if _timer_callback:
            _timer_callback(msg)
        _active_timers.pop(label, None)

    # Cancel existing timer with same label
    if label in _active_timers:
        _active_timers[label].cancel()

    t = threading.Timer(duration_seconds, _fire)
    t.daemon = True
    t.start()
    _active_timers[label] = t

    # Human-readable duration
    minutes, seconds = divmod(duration_seconds, 60)
    hours, minutes   = divmod(minutes, 60)
    parts = []
    if hours:   parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes: parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds: parts.append(f"{seconds} second{'s' if seconds > 1 else ''}")
    duration_str = " and ".join(parts)

    return {
        "success":  True,
        "message":  f"{label} set for {duration_str}.",
        "label":    label,
        "duration": duration_seconds,
    }


def cancel_timer(label: str) -> dict:
    """Cancel an active timer by label."""
    label = label.strip()
    if label in _active_timers:
        _active_timers[label].cancel()
        _active_timers.pop(label)
        return {"success": True, "message": f"{label} cancelled."}
    return {"success": False, "message": f"No active timer named '{label}'."}


def list_timers() -> dict:
    """List all currently active timers."""
    if not _active_timers:
        return {"success": True, "message": "No active timers.", "timers": []}
    names = list(_active_timers.keys())
    return {
        "success": True,
        "message": f"Active timers: {', '.join(names)}.",
        "timers":  names
    }


def add_reminder(label: str, due_at: str) -> dict:
    """
    Add a reminder to persistent memory.
    due_at format: 'YYYY-MM-DD HH:MM'  e.g. '2026-05-14 15:00'
    """
    try:
        # Validate datetime format
        datetime.strptime(due_at.strip(), "%Y-%m-%d %H:%M")
        memory = Memory()
        rid = memory.add_reminder(label, due_at)
        memory.close()
        return {
            "success":     True,
            "message":     f"Reminder set: '{label}' at {due_at}.",
            "reminder_id": rid
        }
    except ValueError:
        return {
            "success": False,
            "message": "Invalid date format. Use YYYY-MM-DD HH:MM, for example 2026-05-14 15:00."
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def calculate(expression: str) -> dict:
    """
    Evaluate a mathematical expression safely.
    Examples: '15 * 8', 'sqrt(144)', '2 ** 10', '(5 + 3) / 2'
    """
    expression = expression.strip()

    # Safe math context — only allow math functions
    safe_globals = {
        "__builtins__": {},
        "sqrt":  math.sqrt,
        "pow":   math.pow,
        "abs":   abs,
        "round": round,
        "floor": math.floor,
        "ceil":  math.ceil,
        "log":   math.log,
        "log10": math.log10,
        "sin":   math.sin,
        "cos":   math.cos,
        "tan":   math.tan,
        "pi":    math.pi,
        "e":     math.e,
    }

    try:
        result = eval(expression, safe_globals)   # nosec — restricted globals
        result = round(float(result), 6)
        # Remove trailing zeros
        result_str = f"{result:.6f}".rstrip("0").rstrip(".")
        return {
            "success":    True,
            "message":    f"{expression} equals {result_str}.",
            "result":     result,
            "expression": expression
        }
    except ZeroDivisionError:
        return {"success": False, "message": "Cannot divide by zero."}
    except Exception:
        return {"success": False, "message": f"Could not evaluate '{expression}'. Please check the expression."}


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """
    Convert between common units.
    Supports: temperature, length, weight, time.
    """
    from_unit = from_unit.lower().strip()
    to_unit   = to_unit.lower().strip()

    conversions = {
        # Temperature
        ("celsius", "fahrenheit"):   lambda v: v * 9/5 + 32,
        ("fahrenheit", "celsius"):   lambda v: (v - 32) * 5/9,
        ("celsius", "kelvin"):       lambda v: v + 273.15,
        ("kelvin", "celsius"):       lambda v: v - 273.15,

        # Length
        ("km", "miles"):             lambda v: v * 0.621371,
        ("miles", "km"):             lambda v: v * 1.60934,
        ("meters", "feet"):          lambda v: v * 3.28084,
        ("feet", "meters"):          lambda v: v / 3.28084,
        ("cm", "inches"):            lambda v: v / 2.54,
        ("inches", "cm"):            lambda v: v * 2.54,

        # Weight
        ("kg", "pounds"):            lambda v: v * 2.20462,
        ("pounds", "kg"):            lambda v: v / 2.20462,
        ("grams", "ounces"):         lambda v: v / 28.3495,
        ("ounces", "grams"):         lambda v: v * 28.3495,

        # Time
        ("hours", "minutes"):        lambda v: v * 60,
        ("minutes", "hours"):        lambda v: v / 60,
        ("minutes", "seconds"):      lambda v: v * 60,
        ("seconds", "minutes"):      lambda v: v / 60,
        ("days", "hours"):           lambda v: v * 24,
        ("hours", "days"):           lambda v: v / 24,
    }

    key = (from_unit, to_unit)
    if key not in conversions:
        return {
            "success": False,
            "message": f"Cannot convert {from_unit} to {to_unit}. Supported: temperature, length, weight, time."
        }

    result = round(conversions[key](value), 4)
    return {
        "success": True,
        "message": f"{value} {from_unit} is {result} {to_unit}.",
        "result":  result
    }


# ──────────────────────────────────────────────
# TOOL DEFINITIONS
# ──────────────────────────────────────────────

UTILITY_TOOLS = [
    {
        "name":        "get_current_time",
        "description": "Get the current date and time.",
        "function":    get_current_time,
        "parameters":  {}
    },
    {
        "name":        "set_timer",
        "description": "Set a countdown timer that fires after a given number of seconds. Use label to name the timer.",
        "function":    set_timer,
        "parameters":  {"duration_seconds": int, "label": str}
    },
    {
        "name":        "cancel_timer",
        "description": "Cancel an active countdown timer by its label.",
        "function":    cancel_timer,
        "parameters":  {"label": str}
    },
    {
        "name":        "list_timers",
        "description": "List all currently active timers.",
        "function":    list_timers,
        "parameters":  {}
    },
    {
        "name":        "add_reminder",
        "description": "Add a persistent reminder that fires at a specific date and time. due_at format: YYYY-MM-DD HH:MM",
        "function":    add_reminder,
        "parameters":  {"label": str, "due_at": str}
    },
    {
        "name":        "calculate",
        "description": "Evaluate a mathematical expression. Supports +, -, *, /, sqrt(), pow(), sin(), cos(), pi, and more.",
        "function":    calculate,
        "parameters":  {"expression": str}
    },
    {
        "name":        "convert_units",
        "description": "Convert between units of temperature, length, weight, or time.",
        "function":    convert_units,
        "parameters":  {"value": float, "from_unit": str, "to_unit": str}
    },
]


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python mcp_servers/utility_server.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] Current time:")
    print(json.dumps(get_current_time(), indent=2))

    print("\n[TEST] Calculate 15 * 8:")
    print(json.dumps(calculate("15 * 8"), indent=2))

    print("\n[TEST] Convert 100 km to miles:")
    print(json.dumps(convert_units(100, "km", "miles"), indent=2))

    print("\n[TEST] Convert 37 celsius to fahrenheit:")
    print(json.dumps(convert_units(37, "celsius", "fahrenheit"), indent=2))

    print("\n[TEST] Set a 5 second timer:")
    import time
    set_timer_callback(lambda msg: print(f"  ALERT: {msg}"))
    print(json.dumps(set_timer(5, "Test Timer"), indent=2))
    print("  Waiting 6 seconds for timer to fire...")
    time.sleep(6)

    print("\n[TEST] Done.")