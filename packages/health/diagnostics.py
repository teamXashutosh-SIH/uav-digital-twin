from dataclasses import dataclass


@dataclass
class DiagnosticResult:
    status: str
    confidence: float
    primary_signal: str
    message: str


def fuse_diagnostics(
    health_status: str,
    health_score: float,
    ml_is_anomaly: bool,
    ml_score: float,
    egt_trend_severity: str,
    cht_trend_severity: str,
) -> DiagnosticResult:

    critical_trend = (
        egt_trend_severity == "CRITICAL"
        or cht_trend_severity == "CRITICAL"
    )

    warning_trend = (
        egt_trend_severity == "WARNING"
        or cht_trend_severity == "WARNING"
    )

    # Rule/physics health has priority over an isolated ML signal.
    if health_status == "CRITICAL":
        return DiagnosticResult(
            status="CRITICAL",
            confidence=0.95,
            primary_signal="PHYSICS_HEALTH",
            message="Critical engine condition detected.",
        )

    if critical_trend:
        return DiagnosticResult(
            status="CRITICAL",
            confidence=0.90,
            primary_signal="TREND",
            message="Critical thermal trend detected.",
        )

    if health_status == "WARNING":
        return DiagnosticResult(
            status="WARNING",
            confidence=0.85,
            primary_signal="PHYSICS_HEALTH",
            message="Engine parameters require attention.",
        )

    if warning_trend:
        return DiagnosticResult(
            status="WARNING",
            confidence=0.75,
            primary_signal="TREND",
            message="Developing thermal trend detected.",
        )

    if ml_is_anomaly:
        return DiagnosticResult(
            status="ANOMALY_SUSPECTED",
            confidence=min(0.70, 0.40 + ml_score * 0.30),
            primary_signal="ML",
            message=(
                "ML detected an anomalous pattern, "
                "but physics-based health remains normal."
            ),
        )

    return DiagnosticResult(
        status="HEALTHY",
        confidence=0.95,
        primary_signal="PHYSICS_HEALTH",
        message="Engine operating within expected conditions.",
    )