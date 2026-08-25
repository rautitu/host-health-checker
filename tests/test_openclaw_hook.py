import json

import pytest

from host_monitor.config import AlertingConfig, Config
from host_monitor.models import Finding, Snapshot
from host_monitor.openclaw_hook import (
    post_openclaw_analysis_hook,
    render_openclaw_hook_payload,
    should_request_analysis_approval,
)


def test_analysis_hook_is_disabled_by_default():
    assert should_request_analysis_approval(_snapshot(), Config()) is False


def test_analysis_hook_requires_findings():
    config = Config(alerting=AlertingConfig(openclaw_analysis_hook_enabled=True))
    snapshot = _snapshot()
    snapshot.findings = []

    assert should_request_analysis_approval(snapshot, config) is False


def test_analysis_hook_ignores_info_findings():
    config = Config(alerting=AlertingConfig(openclaw_analysis_hook_enabled=True))
    snapshot = _snapshot()
    snapshot.findings = [Finding("info", "Informational only")]

    assert should_request_analysis_approval(snapshot, config) is False


def test_hook_payload_requests_approval_and_passes_snapshot_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = render_openclaw_hook_payload(_snapshot(), "123456")
    absolute_snapshot_path = str((tmp_path / "var/snapshots/example.json").resolve())

    assert payload["channel"] == "discord"
    assert payload["to"] == "channel:123456"
    assert payload["deliver"] is True
    assert "only task in this hook run" in payload["message"]
    assert "Do not analyze the findings or start the subagent" in payload["message"]
    assert "must not make changes" in payload["message"]
    assert "untrusted diagnostic data" in payload["message"]
    assert "Memory usage is high" in payload["message"]
    assert "Request id: " in payload["message"]
    assert "Snapshot timestamp: 2026-07-15T09:00:00+00:00" in payload["message"]
    assert f"Absolute snapshot path on the monitored host: {absolute_snapshot_path}" in payload["message"]
    assert "read the snapshot JSON from that exact path" in payload["message"]
    assert "must not depend on Discord channel history" in payload["message"]


def test_post_hook_uses_bearer_token(monkeypatch):
    monkeypatch.setenv("TEST_HOOK_URL", "http://127.0.0.1:18789/hooks/agent")
    monkeypatch.setenv("TEST_HOOK_TOKEN", "secret")
    monkeypatch.setenv("TEST_CHANNEL", "channel:123456")
    config = Config(
        alerting=AlertingConfig(
            openclaw_analysis_hook_enabled=True,
            openclaw_hook_url_env="TEST_HOOK_URL",
            openclaw_hook_token_env="TEST_HOOK_TOKEN",
            openclaw_discord_channel_env="TEST_CHANNEL",
        )
    )
    captured = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    post_openclaw_analysis_hook(_snapshot(), config)

    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:18789/hooks/agent"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data)["to"] == "channel:123456"
    assert captured["timeout"] == 20


def test_post_hook_reports_missing_environment(monkeypatch):
    monkeypatch.delenv("HOST_MONITOR_OPENCLAW_HOOK_URL", raising=False)
    monkeypatch.delenv("HOST_MONITOR_OPENCLAW_HOOK_TOKEN", raising=False)
    monkeypatch.delenv("HOST_MONITOR_OPENCLAW_DISCORD_CHANNEL", raising=False)

    with pytest.raises(RuntimeError, match="environment variables are missing"):
        post_openclaw_analysis_hook(_snapshot(), Config())


def _snapshot():
    return Snapshot(
        generated_at="2026-07-15T09:00:00+00:00",
        hostname="example-host",
        uptime_seconds=3661,
        load_average=(1.0, 0.5, 0.25),
        cpu={"average_percent": 10.0, "max_core_percent": 99.0, "core_count": 2},
        memory={"used_percent": 95.0},
        swap={"used_percent": 0.0},
        disks=[{"mount": "/", "used_percent": 42.0}],
        processes={"top_cpu": [], "top_memory": []},
        docker={"available": True, "containers": []},
        findings=[Finding("warning", "Memory usage is high")],
        snapshot_path="./var/snapshots/example.json",
    )
