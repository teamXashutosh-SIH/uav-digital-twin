from datetime import datetime, timezone
import queue
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
import services.simulator.mqtt_publisher as mqtt_publisher
from sqlalchemy.sql import visitors
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql import operators

from packages.simulation.mission_pipeline import MissionAnalysisPipeline
from packages.simulation.scenarios import SCENARIOS, MissionScenario, MissionSegment
from services.api import main as api
from services.api.db.models import (
    EngineFaultEventModel,
    EngineMissionModel,
    EngineTelemetryModel,
)
from services.api.schemas import FaultInjectionRequest, MissionEndRequest, MissionStartRequest
from services.api.schemas import MissionScenarioRequest
from services.api.simulation.controller import LiveSimulationController


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self):
        self.events = []
        self.telemetry = []
        self.missions = []

    def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        rows = {
            EngineFaultEventModel: self.events,
            EngineMissionModel: self.missions,
            EngineTelemetryModel: self.telemetry,
        }[entity]
        filters = {}
        if statement.whereclause is not None:
            for clause in visitors.iterate(statement.whereclause):
                if (
                    isinstance(clause, BinaryExpression)
                    and hasattr(clause.left, "key")
                    and hasattr(clause.right, "value")
                ):
                    filters[clause.left.key] = clause.right.value

        rows = [
            row
            for row in rows
            if all(getattr(row, key) == value for key, value in filters.items())
        ]

        for ordering in reversed(statement._order_by_clauses):
            descending = getattr(ordering, "modifier", None) is operators.desc_op
            column = getattr(ordering, "element", ordering)
            key = column.key
            rows = sorted(
                rows,
                key=lambda row: getattr(row, key) or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                reverse=descending,
            )

        if statement._limit_clause is not None:
            rows = rows[: statement._limit_clause.value]
        expression = statement.column_descriptions[0]["expr"]
        if not isinstance(expression, type) and hasattr(expression, "key"):
            rows = [getattr(row, expression.key) for row in rows]
        return FakeResult(rows)

    def add(self, event):
        collection = (
            self.events
            if isinstance(event, EngineFaultEventModel)
            else self.missions
            if isinstance(event, EngineMissionModel)
            else self.telemetry
        )
        event.id = len(collection) + 1
        collection.append(event)

    def add_all(self, records):
        for record in records:
            self.add(record)

    def commit(self):
        pass


@pytest.fixture
def fault_api(monkeypatch):
    db = FakeSession()
    controller = LiveSimulationController()
    monkeypatch.setattr(
        controller,
        "_publish_command",
        lambda engine_id, payload, vehicle_id="UAV-DEMO-001": {
            "topic": f"test/{engine_id}/control",
            "command": payload,
        },
    )
    monkeypatch.setattr(api, "inject_fault", controller.inject_fault)
    monkeypatch.setattr(api, "clear_fault", controller.clear_fault)
    monkeypatch.setattr(api, "get_fault_state", controller.get_state)
    return db, controller


def inject(db, fault="overheating", severity=0.8, engine_id="ENGINE-001"):
    return api.simulation_fault(
        FaultInjectionRequest(
            fault=fault,
            severity=severity,
            engine_id=engine_id,
        ),
        db,
    )


def test_fault_injection_defaults_to_engine_001(fault_api):
    db, _ = fault_api
    result = inject(db)

    assert result["engine_id"] == "ENGINE-001"
    state = api.simulation_fault_state(engine_id="ENGINE-001")
    assert state["active"] is True
    assert state["fault"] == "overheating"
    assert db.events[0].engine_id == "ENGINE-001"
    assert db.events[0].status == "ACTIVE"


def test_fault_injection_accepts_custom_engine_id(fault_api):
    db, controller = fault_api
    result = inject(db, engine_id="ENGINE-002")

    assert result["engine_id"] == "ENGINE-002"
    assert controller.get_state("ENGINE-002")["active"] is True
    assert db.events[0].engine_id == "ENGINE-002"


def test_same_active_fault_does_not_create_duplicate_event(fault_api):
    db, _ = fault_api
    inject(db)
    second = inject(db, severity=0.9)

    assert second["status"] == "FAULT_ALREADY_ACTIVE"
    assert len(db.events) == 1
    assert db.events[0].severity == 0.9


def test_clear_marks_event_cleared_and_preserves_history(fault_api):
    db, _ = fault_api
    inject(db)

    result = api.simulation_clear(engine_id="ENGINE-001", db=db)

    assert result["status"] == "FAULT_CLEARED"
    assert len(db.events) == 1
    assert db.events[0].status == "CLEARED"
    assert db.events[0].cleared_at is not None


def test_switching_fault_closes_previous_and_adds_active_event(fault_api):
    db, _ = fault_api
    inject(db, fault="overheating")
    inject(db, fault="low_oil_pressure")

    assert len(db.events) == 2
    assert db.events[0].status == "CLEARED"
    assert db.events[0].cleared_at == db.events[1].started_at
    assert db.events[1].fault == "low_oil_pressure"
    assert db.events[1].status == "ACTIVE"


def test_fault_events_can_be_filtered_by_engine_id(fault_api):
    db, _ = fault_api
    inject(db, engine_id="ENGINE-001")
    inject(db, engine_id="ENGINE-002")

    events = api.simulation_fault_events(
        engine_id="ENGINE-002",
        limit=50,
        db=db,
    )

    assert len(events) == 1
    assert events[0]["engine_id"] == "ENGINE-002"


def test_engine_discovery_includes_fault_only_engine_ids(fault_api):
    db, _ = fault_api
    db.telemetry.append(
        make_telemetry(
            1,
            datetime(2026, 10, 4, tzinfo=timezone.utc),
            engine_id="ENGINE-001",
        )
    )
    db.missions.append(
        EngineMissionModel(
            id=1,
            mission_id="MISSION-2",
            engine_id="ENGINE-002",
            vehicle_id="UAV-DEMO-001",
            status="COMPLETED",
            started_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
            ended_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
            created_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        )
    )
    db.events.append(make_fault_event(1, engine_id="ENGINE-003"))
    db.events.append(make_fault_event(2, engine_id="ENGINE-001"))

    result = api.list_engines(db=db)

    assert result["engine_ids"] == [
        "ENGINE-001",
        "ENGINE-002",
        "ENGINE-003",
    ]


def test_overheating_health_score_stays_positive_when_critical():
    scenario = MissionScenario(
        scenario_id="overheating_health_score",
        name="Overheating Health Score",
        description="Verify active overheating retains a positive health score.",
        segments=(
            MissionSegment("CRUISE", 20, 60.0, 0.0, 25.0),
            MissionSegment(
                "OVERHEATING",
                20,
                75.0,
                0.0,
                25.0,
                "overheating",
                0.8,
            ),
        ),
    )

    result = MissionAnalysisPipeline().run(scenario)
    critical_assessments = [
        step.health.health
        for step in result.steps
        if step.health.health.status == "CRITICAL"
    ]

    assert critical_assessments
    assert all(assessment.health_score > 0 for assessment in critical_assessments)


def make_fault_event(
    event_id,
    *,
    engine_id="ENGINE-001",
    fault="overheating",
    status="ACTIVE",
    created_at=None,
):
    created_at = created_at or datetime.now(timezone.utc)
    return EngineFaultEventModel(
        id=event_id,
        engine_id=engine_id,
        vehicle_id="UAV-DEMO-001",
        mission_id="MISSION-DEMO-001",
        fault=fault,
        severity=0.8,
        status=status,
        started_at=created_at,
        cleared_at=created_at if status == "CLEARED" else None,
        created_at=created_at,
        event_metadata={"evidence": ["thermal deviation elevated"]},
    )


def test_notifications_return_empty_list(fault_api):
    db, _ = fault_api

    assert api.notifications(limit=50, db=db) == []


def test_notifications_include_active_event(fault_api):
    db, _ = fault_api
    db.events.append(make_fault_event(1))

    notifications = api.notifications(limit=50, db=db)

    assert len(notifications) == 1
    assert notifications[0].fault == "overheating"
    assert notifications[0].status == "ACTIVE"
    assert notifications[0].metadata == {
        "evidence": ["thermal deviation elevated"]
    }


def test_notifications_include_cleared_historical_event(fault_api):
    db, _ = fault_api
    db.events.append(make_fault_event(1, status="CLEARED"))

    notifications = api.notifications(limit=50, db=db)

    assert len(notifications) == 1
    assert notifications[0].status == "CLEARED"
    assert notifications[0].cleared_at is not None


def test_notifications_filter_by_engine_id(fault_api):
    db, _ = fault_api
    db.events.extend(
        [
            make_fault_event(1, engine_id="ENGINE-001"),
            make_fault_event(2, engine_id="ENGINE-002"),
        ]
    )

    notifications = api.notifications(
        engine_id="ENGINE-002",
        limit=50,
        db=db,
    )

    assert [event.engine_id for event in notifications] == ["ENGINE-002"]


def test_notifications_can_be_limited_to_active_events(fault_api):
    db, _ = fault_api
    db.events.extend(
        [
            make_fault_event(1, status="ACTIVE"),
            make_fault_event(2, fault="sensor_drift", status="CLEARED"),
        ]
    )

    notifications = api.notifications(
        active_only=True,
        limit=50,
        db=db,
    )

    assert [event.status for event in notifications] == ["ACTIVE"]


def test_notifications_are_ordered_newest_first(fault_api):
    db, _ = fault_api
    earlier = datetime(2026, 10, 4, tzinfo=timezone.utc)
    later = datetime(2026, 10, 5, tzinfo=timezone.utc)
    db.events.extend(
        [
            make_fault_event(1, created_at=earlier),
            make_fault_event(2, fault="sensor_drift", created_at=later),
        ]
    )

    notifications = api.notifications(limit=50, db=db)

    assert [event.id for event in notifications] == [2, 1]


@pytest.fixture
def mission_api(monkeypatch):
    db = FakeSession()
    monkeypatch.setattr(
        api,
        "set_mission_context",
        lambda **kwargs: {"status": "COMMAND_SENT", **kwargs},
    )
    monkeypatch.setattr(
        api,
        "end_mission_context",
        lambda **kwargs: {"status": "COMMAND_SENT", **kwargs},
    )
    return db


def start_mission(db, mission_id="MISSION-A", engine_id="ENGINE-001"):
    return api.start_mission(
        MissionStartRequest(
            mission_id=mission_id,
            engine_id=engine_id,
        ),
        db,
    )


def test_mission_start_creates_current_mission(mission_api):
    db = mission_api
    started = start_mission(db)

    assert started["mission_id"] == "MISSION-A"
    assert started["status"] == "ACTIVE"
    assert api.current_mission(engine_id="ENGINE-001", db=db)["mission_id"] == "MISSION-A"


def test_mission_start_mqtt_failure_does_not_persist_mission(
    mission_api,
    monkeypatch,
):
    db = mission_api

    def fail_publish(**kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(api, "set_mission_context", fail_publish)

    with pytest.raises(HTTPException) as error:
        start_mission(db)

    assert error.value.status_code == 502
    assert error.value.detail["error"] == "MISSION_COMMAND_FAILED"
    assert db.missions == []


def test_mission_end_preserves_completed_history(mission_api):
    db = mission_api
    start_mission(db)

    ended = api.end_mission(
        MissionEndRequest(engine_id="ENGINE-001"),
        db,
    )

    assert ended["status"] == "COMPLETED"
    assert api.current_mission(engine_id="ENGINE-001", db=db) is None
    missions = api.list_missions(limit=50, db=db)
    assert [mission["mission_id"] for mission in missions] == ["MISSION-A"]


def test_mission_end_mqtt_failure_preserves_active_mission(
    mission_api,
    monkeypatch,
):
    db = mission_api
    start_mission(db, mission_id="MISSION-A")

    def fail_publish(**kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(api, "end_mission_context", fail_publish)

    with pytest.raises(HTTPException) as error:
        api.end_mission(MissionEndRequest(engine_id="ENGINE-001"), db)

    assert error.value.status_code == 502
    assert error.value.detail["error"] == "MISSION_COMMAND_FAILED"
    assert db.missions[0].status == "ACTIVE"
    assert db.missions[0].ended_at is None


def test_second_mission_starts_after_first_ends(mission_api):
    db = mission_api
    start_mission(db, mission_id="MISSION-A")
    api.end_mission(MissionEndRequest(), db)
    second = start_mission(db, mission_id="MISSION-B")

    assert second["mission_id"] == "MISSION-B"
    assert len(db.missions) == 2
    assert db.missions[0].status == "COMPLETED"
    assert db.missions[1].status == "ACTIVE"


def test_multiple_engines_have_independent_current_missions(mission_api):
    db = mission_api
    start_mission(db, mission_id="MISSION-A", engine_id="ENGINE-001")
    start_mission(db, mission_id="MISSION-B", engine_id="ENGINE-002")

    assert api.current_mission("ENGINE-001", db)["mission_id"] == "MISSION-A"
    assert api.current_mission("ENGINE-002", db)["mission_id"] == "MISSION-B"


def test_fault_event_uses_current_engine_mission(mission_api, monkeypatch):
    db = mission_api
    start_mission(db, mission_id="MISSION-CURRENT")
    controller = LiveSimulationController()
    monkeypatch.setattr(
        controller,
        "_publish_command",
        lambda engine_id, payload, vehicle_id="UAV-DEMO-001": {
            "topic": f"test/{engine_id}/control",
            "command": payload,
        },
    )
    monkeypatch.setattr(api, "inject_fault", controller.inject_fault)

    result = inject(db)

    assert result["mission_id"] == "MISSION-CURRENT"
    assert db.events[0].mission_id == "MISSION-CURRENT"


def make_telemetry(
    sequence,
    timestamp,
    mission_id="MISSION-A",
    *,
    engine_id="ENGINE-001",
    egt_c=690.0,
):
    return EngineTelemetryModel(
        id=sequence,
        schema_version="1.0",
        vehicle_id="UAV-DEMO-001",
        engine_id=engine_id,
        mission_id=mission_id,
        sequence=sequence,
        timestamp=timestamp,
        rpm=2520.0,
        cht_c=170.0,
        egt_c=egt_c,
        oil_pressure_kpa=485.0,
        oil_temperature_c=92.0,
        fuel_flow_gph=9.7,
        vibration_g=0.32,
        battery_voltage_v=24.0,
        alternator_current_a=10.0,
        injection_timing_deg=25.0,
        altitude_m=2000.0,
        ambient_temperature_c=25.0,
        throttle_pct=60.0,
        quality_flags=["simulated"],
    )


def test_engine_status_uses_only_selected_engine_telemetry(
    mission_api,
    monkeypatch,
):
    db = mission_api
    t0 = datetime(2026, 10, 4, tzinfo=timezone.utc)
    db.telemetry.extend(
        [
            make_telemetry(
                1,
                t0,
                engine_id="ENGINE-001",
                egt_c=610.0,
            ),
            make_telemetry(
                1,
                t0.replace(second=1),
                engine_id="ENGINE-002",
                egt_c=810.0,
            ),
            make_telemetry(
                2,
                t0.replace(second=2),
                engine_id="ENGINE-001",
                egt_c=620.0,
            ),
            make_telemetry(
                2,
                t0.replace(second=3),
                engine_id="ENGINE-002",
                egt_c=820.0,
            ),
        ]
    )
    recorded_histories = {}
    contexts = {
        engine_id: api.get_engine_analysis_context(engine_id)
        for engine_id in ("ENGINE-001", "ENGINE-002")
    }
    for engine_id, context in contexts.items():
        class RecordingHealthEngine:
            def __init__(self, wrapped, engine_key):
                self.wrapped = wrapped
                self.engine_key = engine_key

            def assess(self, *, twin_state, egt_history, cht_history):
                recorded_histories[self.engine_key] = list(egt_history)
                return self.wrapped.assess(
                    twin_state=twin_state,
                    egt_history=egt_history,
                    cht_history=cht_history,
                )

        context.health_engine = RecordingHealthEngine(
            context.health_engine,
            engine_id,
        )

    monkeypatch.setattr(api, "train_anomaly_detector", lambda: None)
    monkeypatch.setattr(
        api.anomaly_detector,
        "predict",
        lambda features: SimpleNamespace(
            is_anomaly=False,
            anomaly_score=0.1,
        ),
    )

    status_001 = api.engine_status(engine_id="ENGINE-001", db=db)
    status_002 = api.engine_status(engine_id="ENGINE-002", db=db)

    assert status_001["engine_id"] == "ENGINE-001"
    assert status_002["engine_id"] == "ENGINE-002"
    assert recorded_histories["ENGINE-001"] == [610.0, 620.0]
    assert recorded_histories["ENGINE-002"] == [810.0, 820.0]


def test_engine_status_without_engine_id_uses_latest_engine_only(
    mission_api,
    monkeypatch,
):
    db = mission_api
    t0 = datetime(2026, 10, 4, tzinfo=timezone.utc)
    db.telemetry.extend(
        [
            make_telemetry(1, t0, engine_id="ENGINE-001", egt_c=610.0),
            make_telemetry(
                1,
                t0.replace(second=1),
                engine_id="ENGINE-002",
                egt_c=810.0,
            ),
        ]
    )
    recorded_histories = []
    context = api.get_engine_analysis_context("ENGINE-002")
    health_engine = context.health_engine

    class RecordingHealthEngine:
        def __init__(self, wrapped, engine_key):
            self.wrapped = wrapped
            self.engine_key = engine_key

        def assess(self, *, twin_state, egt_history, cht_history):
            recorded_histories.append((self.engine_key, list(egt_history)))
            return self.wrapped.assess(
                twin_state=twin_state,
                egt_history=egt_history,
                cht_history=cht_history,
            )

    context.health_engine = RecordingHealthEngine(
        health_engine,
        "ENGINE-002",
    )
    monkeypatch.setattr(api, "train_anomaly_detector", lambda: None)
    monkeypatch.setattr(
        api.anomaly_detector,
        "predict",
        lambda features: SimpleNamespace(
            is_anomaly=False,
            anomaly_score=0.1,
        ),
    )

    status = api.engine_status(db=db)

    assert status["engine_id"] == "ENGINE-002"
    assert recorded_histories == [("ENGINE-002", [810.0])]


def test_latest_telemetry_filters_by_engine(mission_api):
    db = mission_api
    t0 = datetime(2026, 10, 4, tzinfo=timezone.utc)
    db.telemetry.extend(
        [
            make_telemetry(1, t0, engine_id="ENGINE-001"),
            make_telemetry(1, t0.replace(second=1), engine_id="ENGINE-002"),
            make_telemetry(
                2,
                t0.replace(second=2),
                engine_id="ENGINE-001",
            ),
        ]
    )

    latest_001 = api.latest_telemetry(engine_id="ENGINE-001", db=db)
    latest_002 = api.latest_telemetry(engine_id="ENGINE-002", db=db)

    assert latest_001.engine_id == "ENGINE-001"
    assert latest_001.sequence == 2
    assert latest_002.engine_id == "ENGINE-002"
    assert latest_002.sequence == 1


def test_latest_telemetry_returns_empty_detail_when_no_engine_samples(mission_api):
    response = api.latest_telemetry(engine_id="ENGINE-NO-DATA", db=mission_api)

    assert response == {"detail": "No telemetry available."}


def test_mission_telemetry_and_replay_are_chronological(mission_api):
    db = mission_api
    start_mission(db, mission_id="MISSION-A")
    t0 = datetime(2026, 10, 4, tzinfo=timezone.utc)
    db.telemetry.extend(
        [
            make_telemetry(2, t0.replace(second=1)),
            make_telemetry(1, t0),
        ]
    )

    telemetry = api.get_mission_telemetry("MISSION-A", db)
    replay = api.get_mission_replay("MISSION-A", db)

    assert [row.sequence for row in telemetry] == [1, 2]
    assert [row["sequence"] for row in replay["telemetry"]] == [1, 2]
    assert replay["health"][0]["timestamp"] < replay["health"][1]["timestamp"]


def test_mission_lookup_and_events_retain_mission_association(mission_api):
    db = mission_api
    start_mission(db, mission_id="MISSION-A")
    db.events.append(
        make_fault_event(
            1,
            engine_id="ENGINE-001",
            status="CLEARED",
        )
    )
    db.events[0].mission_id = "MISSION-A"
    db.telemetry.append(
        make_telemetry(1, datetime(2026, 10, 4, tzinfo=timezone.utc))
    )

    mission = api.get_mission("MISSION-A", db)
    events = api.get_mission_events("MISSION-A", db)

    assert mission["telemetry_samples"] == 1
    assert mission["fault_event_count"] == 1
    assert events[0]["mission_id"] == "MISSION-A"


def test_engine_analysis_state_is_independent():
    first = api.get_engine_analysis_context("ENGINE-101")
    second = api.get_engine_analysis_context("ENGINE-102")

    assert first is not second
    assert first.digital_twin is not second.digital_twin
    assert first.degradation_tracker is not second.degradation_tracker
    assert first.rul_estimator is not second.rul_estimator


def test_analysis_context_cache_evicts_oldest_unused_context(monkeypatch):
    monkeypatch.setattr(api, "MAX_ANALYSIS_CONTEXTS", 2)
    monkeypatch.setattr(
        api,
        "analysis_contexts",
        type(api.analysis_contexts)(),
    )

    old_context = api.get_engine_analysis_context("ENGINE-OLD")
    recent_context = api.get_engine_analysis_context("ENGINE-RECENT")
    assert api.get_engine_analysis_context("ENGINE-RECENT") is recent_context

    new_context = api.get_engine_analysis_context("ENGINE-NEW")

    assert "ENGINE-OLD" not in api.analysis_contexts
    assert api.analysis_contexts["ENGINE-RECENT"] is recent_context
    assert api.analysis_contexts["ENGINE-NEW"] is new_context
    assert len(api.analysis_contexts) == 2
    assert old_context is not recent_context


def test_synthetic_scenario_persists_mission_samples_and_events(mission_api):
    db = mission_api
    result = api.run_simulation_scenario(
        MissionScenarioRequest(
            scenario="overheating",
            engine_id="ENGINE-002",
            mission_id="MISSION-SCENARIO",
            duration=20,
        ),
        db,
    )

    assert result["persisted"] is True
    assert result["mission_id"] == "MISSION-SCENARIO"
    assert len(db.telemetry) == 20
    assert all(row.engine_id == "ENGINE-002" for row in db.telemetry)
    assert all(row.mission_id == "MISSION-SCENARIO" for row in db.telemetry)
    assert all(row.quality_flags == ["simulated"] for row in db.telemetry)
    assert db.events[0].mission_id == "MISSION-SCENARIO"
    assert db.events[0].engine_id == "ENGINE-002"
    assert db.events[0].fault == "overheating"
    assert db.events[0].status == "CLEARED"


def test_normal_scenario_alias_uses_existing_normal_mission(mission_api):
    result = api.run_simulation_scenario(
        MissionScenarioRequest(
            scenario="normal",
            engine_id="ENGINE-002",
            mission_id="MISSION-NORMAL",
            duration=3,
        ),
        mission_api,
    )

    assert result["mission_id"] == "MISSION-NORMAL"
    assert result["scenario"]["id"] == "normal_mission"
    assert len(mission_api.telemetry) == 3
    assert mission_api.events == []


def test_required_synthetic_scenarios_are_available():
    required = {
        "normal_mission",
        "high_altitude",
        "hot_weather",
        "rapid_throttle",
        "overheating",
        "low_oil_pressure",
        "abnormal_vibration",
        "combustion_anomaly",
        "sensor_drift",
    }

    assert required.issubset(SCENARIOS)


@pytest.mark.parametrize(
    ("scenario_id", "measurement", "direction"),
    [
        ("overheating", "cht_c", "increase"),
        ("overheating", "egt_c", "increase"),
        ("low_oil_pressure", "oil_pressure_kpa", "decrease"),
        ("abnormal_vibration", "vibration_g", "increase"),
        ("combustion_anomaly", "egt_c", "increase"),
        ("sensor_drift", "egt_c", "increase"),
    ],
)
def test_fault_scenarios_change_corresponding_telemetry(
    scenario_id,
    measurement,
    direction,
):
    scenario = SCENARIOS[scenario_id]
    result = MissionAnalysisPipeline().run(scenario)
    baseline = next(
        step.twin_state.observed
        for step in reversed(result.steps)
        if step.segment_name == scenario.segments[0].name
    )
    final = result.steps[-1].twin_state.observed

    if direction == "increase":
        assert getattr(final, measurement) > getattr(baseline, measurement)
    else:
        assert getattr(final, measurement) < getattr(baseline, measurement)


def test_non_fault_scenario_telemetry_is_deterministic():
    scenario = SCENARIOS["high_altitude"]
    first = MissionAnalysisPipeline().run(scenario)
    second = MissionAnalysisPipeline().run(scenario)
    fields = ("rpm", "cht_c", "egt_c", "oil_pressure_kpa", "vibration_g")

    first_samples = [
        tuple(getattr(step.twin_state.observed, field) for field in fields)
        for step in first.steps
    ]
    second_samples = [
        tuple(getattr(step.twin_state.observed, field) for field in fields)
        for step in second.steps
    ]

    assert first_samples == second_samples


def test_temporary_fault_recovers_without_persistent_degradation():
    scenario = MissionScenario(
        scenario_id="temporary_fault_recovery",
        name="Temporary Fault Recovery",
        description="Verify health recovers after a temporary synthetic fault.",
        segments=(
            MissionSegment("NORMAL", 20, 60.0, 2500.0, 25.0),
            MissionSegment(
                "OVERHEATING",
                25,
                70.0,
                2500.0,
                25.0,
                "overheating",
                0.6,
            ),
            MissionSegment("COOLDOWN", 60, 60.0, 2500.0, 25.0),
        ),
    )
    result = MissionAnalysisPipeline().run(scenario)
    fault_steps = [
        step for step in result.steps if step.segment_name == "OVERHEATING"
    ]
    recovery_steps = [
        step for step in result.steps if step.segment_name == "COOLDOWN"
    ]

    assert min(step.health.health.health_score for step in fault_steps) < 100
    assert recovery_steps[-1].health.health.health_score > min(
        step.health.health.health_score for step in fault_steps
    )
    assert recovery_steps[-1].degradation.degradation_index < max(
        step.degradation.degradation_index for step in fault_steps
    )
    assert recovery_steps[-1].fault.fault == "NO_SPECIFIC_FAULT"


@pytest.fixture
def isolated_publisher_state(monkeypatch):
    monkeypatch.setattr(
        mqtt_publisher,
        "simulators",
        {"ENGINE-001": mqtt_publisher.EngineSimulator()},
    )
    monkeypatch.setattr(
        mqtt_publisher,
        "mission_ids",
        {"ENGINE-001": "MISSION-DEMO-001"},
    )
    monkeypatch.setattr(
        mqtt_publisher,
        "vehicle_ids",
        {"ENGINE-001": "UAV-DEMO-001"},
    )
    monkeypatch.setattr(mqtt_publisher, "command_queue", queue.Queue())
    return mqtt_publisher


def test_publisher_dispatches_inject_fault(
    isolated_publisher_state,
    capsys,
):
    publisher = isolated_publisher_state
    publisher.command_queue.put(
        {
            "command": "inject_fault",
            "engine_id": "ENGINE-001",
            "fault": "overheating",
            "severity": 0.8,
        }
    )

    publisher.process_commands()

    assert publisher.simulators["ENGINE-001"].active_fault == "overheating"
    assert "UNKNOWN CONTROL COMMAND" not in capsys.readouterr().out


def test_publisher_dispatches_clear_fault(
    isolated_publisher_state,
    capsys,
):
    publisher = isolated_publisher_state
    publisher.simulators["ENGINE-001"].inject_fault("overheating", 0.8)
    publisher.command_queue.put(
        {
            "command": "clear_fault",
            "engine_id": "ENGINE-001",
        }
    )

    publisher.process_commands()

    assert publisher.simulators["ENGINE-001"].active_fault is None
    assert "UNKNOWN CONTROL COMMAND" not in capsys.readouterr().out


def test_publisher_dispatches_set_mission(
    isolated_publisher_state,
    capsys,
):
    publisher = isolated_publisher_state
    publisher.command_queue.put(
        {
            "command": "set_mission",
            "engine_id": "ENGINE-001",
            "vehicle_id": "UAV-DEMO-001",
            "mission_id": "MISSION-NEXT",
        }
    )

    publisher.process_commands()

    output = capsys.readouterr().out
    assert publisher.mission_ids["ENGINE-001"] == "MISSION-NEXT"
    assert "MISSION COMMAND APPLIED" in output
    assert "UNKNOWN CONTROL COMMAND" not in output


def test_publisher_dispatches_end_mission(
    isolated_publisher_state,
    capsys,
):
    publisher = isolated_publisher_state
    publisher.command_queue.put(
        {
            "command": "end_mission",
            "engine_id": "ENGINE-001",
            "mission_id": "MISSION-DEMO-001",
        }
    )

    publisher.process_commands()

    output = capsys.readouterr().out
    assert publisher.mission_ids["ENGINE-001"] is None
    assert "MISSION COMMAND APPLIED" in output
    assert "UNKNOWN CONTROL COMMAND" not in output
