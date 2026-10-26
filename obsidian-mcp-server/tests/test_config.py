from obsidian_mcp_server.config import Settings


def test_settings_use_local_api_defaults_and_disable_writes() -> None:
    settings = Settings.from_env({})

    assert settings.api_url == "https://127.0.0.1:27124"
    assert settings.api_key == ""
    assert settings.enable_writes is False
    assert settings.enable_delete is False
    assert settings.max_content_bytes == 1_048_576


def test_settings_parse_explicit_security_flags() -> None:
    settings = Settings.from_env(
        {
            "OBSIDIAN_API_URL": "http://127.0.0.1:27123/",
            "OBSIDIAN_API_KEY": "secret-test-value",
            "OBSIDIAN_ENABLE_WRITES": "true",
            "OBSIDIAN_ENABLE_DELETE": "true",
            "OBSIDIAN_VERIFY_TLS": "false",
        }
    )

    assert settings.api_url == "http://127.0.0.1:27123"
    assert settings.api_key == "secret-test-value"
    assert settings.enable_writes is True
    assert settings.enable_delete is True
    assert settings.verify_tls is False
