from dataclasses import dataclass

from packages.digital_twin.core import (
    EngineDigitalTwin,
    DigitalTwinState,
)

from packages.health.engine_health import (
    EngineHealthEngine,
    IntegratedHealthAssessment,
)
from packages.health.monitor import EngineHealthMonitor

from packages.digital_twin.state_estimator import (
    EngineStateEstimator,
    EngineState,
)

from packages.health.degradation import (
    EngineDegradationTracker,
    DegradationResult,
)

from packages.health.rul import (
    EngineRULEstimator,
    RULResult,
)

from packages.health.fault_classifier import (
    classify_fault,
    FaultDiagnosis,
)

from packages.simulation.mission_runner import (
    MissionRunner,
    MissionStepResult,
)

from packages.simulation.scenarios import (
    MissionScenario,
)

from packages.simulation.operating_condition import (
    OperatingConditionTracker,
    OperatingConditionStatus,
)


@dataclass
class MissionAnalysisStep:
    """
    Complete Digital Twin analysis result for one
    mission telemetry sample.
    """

    mission_time_seconds: int
    segment_name: str

    twin_state: DigitalTwinState

    health: IntegratedHealthAssessment

    engine_state: EngineState

    degradation: DegradationResult

    rul: RULResult

    fault: FaultDiagnosis

    operating_condition: OperatingConditionStatus


@dataclass
class MissionAnalysisResult:
    """
    Complete analysis result for one simulated mission.
    """

    scenario_id: str
    scenario_name: str

    total_samples: int
    mission_duration_seconds: int

    steps: list[MissionAnalysisStep]


class MissionAnalysisPipeline:
    """
    Runs a complete mission through the AeroTwin
    Digital Twin analysis pipeline.

    Development/demo implementation.
    """

    def __init__(
        self,
        engine_id: str = "ENGINE-001",
        mission_id: str = "MISSION-DEMO-001",
        vehicle_id: str = "UAV-DEMO-001",
    ):

        self.mission_runner = MissionRunner(
            engine_id=engine_id,
            mission_id=mission_id,
            vehicle_id=vehicle_id,
        )

        self.digital_twin = (
            EngineDigitalTwin()
        )

        self.health_engine = (
            EngineHealthEngine()
        )

        self.state_estimator = (
            EngineStateEstimator()
        )

        self.degradation_tracker = (
            EngineDegradationTracker()
        )

        self.rul_estimator = (
            EngineRULEstimator()
        )

        self.operating_condition_tracker = (
            OperatingConditionTracker()
        )

        self.egt_history = []
        self.cht_history = []

    def reset(self) -> None:
        """
        Reset all mission-analysis state.
        """

        self.mission_runner.reset()
        self.digital_twin.reset()

        self.degradation_tracker = (
            EngineDegradationTracker()
        )

        self.rul_estimator = (
            EngineRULEstimator()
        )

        self.operating_condition_tracker.reset()

        self.egt_history = []
        self.cht_history = []

    @staticmethod
    def _apply_transient_context(
        health: IntegratedHealthAssessment,
        twin_state: DigitalTwinState,
        operating_condition: OperatingConditionStatus,
        is_initialization: bool = False,
    ) -> IntegratedHealthAssessment:
        """
        Apply operating-condition context to aggregate health.

        The first telemetry sample can contain a Digital Twin
        initialization mismatch because the simulator starts from
        an initial physical state while the Digital Twin starts from
        the expected operating point.

        Such an initialization mismatch must not be interpreted
        as an engine fault when independent fault evidence is absent.

        Thresholds are development/demo assumptions for synthetic
        data and are not validated aircraft-engine limits.
        """

        from dataclasses import replace

        deviation = twin_state.deviation
        original_health = health.health

        # ---------------------------------------------------------
        # 1. Digital Twin initialization context
        # ---------------------------------------------------------
        #
        # At the first sample, the observed engine state and the
        # Digital Twin expected state may legitimately differ.
        #
        # We only suppress the aggregate health penalty when the
        # independent engine-health indicators remain normal.
        #
        # This prevents startup initialization from becoming a
        # false CRITICAL engine condition.
        # ---------------------------------------------------------

        if is_initialization:

            independent_fault_evidence = (
                original_health.oil_pressure_status == "CRITICAL"
                or original_health.oil_temperature_status == "CRITICAL"
                or original_health.vibration_status == "CRITICAL"
                or original_health.fuel_flow_status == "CRITICAL"
            )

            if not independent_fault_evidence:

                updated_health = replace(
                    original_health,
                    status="HEALTHY",
                    health_score=100.0,
                    anomaly_score=0.0,
                )

                return replace(
                    health,
                    health=updated_health,
                )

        # ---------------------------------------------------------
        # 2. Normal operation
        # ---------------------------------------------------------

        if not operating_condition.is_transition:
            return health

        # ---------------------------------------------------------
        # 3. Rapid throttle / operating transition
        # ---------------------------------------------------------

        thermal_abnormal = (
            deviation.cht_c >= 25.0
            or deviation.egt_c >= 80.0
        )

        lubrication_abnormal = (
            deviation.oil_pressure_kpa <= -60.0
        )

        vibration_abnormal = (
            deviation.vibration_g >= 0.25
        )

        independent_fault_evidence = (
            thermal_abnormal
            or lubrication_abnormal
            or vibration_abnormal
        )

        transient_response = (
            abs(deviation.rpm) < 500.0
            and abs(deviation.fuel_flow_gph) < 8.0
            and abs(deviation.oil_temperature_c) < 20.0
            and abs(deviation.cht_c) < 25.0
            and abs(deviation.egt_c) < 80.0
            and deviation.oil_pressure_kpa > -60.0
            and deviation.vibration_g < 0.25
        )

        if not transient_response or independent_fault_evidence:
            return health

        # Ignore transient RPM-related health penalties while
        # retaining genuine thermal/lubrication/vibration evidence.
        non_transient_statuses = [
            original_health.cht_status,
            original_health.egt_status,
            original_health.oil_pressure_status,
            original_health.vibration_status,
        ]

        critical_count = non_transient_statuses.count("CRITICAL")
        warning_count = non_transient_statuses.count("WARNING")

        anomaly_score = min(
            1.0,
            critical_count * 0.35
            + warning_count * 0.10,
        )

        health_score = EngineHealthMonitor.health_score_for(
            critical_count=critical_count,
            warning_count=warning_count,
        )

        if critical_count > 0:
            new_status = "CRITICAL"
        elif warning_count > 0:
            new_status = "WARNING"
        else:
            new_status = "HEALTHY"

        updated_health = replace(
            original_health,
            status=new_status,
            health_score=health_score,
            anomaly_score=anomaly_score,
        )

        return replace(
            health,
            health=updated_health,
        )

    def _analyze_step(
        self,
        step: MissionStepResult,
    ) -> MissionAnalysisStep:

        telemetry = step.telemetry

        # -------------------------------------------------
        # 1. Operating-condition tracking
        # -------------------------------------------------

        operating_condition = (
            self.operating_condition_tracker.update(
                throttle_pct=(
                    telemetry.throttle_pct
                ),
                altitude_m=(
                    telemetry.altitude_m
                ),
                ambient_temperature_c=(
                    telemetry.ambient_temperature_c
                ),
            )
        )

        # -------------------------------------------------
        # 2. Digital Twin
        # -------------------------------------------------

        twin_state = (
            self.digital_twin.compare(
                telemetry
            )
        )

        # -------------------------------------------------
        # 3. Thermal history
        # -------------------------------------------------

        self.egt_history.append(
            telemetry.egt_c
        )

        self.cht_history.append(
            telemetry.cht_c
        )

        self.egt_history = (
            self.egt_history[-60:]
        )

        self.cht_history = (
            self.cht_history[-60:]
        )

        # -------------------------------------------------
        # 4. Health Engine
        # -------------------------------------------------

        health = self.health_engine.assess(
            twin_state=twin_state,
            egt_history=self.egt_history,
            cht_history=self.cht_history,
        )

        # -------------------------------------------------
        # 5. Apply operating-condition context
        # -------------------------------------------------

        health = self._apply_transient_context(
            health=health,
            twin_state=twin_state,
            operating_condition=operating_condition,
            is_initialization=(len(self.egt_history) == 1),
    )

        # -------------------------------------------------
        # 6. Engine State
        # -------------------------------------------------

        engine_state = (
            self.state_estimator.estimate(
                assessment=health,
                twin_state=twin_state,
            )
        )

        # -------------------------------------------------
        # 7. Degradation
        # -------------------------------------------------

        degradation = (
            self.degradation_tracker.update(
                twin_state=twin_state,
                is_transition=operating_condition.is_transition,
            )
        )

        # -------------------------------------------------
        # 8. RUL
        # -------------------------------------------------

        rul = self.rul_estimator.update(
            degradation.degradation_index
        )

        # -------------------------------------------------
        # 9. Fault diagnosis
        # -------------------------------------------------

        fault = classify_fault(
            health_status=(
                health.health.status
            ),

            oil_pressure_deviation=(
                twin_state.deviation
                .oil_pressure_kpa
            ),

            cht_deviation=(
                twin_state.deviation
                .cht_c
            ),

            egt_deviation=(
                twin_state.deviation
                .egt_c
            ),

            oil_temperature_deviation=(
                twin_state.deviation
                .oil_temperature_c
            ),

            vibration_deviation=(
                twin_state.deviation
                .vibration_g
            ),

            rpm_deviation=(
                twin_state.deviation
                .rpm
            ),

            egt_trend_direction=(
                health.egt_trend.direction
            ),

            egt_trend_severity=(
                health.egt_trend.severity
            ),

            is_transition=(
                operating_condition.is_transition
            ),
        )

        return MissionAnalysisStep(
            mission_time_seconds=(
                step.mission_time_seconds
            ),

            segment_name=(
                step.segment_name
            ),

            twin_state=twin_state,

            health=health,

            engine_state=engine_state,

            degradation=degradation,

            rul=rul,

            fault=fault,

            operating_condition=(
                operating_condition
            ),
        )

    def run(
        self,
        scenario: MissionScenario,
    ) -> MissionAnalysisResult:
        """
        Execute and analyze a complete mission.
        """

        self.reset()

        mission_steps = (
            self.mission_runner.run_mission(
                scenario
            )
        )

        analyzed_steps = []

        for step in mission_steps:

            analyzed_steps.append(
                self._analyze_step(step)
            )

        return MissionAnalysisResult(
            scenario_id=(
                scenario.scenario_id
            ),

            scenario_name=(
                scenario.name
            ),

            total_samples=len(
                analyzed_steps
            ),

            mission_duration_seconds=(
                analyzed_steps[-1]
                .mission_time_seconds
                if analyzed_steps
                else 0
            ),

            steps=analyzed_steps,
        )