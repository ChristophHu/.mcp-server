import pytest

from obsidian_mcp_server.tags import extract_inline_tags


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Text #work and #project/research", {"work", "project/research"}),
        ("#work #work #work", {"work"}),
        ("Heading ### #not-a-tag? #yes", {"not-a-tag", "yes"}),
        ("Inline `#hidden` and `x #also-hidden` #visible", {"visible"}),
        ("```md\n#hidden\n```\n~~~\n#hidden-too\n~~~\n#visible", {"visible"}),
        ("C# is a language; URL https://host/#anchor; ## heading", set()),
        ("", set()),
    ],
)
def test_extract_inline_tags(body: str, expected: set[str]):
    assert extract_inline_tags(body) == expected
