def coerce_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float_optional(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_time(seconds):
    if seconds is None:
        return ""
    seconds = max(0.0, float(seconds))
    return f"{int(seconds // 60)}:{seconds % 60:06.3f}"
