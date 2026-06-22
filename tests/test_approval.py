from host_monitor.approval import render_subagent_prompt, should_prompt_for_subagent
from host_monitor.config import AlertingConfig, Config
from host_monitor.models import Finding, Snapshot


def test_subagent_prompt_is_disabled_by_default():
    snapshot = _snapshot([Finding("warning", "Memory usage is high")])

    assert should_prompt_for_subagent(snapshot, Config()) is False


def test_subagent_prompt_requires_matching_finding_level():
    snapshot = _snapshot([Finding("warning", "Memory usage is high")])
    config = Config(alerting=AlertingConfig(subagent_prompt_enabled=True, subagent_prompt_min_level="critical"))

    assert should_prompt_for_subagent(snapshot, config) is False


def test_subagent_prompt_payload_contains_model_select_and_buttons():
    snapshot = _snapshot([Finding("critical", "Single CPU core is saturated")])
    config = Config(
        alerting=AlertingConfig(
            subagent_prompt_enabled=True,
            subagent_prompt_default_model="default",
            subagent_prompt_models=["default", "openai/gpt-5.5"],
        )
    )

    payload = render_subagent_prompt(snapshot, config)

    assert "Single CPU core is saturated" in payload["content"]
    assert "expires:" in payload["content"]
    assert len(payload["components"]) == 2

    model_select = payload["components"][0]["components"][0]
    assert model_select["type"] == 3
    assert model_select["options"][0]["value"] == "default"
    assert model_select["options"][0]["default"] is True
    assert model_select["options"][1]["value"] == "openai/gpt-5.5"

    buttons = payload["components"][1]["components"]
    assert buttons[0]["label"] == "Kyllä"
    assert ":approve:" in buttons[0]["custom_id"]
    assert buttons[1]["label"] == "Ei"
    assert ":decline:" in buttons[1]["custom_id"]


def _snapshot(findings):
    return Snapshot(
        generated_at="2026-06-22T12:00:00+00:00",
        hostname="example-host",
        uptime_seconds=3661,
        load_average=(1.0, 0.5, 0.25),
        cpu={"average_percent": 10.0, "max_core_percent": 99.0, "core_count": 2},
        memory={"used_percent": 50.0},
        swap={"used_percent": 0.0},
        disks=[{"mount": "/", "used_percent": 42.0}],
        processes={"top_cpu": [], "top_memory": []},
        docker={"available": False, "reason": "docker CLI not found"},
        findings=findings,
        snapshot_path="./var/snapshots/example.json",
    )
