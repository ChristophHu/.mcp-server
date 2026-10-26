from __future__ import annotations

import re

_FENCED_CODE = re.compile(r"(?ms)^[ \t]{0,3}(`{3,}|~{3,}).*?^[ \t]{0,3}\1[ `~]*$")
_INLINE_CODE = re.compile(r"(`+)[^`\n]*?\1")
_WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")


def extract_wikilinks(markdown: str) -> list[str]:
    """Extract unique vault-relative targets from ordinary Obsidian wikilinks."""
    without_fences = _FENCED_CODE.sub("", markdown)
    visible_text = _INLINE_CODE.sub("", without_fences)
    targets: list[str] = []
    for match in _WIKILINK.finditer(visible_text):
        raw_target = match.group(1).split("|", 1)[0].strip()
        target = re.split(r"[#^]", raw_target, maxsplit=1)[0].strip()
        if target and target not in targets:
            targets.append(target)
    return targets
