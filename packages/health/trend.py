from dataclasses import dataclass


@dataclass
class TrendResult:
    parameter: str
    slope: float
    direction: str
    severity: str


class TrendAnalyzer:
    """
    Time-series trend analyzer for AeroTwin.

    Uses a simple linear trend over a recent window.

    This is a development implementation for synthetic data.

    For thermal-health/degradation monitoring, a rising trend is
    treated as the concerning direction. A falling temperature trend
    is retained as information but is not automatically classified
    as a thermal degradation event.

    This prevents normal cooldown or throttle-reduction behaviour
    from being interpreted as thermal degradation.
    """

    def analyze(
        self,
        values: list[float],
        parameter: str,
        warning_slope: float,
        critical_slope: float,
    ) -> TrendResult:

        # ---------------------------------------------------------
        # Not enough data
        # ---------------------------------------------------------
        if len(values) < 2:
            return TrendResult(
                parameter=parameter,
                slope=0.0,
                direction="INSUFFICIENT_DATA",
                severity="NORMAL",
            )

        n = len(values)

        # ---------------------------------------------------------
        # Linear regression slope
        # ---------------------------------------------------------
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum(
            (i - x_mean) * (value - y_mean)
            for i, value in enumerate(values)
        )

        denominator = sum(
            (i - x_mean) ** 2
            for i in range(n)
        )

        slope = numerator / denominator

        # ---------------------------------------------------------
        # Direction
        # ---------------------------------------------------------
        if slope > 0:
            direction = "RISING"
        elif slope < 0:
            direction = "FALLING"
        else:
            direction = "STABLE"

        # ---------------------------------------------------------
        # Severity
        # ---------------------------------------------------------
        #
        # For thermal degradation:
        #
        #       RISING + large slope
        #               ↓
        #          WARNING/CRITICAL
        #
        #       FALLING
        #               ↓
        #          NORMAL
        #
        # A falling EGT/CHT is commonly associated with cooldown or
        # reduced engine load and therefore should not by itself
        # indicate degradation.
        # ---------------------------------------------------------

        if slope >= critical_slope:
            severity = "CRITICAL"

        elif slope >= warning_slope:
            severity = "WARNING"

        else:
            severity = "NORMAL"

        return TrendResult(
            parameter=parameter,
            slope=slope,
            direction=direction,
            severity=severity,
        )