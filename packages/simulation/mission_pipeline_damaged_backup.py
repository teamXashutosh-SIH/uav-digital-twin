@staticmethod
def _apply_transient_context(
    health: IntegratedHealthAssessment,
    twin_state: DigitalTwinState,
    operating_condition: OperatingConditionStatus,
) -> IntegratedHealthAssessment:
    """
    Apply operating-condition context to the health assessment.

    The engine can temporarily deviate from the Digital Twin
    expectation during startup settling and operating-point
    transitions.

    During these periods, expected dynamic responses such as:
      - RPM lag
      - fuel-flow changes
      - oil-temperature lag

    should not by themselves reduce overall engine health.

    Independent evidence of a genuine anomaly is still retained:
      - elevated CHT
      - elevated EGT
      - low oil pressure
      - excessive vibration

    Parameter-level statuses are preserved for diagnostics.
    Only the aggregate health score/status is adjusted when the
    deviation pattern is consistent with a normal transient.
    """

    if not operating_condition.is_transition:
        return health

    deviation = twin_state.deviation
    original_health = health.health

    # ---------------------------------------------------------
    # 1. Independent fault indicators
    # ---------------------------------------------------------
    #
    # These signals should remain important even during a
    # throttle/startup transition.

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

    # ---------------------------------------------------------
    # 2. Normal transient signature
    # ---------------------------------------------------------
    #
    # Fuel flow and oil temperature can change substantially
    # immediately after a throttle change. RPM can also lag
    # the new operating point.

    transient_response = (
        abs(deviation.rpm) < 500.0
        and abs(deviation.fuel_flow_gph) < 8.0
        and abs(deviation.oil_temperature_c) < 20.0
        and abs(deviation.cht_c) < 25.0
        and abs(deviation.egt_c) < 80.0
        and deviation.oil_pressure_kpa > -60.0
        and deviation.vibration_g < 0.25
    )

    # ---------------------------------------------------------
    # 3. Only suppress aggregate penalty for a benign transient
    # ---------------------------------------------------------

    if not transient_response or independent_fault_evidence:
        return health

    # Keep the individual parameter statuses untouched.
    #
    # We only prevent transient-only fuel-flow / oil-temperature
    # / RPM effects from making the complete engine appear faulty.

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
        (
            critical_count * 0.35
            + warning_count * 0.10
        ),
    )

    health_score = max(
        0.0,
        100.0 * (1.0 - anomaly_score),
    )

    if critical_count > 0:
        new_status = "CRITICAL"
    elif warning_count > 0:
        new_status = "WARNING"
    else:
        new_status = "HEALTHY"

    from dataclasses import replace

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