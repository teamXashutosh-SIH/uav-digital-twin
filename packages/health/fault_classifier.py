from dataclasses import dataclass


@dataclass
class FaultDiagnosis:
    fault: str
    confidence: float
    severity: str
    evidence: list[str]
    recommendation: str


def classify_fault(
    health_status: str,
    oil_pressure_deviation: float,
    cht_deviation: float,
    egt_deviation: float,
    oil_temperature_deviation: float,
    vibration_deviation: float,
    rpm_deviation: float,
    egt_trend_direction: str,
    egt_trend_severity: str,
    is_transition: bool = False,
) -> FaultDiagnosis:
    """
    Diagnose likely engine faults from Digital Twin deviations.

    Development/demo diagnostic logic for synthetic AeroTwin data.

    Operating-condition transitions are explicitly considered so
    short-lived throttle/RPM transients are not automatically
    interpreted as component faults.

    This is NOT a validated aircraft-engine diagnostic system.
    """

    # =========================================================
    # TRANSIENT CONTEXT
    # =========================================================

    # A throttle/operating-point transition can temporarily create
    # large RPM and EGT deviations. We only classify it as a
    # transient when the other independent physical signals remain
    # reasonably normal.
    #
    # This prevents rapid-throttle missions from producing false
    # combustion/oil-pressure/sensor faults.

    transient_like = (
        is_transition
        and abs(rpm_deviation) > 200.0
        and abs(cht_deviation) < 25.0
        and abs(egt_deviation) < 80.0
        and abs(oil_temperature_deviation) < 15.0
        and oil_pressure_deviation > -60.0
        and vibration_deviation < 0.25
    )

    if transient_like:
        return FaultDiagnosis(
            fault="NO_SPECIFIC_FAULT",
            confidence=0.70,
            severity=health_status,
            evidence=[
                "Operating point is in transition",
                (
                    f"RPM deviation is "
                    f"{rpm_deviation:+.1f} RPM"
                ),
                "Independent thermal, lubrication and vibration signals remain near expected values",
            ],
            recommendation=(
                "Continue monitoring after the operating-point "
                "transition. Do not treat the transient response "
                "as a confirmed component fault."
            ),
        )

    # =========================================================
    # LOW OIL PRESSURE
    # =========================================================

    oil_score = 0.0
    oil_evidence = []

    if oil_pressure_deviation <= -120:
        oil_score += 0.70
        oil_evidence.append(
            f"Oil pressure deviation is "
            f"{oil_pressure_deviation:.1f} kPa"
        )

    elif oil_pressure_deviation <= -60:
        oil_score += 0.45
        oil_evidence.append(
            f"Oil pressure deviation is "
            f"{oil_pressure_deviation:.1f} kPa"
        )

    elif oil_pressure_deviation <= -30:
        oil_score += 0.25
        oil_evidence.append(
            f"Oil pressure deviation is "
            f"{oil_pressure_deviation:.1f} kPa"
        )

    # During a transition, require stronger evidence before
    # declaring a lubrication fault.
    oil_threshold = 0.60 if is_transition else 0.45

    if oil_score >= oil_threshold:

        confidence = min(
            0.99,
            0.75 + oil_score * 0.25,
        )

        return FaultDiagnosis(
            fault="LOW_OIL_PRESSURE",
            confidence=confidence,
            severity=health_status,
            evidence=oil_evidence,
            recommendation=(
                "Reduce engine load and inspect the "
                "lubrication system, oil level, oil pump "
                "and pressure regulation system."
            ),
        )

    # =========================================================
    # OVERHEATING / THERMAL ABNORMALITY
    # =========================================================

    thermal_score = 0.0
    thermal_evidence = []

    if egt_deviation >= 100:
        thermal_score += 0.35
        thermal_evidence.append(
            f"EGT deviation is "
            f"+{egt_deviation:.1f}°C"
        )

    elif egt_deviation >= 50:
        thermal_score += 0.20
        thermal_evidence.append(
            f"EGT deviation is "
            f"+{egt_deviation:.1f}°C"
        )

    if cht_deviation >= 50:
        thermal_score += 0.30
        thermal_evidence.append(
            f"CHT deviation is "
            f"+{cht_deviation:.1f}°C"
        )

    elif cht_deviation >= 25:
        thermal_score += 0.15
        thermal_evidence.append(
            f"CHT deviation is "
            f"+{cht_deviation:.1f}°C"
        )

    if oil_temperature_deviation >= 25:
        thermal_score += 0.20
        thermal_evidence.append(
            f"Oil temperature deviation is "
            f"+{oil_temperature_deviation:.1f}°C"
        )

    elif oil_temperature_deviation >= 10:
        thermal_score += 0.10
        thermal_evidence.append(
            f"Oil temperature deviation is "
            f"+{oil_temperature_deviation:.1f}°C"
        )

    if vibration_deviation >= 0.25:
        thermal_score += 0.10
        thermal_evidence.append(
            f"Vibration deviation is "
            f"+{vibration_deviation:.3f} g"
        )

    if egt_trend_direction == "RISING":
        thermal_score += 0.05
        thermal_evidence.append(
            "EGT trend is rising"
        )

    # Genuine multi-signal thermal abnormality is still allowed
    # during an operating transition.
    thermal_threshold = 0.70

    if thermal_score >= thermal_threshold:

        confidence = min(
            0.99,
            0.70 + thermal_score * 0.25,
        )

        return FaultDiagnosis(
            fault="OVERHEATING",
            confidence=confidence,
            severity=health_status,
            evidence=thermal_evidence,
            recommendation=(
                "Reduce engine load and inspect cooling, "
                "combustion and lubrication systems."
            ),
        )

    # =========================================================
    # ABNORMAL VIBRATION
    # =========================================================

    vibration_score = 0.0
    vibration_evidence = []

    if vibration_deviation >= 0.50:
        vibration_score = 0.90
        vibration_evidence.append(
            f"Vibration deviation is "
            f"+{vibration_deviation:.3f} g"
        )

    elif vibration_deviation >= 0.25:
        vibration_score = 0.65
        vibration_evidence.append(
            f"Vibration deviation is "
            f"+{vibration_deviation:.3f} g"
        )

    # Require stronger evidence during transition.
    vibration_threshold = 0.75 if is_transition else 0.60

    if vibration_score >= vibration_threshold:

        return FaultDiagnosis(
            fault="ABNORMAL_VIBRATION",
            confidence=min(
                0.95,
                0.70 + vibration_score * 0.25,
            ),
            severity=health_status,
            evidence=vibration_evidence,
            recommendation=(
                "Reduce engine load and inspect rotating "
                "components, mounting integrity and "
                "possible mechanical imbalance."
            ),
        )

    # =========================================================
    # COMBUSTION ANOMALY
    # =========================================================

    combustion_score = 0.0
    combustion_evidence = []

    egt_abnormal = abs(egt_deviation) >= 80.0
    rpm_abnormal = abs(rpm_deviation) >= 100.0

    if egt_abnormal:
        combustion_score += 0.45
        combustion_evidence.append(
            f"EGT deviation is "
            f"{egt_deviation:+.1f}°C"
        )

    if rpm_abnormal:
        combustion_score += 0.30
        combustion_evidence.append(
            f"RPM deviation is "
            f"{rpm_deviation:+.1f} RPM"
        )

    # EGT trend is useful supporting evidence, but it is NOT
    # considered an independent physical signal during a
    # throttle/operating-point transition.
    trend_support = (
        egt_trend_direction == "RISING"
        and egt_trend_severity in {
            "WARNING",
            "CRITICAL",
        }
    )

    if trend_support:
        combustion_score += 0.15
        combustion_evidence.append(
            "EGT trend is rising"
        )

    # Independent physical corroboration.
    #
    # These signals respond differently from RPM/EGT and are
    # therefore more useful for distinguishing a real combustion
    # problem from a normal operating-point transient.

    independent_corroboration = (
        abs(cht_deviation) >= 25.0
        or abs(oil_temperature_deviation) >= 15.0
        or vibration_deviation >= 0.25
    )

    if is_transition:

        # During an operating-point transition, RPM + EGT +
        # rising EGT trend are NOT sufficient by themselves.
        #
        # A real combustion anomaly must have an additional
        # independent physical signal.

        if (
            egt_abnormal
            and rpm_abnormal
            and independent_corroboration
        ):

            combustion_score += 0.20

            combustion_evidence.append(
                "Independent physical signal corroborates the abnormal response"
            )

            return FaultDiagnosis(
                fault="COMBUSTION_ANOMALY",
                confidence=min(
                    0.95,
                    0.70 + combustion_score * 0.25,
                ),
                severity=health_status,
                evidence=combustion_evidence,
                recommendation=(
                    "Inspect fuel delivery, injection timing, "
                    "air-fuel mixture and combustion stability."
                ),
            )

    else:

        if combustion_score >= 0.65:

            return FaultDiagnosis(
                fault="COMBUSTION_ANOMALY",
                confidence=min(
                    0.95,
                    0.70 + combustion_score * 0.25,
                ),
                severity=health_status,
                evidence=combustion_evidence,
                recommendation=(
                    "Inspect fuel delivery, injection timing, "
                    "air-fuel mixture and combustion stability."
                ),
            )
    

    # =========================================================
    # SENSOR DRIFT
    # =========================================================

    # Sensor drift should not be declared from a single
    # transition-related EGT deviation.
    if (
        not is_transition
        and abs(egt_deviation) >= 70
        and abs(cht_deviation) < 20
        and abs(oil_temperature_deviation) < 15
    ):

        return FaultDiagnosis(
            fault="SENSOR_DRIFT",
            confidence=0.75,
            severity=health_status,
            evidence=[
                (
                    f"EGT deviation is "
                    f"{egt_deviation:+.1f}°C"
                ),
                "Other thermal parameters remain near expected values",
            ],
            recommendation=(
                "Inspect the EGT sensor, wiring and "
                "sensor calibration before concluding "
                "that the engine itself is degraded."
            ),
        )

    # =========================================================
    # NO SPECIFIC FAULT
    # =========================================================

    evidence = []

    if is_transition:
        evidence.append(
            "Operating point is in transition"
        )

    if egt_trend_direction == "RISING":
        evidence.append(
            "EGT trend is rising"
        )

    return FaultDiagnosis(
        fault="NO_SPECIFIC_FAULT",
        confidence=0.50,
        severity=health_status,
        evidence=evidence,
        recommendation=(
            "Continue monitoring engine parameters "
            "and investigate developing anomalies."
        ),
    )