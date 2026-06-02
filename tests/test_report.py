from host_monitor.config import Config
from host_monitor.models import Finding, Snapshot
from host_monitor.report import render_discord_report


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

