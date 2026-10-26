import re

_FENCED_CODE = re.compile(r"(?ms)^[ \t]*(?:```|~~~)[^\n]*\n.*?^[ \t]*(?:```|~~~)[ \t]*(?:\n|$)")
_INLINE_CODE = re.compile(r"`+[^`\n]*`+")
_TAG = re.compile(r"(?<![\w#/?&=%])#([^\W\d][\w/-]*|_[\w/-]*)", re.UNICODE)


def extract_inline_tags(body: str) -> set[str]:
    """Return Obsidian-style inline tags, excluding Markdown code spans/blocks."""
    visible = _FENCED_CODE.sub(" ", body)
    visible = _INLINE_CODE.sub(" ", visible)
    return set(_TAG.findall(visible))
