from dataclasses import dataclass

from packages.digital_twin.core import DigitalTwinState
from packages.health.monitor import EngineHealthMonitor, HealthAssessment
from packages.health.trend import TrendAnalyzer, TrendResult


@dataclass
class IntegratedHealthAssessment:
    health: HealthAssessment
    egt_trend: TrendResult
    cht_trend: TrendResult


class EngineHealthEngine:
    """
    Integrates instantaneous Digital Twin health assessment
    with time-series thermal trend analysis.

    Development implementation for synthetic AeroTwin data.
    """

    def __init__(self):
        self.monitor = EngineHealthMonitor()
        self.trend_analyzer = TrendAnalyzer()

    def assess(
        self,
        twin_state: DigitalTwinState,
        egt_history: list[float],
        cht_history: list[float],
    ) -> IntegratedHealthAssessment:

        health = self.monitor.assess(twin_state)

        egt_trend = self.trend_analyzer.analyze(
            values=egt_history,
            parameter="EGT",
            warning_slope=2.0,
            critical_slope=5.0,
        )

        cht_trend = self.trend_analyzer.analyze(
            values=cht_history,
            parameter="CHT",
            warning_slope=1.0,
            critical_slope=3.0,
        )

        return IntegratedHealthAssessment(
            health=health,
            egt_trend=egt_trend,
            cht_trend=cht_trend,
        )