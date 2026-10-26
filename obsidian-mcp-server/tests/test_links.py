from obsidian_mcp_server.links import extract_wikilinks


def test_extracts_wikilink_targets_and_ignores_code_samples() -> None:
    markdown = (
        "[[A|Alias]] and [[Folder/B#Section]] and [[C^block]]\n"
        "```md\n[[FencedExample]]\n```\n"
        "Inline `[[InlineExample]]`\n"
    )

    assert extract_wikilinks(markdown) == ["A", "Folder/B", "C"]
