from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from services.simulator.engine_simulator import EngineSimulator
from packages.simulation.scenarios import (
    MissionScenario,
    MissionSegment,
)


@dataclass
class MissionStepResult:
    """
    Result produced by one simulation step.
    """

    mission_time_seconds: int

    segment_name: str

    telemetry: object


class MissionRunner:
    """
    Executes a MissionScenario using the existing
    EngineSimulator.

    The runner controls the mission timeline and passes
    operating conditions and fault conditions to the
    simulator.

    Development/demo mission execution model.
    """

    def __init__(
        self,
        simulator: EngineSimulator | None = None,
        engine_id: str = "ENGINE-001",
        mission_id: str = "MISSION-DEMO-001",
        vehicle_id: str = "UAV-DEMO-001",
    ):

        self.simulator = (
            simulator
            if simulator is not None
            else EngineSimulator()
        )

        self.mission_time_seconds = 0
        self.engine_id = engine_id
        self.mission_id = mission_id
        self.vehicle_id = vehicle_id
        self.started_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        """
        Reset the mission timeline and simulator state.
        """

        self.simulator = EngineSimulator()

        self.mission_time_seconds = 0
        self.started_at = datetime.now(timezone.utc)

    def run_segment(
        self,
        segment: MissionSegment,
    ) -> list[MissionStepResult]:
        """
        Execute one mission segment.

        Each second of the segment produces one telemetry
        sample.
        """

        results = []

        for _ in range(
            segment.duration_seconds
        ):

            telemetry = self.simulator.step(
                throttle_pct=segment.throttle_pct,
                altitude_m=segment.altitude_m,
                ambient_temperature_c=(
                    segment.ambient_temperature_c
                ),
                fault=segment.fault,
                fault_severity=(
                    segment.fault_severity
                ),
                engine_id=self.engine_id,
                mission_id=self.mission_id,
                vehicle_id=self.vehicle_id,
                timestamp=(
                    self.started_at
                    + timedelta(seconds=self.mission_time_seconds + 1)
                ),
            )

            self.mission_time_seconds += 1

            results.append(
                MissionStepResult(
                    mission_time_seconds=(
                        self.mission_time_seconds
                    ),
                    segment_name=segment.name,
                    telemetry=telemetry,
                )
            )

        return results

    def run_mission(
        self,
        scenario: MissionScenario,
    ) -> list[MissionStepResult]:
        """
        Execute all segments of a mission scenario.
        """

        self.reset()

        mission_results = []

        for segment in scenario.segments:

            segment_results = (
                self.run_segment(segment)
            )

            mission_results.extend(
                segment_results
            )

        return mission_results