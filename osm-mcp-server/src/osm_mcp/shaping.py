import math
import re
from collections.abc import Mapping
from typing import Any

MAX_NAME_LENGTH = 500
MAX_INSTRUCTION_LENGTH = 300
MAX_TAG_KEY_LENGTH = 255
MAX_TAG_VALUE_LENGTH = 500
MAX_MEASURE = 1e12
MAX_SAFE_INTEGER = 2**53 - 1
_UNSAFE_DATA = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")
_UNSAFE_ERROR = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def finite_number_from_text(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return finite_number(value)
    if not isinstance(value, str) or not value or len(value) > 40:
        return None
    try:
        return finite_number(float(value))
    except ValueError:
        return None


def valid_latlon(lat: Any, lon: Any) -> bool:
    latitude, longitude = finite_number(lat), finite_number(lon)
    return latitude is not None and longitude is not None and -90 <= latitude <= 90 and -180 <= longitude <= 180


def measure(value: Any) -> float | None:
    number = finite_number(value)
    return number if number is not None and 0 <= number <= MAX_MEASURE else None


def nonnegative_integer(value: Any) -> int | None:
    number = finite_number(value)
    if number is None or number < 0 or number > MAX_SAFE_INTEGER or not number.is_integer():
        return None
    return int(number)


def truncate(value: str, maximum: int) -> str:
    return value if len(value) <= maximum else value[:maximum] + "… (truncated)"


def clean_tags(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            continue
        if isinstance(raw, (str, int, float, bool)):
            result[truncate(key, MAX_TAG_KEY_LENGTH)] = truncate(str(raw), MAX_TAG_VALUE_LENGTH)
    return result


def clean_untrusted(value: Any, secret: str | None = None, *, error: bool = False) -> Any:
    pattern = _UNSAFE_ERROR if error else _UNSAFE_DATA
    if isinstance(value, str):
        cleaned = pattern.sub("", value)
        return cleaned.replace(secret, "[redacted]") if secret and len(secret) >= 8 else cleaned
    if isinstance(value, list):
        return [clean_untrusted(item, secret, error=error) for item in value]
    if isinstance(value, tuple):
        return [clean_untrusted(item, secret, error=error) for item in value]
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            safe_key = clean_untrusted(str(key), secret, error=error)
            if safe_key != "__proto__":
                cleaned[safe_key] = clean_untrusted(item, secret, error=error)
        return cleaned
    return value


def sanitize_error_body(body: str, maximum: int = 2000) -> str:
    cleaned = _UNSAFE_ERROR.sub("", body).strip()
    if re.match(r"^(<!doctype|<html[\s>]|<\?xml|<!--)", cleaned, re.IGNORECASE):
        return "(HTML error page omitted)"
    return cleaned if len(cleaned) <= maximum else cleaned[:maximum] + "… (truncated)"
