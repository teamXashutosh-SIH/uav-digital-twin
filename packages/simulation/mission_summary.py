from dataclasses import dataclass

from packages.simulation.mission_pipeline import (
    MissionAnalysisResult,
)


@dataclass
class MissionSummary:
    """
    Mission-level summary generated from the complete
    Digital Twin mission analysis.

    Development/demo implementation.
    """

    scenario_id: str
    scenario_name: str

    total_samples: int
    duration_seconds: int

    final_health_status: str
    final_health_score: float

    peak_health_score: float
    minimum_health_score: float

    final_degradation_index: float
    maximum_degradation_index: float
    degradation_trend: str

    final_rul_hours: float
    final_rul_confidence: float
    final_rul_status: str

    primary_fault: str
    fault_confidence: float
    fault_severity: str

    segments: list[str]

    warning_samples: int
    critical_samples: int
    anomaly_samples: int


def build_mission_summary(
    mission: MissionAnalysisResult,
) -> MissionSummary:
    """
    Convert detailed mission analysis results into
    one mission-level summary.
    """

    if not mission.steps:
        raise ValueError(
            "Cannot create a summary from an empty mission."
        )

    steps = mission.steps

    health_scores = [
        step.health.health.health_score
        for step in steps
    ]

    health_statuses = [
        step.health.health.status
        for step in steps
    ]

    degradation_values = [
        step.degradation.degradation_index
        for step in steps
    ]

    segments = []

    for step in steps:
        if step.segment_name not in segments:
            segments.append(
                step.segment_name
            )

    warning_samples = sum(
        1
        for status in health_statuses
        if status == "WARNING"
    )

    critical_samples = sum(
        1
        for status in health_statuses
        if status == "CRITICAL"
    )

    anomaly_samples = sum(
        1
        for step in steps
        if step.fault.fault
        != "NO_SPECIFIC_FAULT"
    )

    # Determine the most frequently diagnosed
    # specific fault during the mission.
    fault_counts = {}

    for step in steps:

        fault = step.fault.fault

        if fault == "NO_SPECIFIC_FAULT":
            continue

        fault_counts[fault] = (
            fault_counts.get(fault, 0)
            + 1
        )

    if fault_counts:

        primary_fault = max(
            fault_counts,
            key=fault_counts.get,
        )

        fault_steps = [
            step
            for step in steps
            if step.fault.fault
            == primary_fault
        ]

        fault_confidence = max(
            step.fault.confidence
            for step in fault_steps
        )

        fault_severity = max(
            (
                step.fault.severity
                for step in fault_steps
            ),
            key=lambda value: {
                "HEALTHY": 0,
                "WARNING": 1,
                "CRITICAL": 2,
            }.get(value, 0),
        )

    else:

        primary_fault = (
            "NO_SPECIFIC_FAULT"
        )

        fault_confidence = 0.0

        fault_severity = (
            "HEALTHY"
        )

    final_step = steps[-1]

    return MissionSummary(
        scenario_id=mission.scenario_id,

        scenario_name=mission.scenario_name,

        total_samples=mission.total_samples,

        duration_seconds=(
            mission.mission_duration_seconds
        ),

        final_health_status=(
            final_step.health.health.status
        ),

        final_health_score=float(
            final_step.health.health.health_score
        ),

        peak_health_score=float(
            max(health_scores)
        ),

        minimum_health_score=float(
            min(health_scores)
        ),

        final_degradation_index=float(
            final_step.degradation.degradation_index
        ),

        maximum_degradation_index=float(
            max(degradation_values)
        ),

        degradation_trend=(
            final_step.degradation.trend
        ),

        final_rul_hours=float(
            final_step.rul.rul_hours
        ),

        final_rul_confidence=float(
            final_step.rul.confidence
        ),

        final_rul_status=(
            final_step.rul.status
        ),

        primary_fault=primary_fault,

        fault_confidence=float(
            fault_confidence
        ),

        fault_severity=fault_severity,

        segments=segments,

        warning_samples=(
            warning_samples
        ),

        critical_samples=(
            critical_samples
        ),

        anomaly_samples=(
            anomaly_samples
        ),
    )


def summary_to_dict(
    summary: MissionSummary,
) -> dict:
    """
    Convert MissionSummary into a JSON-friendly
    dictionary for future API/dashboard use.
    """

    return {
        "scenario_id": summary.scenario_id,
        "scenario_name": summary.scenario_name,

        "total_samples": summary.total_samples,
        "duration_seconds": summary.duration_seconds,

        "health": {
            "final_status": (
                summary.final_health_status
            ),
            "final_score": (
                summary.final_health_score
            ),
            "peak_score": (
                summary.peak_health_score
            ),
            "minimum_score": (
                summary.minimum_health_score
            ),
        },

        "degradation": {
            "final_index": (
                summary.final_degradation_index
            ),
            "maximum_index": (
                summary.maximum_degradation_index
            ),
            "trend": (
                summary.degradation_trend
            ),
        },

        "rul": {
            "final_hours": (
                summary.final_rul_hours
            ),
            "confidence": (
                summary.final_rul_confidence
            ),
            "status": (
                summary.final_rul_status
            ),
        },

        "fault": {
            "primary_fault": (
                summary.primary_fault
            ),
            "confidence": (
                summary.fault_confidence
            ),
            "severity": (
                summary.fault_severity
            ),
        },

        "mission": {
            "segments": summary.segments,
            "warning_samples": (
                summary.warning_samples
            ),
            "critical_samples": (
                summary.critical_samples
            ),
            "anomaly_samples": (
                summary.anomaly_samples
            ),
        },
    }