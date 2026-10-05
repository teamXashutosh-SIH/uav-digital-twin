from pathlib import Path


def test_dashboard_declares_telemetry_stale_before_first_use():
    source = (
        Path(__file__).parents[1] / "apps" / "dashboard" / "src" / "App.jsx"
    ).read_text(encoding="utf-8")

    declaration = source.index("const telemetryStale =")
    first_reference = source.index("telemetryStale")

    assert first_reference == declaration + len("const ")
