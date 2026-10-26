import pytest

from obsidian_mcp_server.links import extract_wikilinks


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("[[A]] [[A]] [[#heading]]", ["A"]),
        ("nothing linked", []),
    ],
)
def test_wikilinks_ignore_empty_targets_and_deduplicate(markdown, expected):
    assert extract_wikilinks(markdown) == expected
