from host_monitor.checks.processes import _format_command


def test_format_command_redacts_sensitive_values_and_urls():
    command = _format_command(
        [
            "python",
            "-m",
            "host_monitor",
            "--discord-webhook-url=https://discord.com/api/webhooks/123/token",
            "--token",
            "secret-value",
            "https://example.com/path",
            "`quoted`",
        ],
        "python",
    )

    assert "secret-value" not in command
    assert "discord.com/api/webhooks" not in command
    assert "https://example.com/path" not in command
    assert "`" not in command
    assert "--token [redacted]" in command
