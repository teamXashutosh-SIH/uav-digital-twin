from packages.health.trend import TrendAnalyzer


def test_stable_engine_trend():

    analyzer = TrendAnalyzer()

    values = [
        690.0,
        690.5,
        689.8,
        690.2,
        690.1,
        690.4,
    ]

    result = analyzer.analyze(
        values=values,
        parameter="EGT",
        warning_slope=2.0,
        critical_slope=5.0,
    )

    print("\n--- STABLE TREND TEST ---")

    print(f"Parameter: {result.parameter}")
    print(f"Slope:     {result.slope:.3f}")
    print(f"Direction: {result.direction}")
    print(f"Severity:  {result.severity}")

    assert result.severity == "NORMAL"

    print("\nStable trend detection successful.")


def test_progressive_egt_rise():

    analyzer = TrendAnalyzer()

    values = [
        690.0,
        695.0,
        701.0,
        708.0,
        716.0,
        726.0,
    ]

    result = analyzer.analyze(
        values=values,
        parameter="EGT",
        warning_slope=2.0,
        critical_slope=5.0,
    )

    print("\n--- PROGRESSIVE EGT TEST ---")

    print(f"Parameter: {result.parameter}")
    print(f"Slope:     {result.slope:.3f}")
    print(f"Direction: {result.direction}")
    print(f"Severity:  {result.severity}")

    assert result.direction == "RISING"
    assert result.severity == "CRITICAL"

    print("\nProgressive EGT trend detected successfully.")