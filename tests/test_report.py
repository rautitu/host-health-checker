from host_monitor.config import Config
from host_monitor.models import Finding, Snapshot
from host_monitor.report import post_discord_report, render_discord_report


def test_report_renders_findings_and_snapshot_path():
    snapshot = Snapshot(
        generated_at="2026-06-02T15:00:00+00:00",
        hostname="example-host",
        uptime_seconds=3661,
        load_average=(1.0, 0.5, 0.25),
        cpu={"average_percent": 10.0, "max_core_percent": 99.0, "core_count": 2},
        memory={"used_percent": 50.0},
        swap={"used_percent": 0.0},
        disks=[{"mount": "/", "used_percent": 42.0}],
        processes={"top_cpu": [], "top_memory": []},
        docker={"available": False, "reason": "docker CLI not found"},
        findings=[Finding("critical", "Single CPU core is saturated at 99.0%")],
        snapshot_path="./var/snapshots/example.json",
    )

    report = render_discord_report(snapshot, Config())

    assert "example-host" in report
    assert "Single CPU core is saturated" in report
    assert "./var/snapshots/example.json" in report


def test_report_renders_process_command_details():
    snapshot = Snapshot(
        generated_at="2026-06-02T15:00:00+00:00",
        hostname="example-host",
        uptime_seconds=3661,
        load_average=(1.0, 0.5, 0.25),
        cpu={"average_percent": 10.0, "max_core_percent": 20.0, "core_count": 2},
        memory={"used_percent": 50.0},
        swap={"used_percent": 0.0},
        disks=[{"mount": "/", "used_percent": 42.0}],
        processes={
            "top_cpu": [
                {
                    "pid": 123,
                    "name": "node",
                    "username": "app",
                    "cpu_percent": 12.3,
                    "memory_percent": 4.5,
                    "cmdline": "node server.js",
                }
            ],
            "top_memory": [],
        },
        docker={"available": False, "reason": "docker CLI not found"},
        findings=[],
        snapshot_path="./var/snapshots/example.json",
    )

    report = render_discord_report(snapshot, Config())

    assert "`app` node - node server.js" in report


def test_post_discord_report_sets_user_agent(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("host_monitor.report.urllib.request.urlopen", fake_urlopen)

    post_discord_report("hello", "https://discord.com/api/webhooks/example/token")

    assert captured["timeout"] == 20
    assert captured["request"].headers["User-agent"] == "host-health-checker/0.1"
