from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.digital_twin.core import EngineDigitalTwin
from packages.digital_twin.state_estimator import (
    EngineStateEstimator,
)

from packages.health.engine_health import EngineHealthEngine
from packages.health.diagnostics import fuse_diagnostics
from packages.health.fault_classifier import classify_fault
from packages.health.degradation import (
    EngineDegradationTracker,
)
from packages.health.rul import (
    EngineRULEstimator,
)

from services.api.db.database import SessionLocal
from services.api.db.models import (
    EngineFaultEventModel,
    EngineMissionModel,
    EngineTelemetryModel,
)
from services.api.schemas import (
    TelemetryResponse,
    FaultInjectionRequest,
    MissionEndRequest,
    MissionScenarioRequest,
    MissionStartRequest,
    NotificationResponse,
)

from services.ml.anomaly_detector import EngineAnomalyDetector
from services.ml.features import build_ml_features

from services.api.simulation.controller import (
    inject_fault,
    clear_fault,
    get_fault_state,
    DEFAULT_ENGINE_ID,
    DEFAULT_MISSION_ID,
    DEFAULT_VEHICLE_ID,
    end_mission_context,
    set_mission_context,
)

from services.simulator.engine_simulator import (
    EngineSimulator,
)


from packages.simulation.scenarios import SCENARIOS
from packages.simulation.mission_pipeline import (
    MissionAnalysisPipeline,
)
from packages.simulation.operating_condition import OperatingConditionTracker
from packages.simulation.scenarios import MissionScenario, MissionSegment
from packages.simulation.mission_summary import (
    build_mission_summary,
    summary_to_dict,
)
from packages.simulation.mission_replay import (
    build_mission_replay,
    replay_to_dict,
)


# =============================================================
# FASTAPI APPLICATION
# =============================================================

app = FastAPI(
    title="AeroTwin API",
    description=(
        "Real-time Digital Twin and health monitoring API "
        "for UAV piston-engine diagnostics."
    ),
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://uav-digital-twin-1.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# =============================================================
# CORE ENGINES
# =============================================================

# Kept separate from per-engine live analysis; it is used only while
# training the shared development anomaly detector.
digital_twin = EngineDigitalTwin()

anomaly_detector = EngineAnomalyDetector()


@dataclass
class EngineAnalysisContext:
    digital_twin: EngineDigitalTwin
    health_engine: EngineHealthEngine
    state_estimator: EngineStateEstimator
    degradation_tracker: EngineDegradationTracker
    rul_estimator: EngineRULEstimator
    degradation_initialized: bool = False
    last_degradation_sequence: int | None = None
    rul_initialized: bool = False
    last_rul_sequence: int | None = None
    last_rul_result: object | None = None


analysis_context_lock = RLock()
MAX_ANALYSIS_CONTEXTS = 128
analysis_contexts: OrderedDict[str, EngineAnalysisContext] = OrderedDict()


def get_engine_analysis_context(engine_id: str) -> EngineAnalysisContext:
    with analysis_context_lock:
        context = analysis_contexts.get(engine_id)
        if context is None:
            context = EngineAnalysisContext(
                digital_twin=EngineDigitalTwin(),
                health_engine=EngineHealthEngine(),
                state_estimator=EngineStateEstimator(),
                degradation_tracker=EngineDegradationTracker(),
                rul_estimator=EngineRULEstimator(
                    history_size=60,
                    sample_interval_seconds=1.0,
                ),
            )
            analysis_contexts[engine_id] = context
            while len(analysis_contexts) > MAX_ANALYSIS_CONTEXTS:
                analysis_contexts.popitem(last=False)
        else:
            analysis_contexts.move_to_end(engine_id)
        return context


# =============================================================
# ML MODEL TRAINING STATE
# =============================================================

ml_model_initialized = False


# =============================================================
# DATABASE
# =============================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =============================================================
# ML TRAINING
# =============================================================

def train_anomaly_detector() -> None:
    """
    Train the anomaly detector using clean synthetic
    NORMAL engine-operation data.

    The model is trained only once.

    Faulty database telemetry is intentionally NOT used
    as training data.
    """

    global ml_model_initialized

    # ---------------------------------------------------------
    # PREVENT RE-TRAINING
    # ---------------------------------------------------------

    if ml_model_initialized:
        return

    # ---------------------------------------------------------
    # NORMAL OPERATING CONDITIONS
    # ---------------------------------------------------------

    operating_points = [

        (30.0, 500.0, 20.0),

        (40.0, 1000.0, 22.0),

        (50.0, 1500.0, 25.0),

        (60.0, 2000.0, 25.0),

        (70.0, 2500.0, 28.0),

        (80.0, 3000.0, 30.0),

    ]

    samples_per_point = 50

    feature_vectors = []

    # ---------------------------------------------------------
    # GENERATE NORMAL TRAINING DATA
    # ---------------------------------------------------------

    for (
        throttle_pct,
        altitude_m,
        ambient_temp,
    ) in operating_points:

        # Create an independent clean simulator for each
        # operating region so the training data remains
        # representative of normal engine operation.

        simulator = EngineSimulator(
            seed=int(
                throttle_pct
                + altitude_m
            )
        )

        for _ in range(
            samples_per_point
        ):

            telemetry = simulator.step(

                throttle_pct=(
                    throttle_pct
                ),

                altitude_m=(
                    altitude_m
                ),

                ambient_temperature_c=(
                    ambient_temp
                ),
            )

            # -------------------------------------------------
            # DIGITAL TWIN FEATURES
            # -------------------------------------------------

            twin_state = (
                digital_twin.compare(
                    telemetry
                )
            )

            features = build_ml_features(
                twin_state=twin_state
            )

            feature_vectors.append(
                features
            )

    # ---------------------------------------------------------
    # FIT MODEL
    # ---------------------------------------------------------

    anomaly_detector.fit(
        feature_vectors
    )

    ml_model_initialized = True

    print(
        "ML anomaly detector trained successfully. "
        f"Training samples="
        f"{len(feature_vectors)}"
    )


# =============================================================
# DEGRADATION TRACKING
# =============================================================

def update_degradation_tracker(
    telemetry_rows,
    context: EngineAnalysisContext,
) -> object:
    """
    Update the degradation tracker using chronological
    telemetry samples.

    On the first API request, the recent telemetry history
    is replayed into the degradation tracker.

    On subsequent requests, only new telemetry samples are
    processed.

    This prevents repeatedly counting the same telemetry
    sample every time /engine/status is requested.
    """

    tracker = context.degradation_tracker
    if not context.degradation_initialized:

        for row in telemetry_rows:

            telemetry = (
                TelemetryResponse.model_validate(
                    row
                )
            )

            twin_state = (
                context.digital_twin.compare(
                    telemetry
                )
            )

            degradation_result = (
                tracker.update(
                    twin_state
                )
            )

            context.last_degradation_sequence = (
                telemetry.sequence
            )

        context.degradation_initialized = True

        return degradation_result

    # ---------------------------------------------------------
    # PROCESS ONLY NEW TELEMETRY
    # ---------------------------------------------------------

    latest_row = telemetry_rows[-1]

    latest_telemetry = (
        TelemetryResponse.model_validate(
            latest_row
        )
    )

    latest_sequence = (
        latest_telemetry.sequence
    )

    if (
        context.last_degradation_sequence
        is not None
        and latest_sequence
        == context.last_degradation_sequence
    ):

        # No new telemetry has arrived.
        #
        # Return the most recent degradation result
        # by updating the tracker with the latest state.
        #
        # This does NOT append a duplicate sample because
        # the current tracker state is already represented
        # by the stored history.

        return tracker.update(
            context.digital_twin.compare(
                latest_telemetry
            )
        )

    # ---------------------------------------------------------
    # NEW TELEMETRY
    # ---------------------------------------------------------

    if (
        context.last_degradation_sequence
        is None
        or latest_sequence
        > context.last_degradation_sequence
    ):

        twin_state = (
            context.digital_twin.compare(
                latest_telemetry
            )
        )

        degradation_result = (
            tracker.update(
                twin_state
            )
        )

        context.last_degradation_sequence = (
            latest_sequence
        )

        return degradation_result

    # ---------------------------------------------------------
    # SEQUENCE RESET / OUT-OF-ORDER CASE
    # ---------------------------------------------------------

    twin_state = (
        context.digital_twin.compare(
            latest_telemetry
        )
    )

    degradation_result = (
        tracker.update(
            twin_state
        )
    )

    context.last_degradation_sequence = (
        latest_sequence
    )

    return degradation_result


# =============================================================
# RUL ESTIMATION
# =============================================================

def update_rul_estimator(
    degradation_result,
    latest_sequence,
    context: EngineAnalysisContext,
):
    """
    Update the RUL estimator from the degradation trajectory.

    On first initialization, the degradation history already
    collected by the Degradation Tracker is replayed into the
    RUL estimator.

    On subsequent API requests, only a genuinely new telemetry
    sequence is added.

    This is a synthetic/development prognostics model and is
    NOT a validated aircraft-engine RUL model.
    """

    if not context.rul_initialized:

        # Replay the degradation history already accumulated
        # by the degradation tracker.

        if context.degradation_tracker.degradation_history:

            for degradation_index in (
                context.degradation_tracker.degradation_history
            ):

                context.last_rul_result = (
                    context.rul_estimator.update(
                        degradation_index=float(
                            degradation_index
                        )
                    )
                )

        else:

            context.last_rul_result = (
                context.rul_estimator.update(
                    degradation_index=(
                        degradation_result
                        .degradation_index
                    )
                )
            )

        context.rul_initialized = True
        context.last_rul_sequence = latest_sequence

        return context.last_rul_result

    # ---------------------------------------------------------
    # NO NEW TELEMETRY
    # ---------------------------------------------------------

    if (
        context.last_rul_sequence is not None
        and latest_sequence == context.last_rul_sequence
    ):

        return context.last_rul_result

    # ---------------------------------------------------------
    # NEW TELEMETRY
    # ---------------------------------------------------------

    context.last_rul_result = (
        context.rul_estimator.update(
            degradation_index=(
                degradation_result
                .degradation_index
            )
        )
    )

    context.last_rul_sequence = latest_sequence

    return context.last_rul_result


# =============================================================
# ROOT
# =============================================================

@app.get("/")
def root():

    return {
        "service": "AeroTwin API",
        "version": "0.1.0",
        "status": "online",
    }


# =============================================================
# HEALTH CHECK
# =============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy",

        "service": "aerotwin-api",

        "timestamp": (
            datetime.now(
                timezone.utc
            )
        ),
    }


# =============================================================
# LATEST TELEMETRY
# =============================================================

@app.get(
    "/telemetry/latest",
    response_model=TelemetryResponse | dict[str, str],
)
def latest_telemetry(
    engine_id: str | None = None,
    db: Session = Depends(get_db),
):

    statement = select(EngineTelemetryModel)
    if engine_id is not None:
        statement = statement.where(
            EngineTelemetryModel.engine_id == engine_id
        )
    statement = statement.order_by(
        EngineTelemetryModel.timestamp.desc(),
        EngineTelemetryModel.id.desc(),
    ).limit(1)

    telemetry = (
        db.execute(statement)
        .scalar_one_or_none()
    )

    if telemetry is None:

        return {
            "detail": (
                "No telemetry available."
            )
        }

    return telemetry


# =============================================================
# RECENT TELEMETRY
# =============================================================

@app.get(
    "/telemetry/recent",
    response_model=list[TelemetryResponse],
)
def recent_telemetry(
    limit: int = 60,
    engine_id: str | None = None,
    mission_id: str | None = None,
    db: Session = Depends(get_db),
):

    statement = select(EngineTelemetryModel)
    if engine_id is not None:
        statement = statement.where(
            EngineTelemetryModel.engine_id == engine_id
        )
    if mission_id is not None:
        statement = statement.where(
            EngineTelemetryModel.mission_id == mission_id
        )
    statement = statement.order_by(
        EngineTelemetryModel.timestamp.desc()
    ).limit(limit)

    telemetry = (
        db.execute(statement)
        .scalars()
        .all()
    )

    return list(
        reversed(telemetry)
    )


# =============================================================
# ENGINE STATUS
# =============================================================

@app.get("/engine/status")
def engine_status(
    engine_id: str | None = None,
    db: Session = Depends(get_db),
):

    # =========================================================
    # LOAD RECENT TELEMETRY
    # =========================================================

    if engine_id is None:
        latest_statement = (
            select(EngineTelemetryModel)
            .order_by(
                EngineTelemetryModel.timestamp.desc(),
                EngineTelemetryModel.id.desc(),
            )
            .limit(1)
        )
        latest_engine_telemetry = (
            db.execute(latest_statement)
            .scalar_one_or_none()
        )
        if latest_engine_telemetry is None:
            return {
                "status": "NO_DATA",
                "message": "No telemetry available.",
            }
        engine_id = latest_engine_telemetry.engine_id

    statement = select(EngineTelemetryModel)
    statement = statement.where(
        EngineTelemetryModel.engine_id == engine_id
    )
    statement = statement.order_by(
        EngineTelemetryModel.timestamp.desc(),
        EngineTelemetryModel.id.desc(),
    ).limit(20)

    telemetry_rows = (
        db.execute(statement)
        .scalars()
        .all()
    )

    if not telemetry_rows:

        return {
            "status": "NO_DATA",

            "message": (
                "No telemetry available."
            ),
        }

    telemetry_rows = list(
        reversed(
            telemetry_rows
        )
    )

    latest = telemetry_rows[-1]

    telemetry = (
        TelemetryResponse.model_validate(
            latest
        )
    )
    context = get_engine_analysis_context(telemetry.engine_id)

    # =========================================================
    # DIGITAL TWIN
    # =========================================================

    twin_state = (
        context.digital_twin.compare(
            telemetry
        )
    )

    # =========================================================
    # TREND HISTORY
    # =========================================================

    egt_history = [
        row.egt_c
        for row in telemetry_rows
    ]

    cht_history = [
        row.cht_c
        for row in telemetry_rows
    ]

    # =========================================================
    # HEALTH ENGINE
    # =========================================================

    assessment = (
        context.health_engine.assess(

            twin_state=twin_state,

            egt_history=(
                egt_history
            ),

            cht_history=(
                cht_history
            ),
        )
    )

    # =========================================================
    # ENGINE STATE ESTIMATION
    # =========================================================

    engine_state = (
        context.state_estimator.estimate(

            assessment=assessment,

            twin_state=twin_state,
        )
    )

    # =========================================================
    # DEGRADATION TRACKING
    # =========================================================

    degradation = (
        update_degradation_tracker(
            telemetry_rows,
            context,
        )
    )

    # =========================================================
    # RUL ESTIMATION
    # =========================================================

    rul = (
        update_rul_estimator(
            degradation_result=degradation,
            latest_sequence=(
                telemetry.sequence
            ),
            context=context,
        )
    )

    # =========================================================
    # MACHINE LEARNING
    # =========================================================

    # Train only once.
    #
    # After initialization the same trained model
    # is reused for incoming telemetry.

    train_anomaly_detector()

    ml_features = build_ml_features(

        twin_state=twin_state,

        egt_trend_slope=(
            assessment
            .egt_trend
            .slope
        ),

        cht_trend_slope=(
            assessment
            .cht_trend
            .slope
        ),
    )

    ml_result = (
        anomaly_detector.predict(
            ml_features
        )
    )

    # =========================================================
    # DIAGNOSTIC FUSION
    # =========================================================

    diagnostic = fuse_diagnostics(

        health_status=(
            assessment
            .health
            .status
        ),

        health_score=(
            assessment
            .health
            .health_score
        ),

        ml_is_anomaly=bool(
            ml_result
            .is_anomaly
        ),

        ml_score=float(
            ml_result
            .anomaly_score
        ),

        egt_trend_severity=(
            assessment
            .egt_trend
            .severity
        ),

        cht_trend_severity=(
            assessment
            .cht_trend
            .severity
        ),
    )

    # =========================================================
    # FAULT CLASSIFICATION
    # =========================================================

    fault_diagnosis = classify_fault(

        health_status=(
            assessment
            .health
            .status
        ),

        oil_pressure_deviation=(
            twin_state
            .deviation
            .oil_pressure_kpa
        ),

        cht_deviation=(
            twin_state
            .deviation
            .cht_c
        ),

        egt_deviation=(
            twin_state
            .deviation
            .egt_c
        ),

        oil_temperature_deviation=(
            twin_state
            .deviation
            .oil_temperature_c
        ),

        vibration_deviation=(
            twin_state
            .deviation
            .vibration_g
        ),

        rpm_deviation=(
            twin_state
            .deviation
            .rpm
        ),

        egt_trend_direction=(
            assessment
            .egt_trend
            .direction
        ),

        egt_trend_severity=(
            assessment
            .egt_trend
            .severity
        ),
    )

    fault_state = get_fault_state(telemetry.engine_id)

    # =========================================================
    # API RESPONSE
    # =========================================================

    return {

        # -----------------------------------------------------
        # IDENTIFICATION
        # -----------------------------------------------------

        "engine_id": (
            telemetry.engine_id
        ),

        "mission_id": (
            telemetry.mission_id
        ),
        "active_fault": (
            {
                "fault": fault_state["fault"],
                "severity": fault_state["severity"],
                "started_at": fault_state["started_at"],
                "status": fault_state["status"],
            }
            if fault_state["active"]
            else None
        ),

        # -----------------------------------------------------
        # ENGINE STATE
        # -----------------------------------------------------

        "engine_state": {

            "operating_mode": (
                engine_state
                .operating_mode
            ),

            "overall_health": (
                engine_state
                .overall_health
            ),

            "thermal_state": (
                engine_state
                .thermal_state
            ),

            "lubrication_state": (
                engine_state
                .lubrication_state
            ),

            "combustion_state": (
                engine_state
                .combustion_state
            ),

            "mechanical_state": (
                engine_state
                .mechanical_state
            ),

            "electrical_state": (
                engine_state
                .electrical_state
            ),

            "sensor_confidence": (
                engine_state
                .sensor_confidence
            ),
        },

        # -----------------------------------------------------
        # HEALTH
        # -----------------------------------------------------

        "health_score": (
            assessment
            .health
            .health_score
        ),

        "status": (
            assessment
            .health
            .status
        ),

        "anomaly_score": (
            assessment
            .health
            .anomaly_score
        ),

        # -----------------------------------------------------
        # DEGRADATION
        # -----------------------------------------------------

        "degradation": {

            "index": float(
                degradation
                .degradation_index
            ),

            "level": (
                degradation
                .degradation_level
            ),

            "trend": (
                degradation
                .trend
            ),

            "trend_rate": float(
                degradation
                .trend_rate
            ),

            "indicators": {

                "egt": float(
                    degradation
                    .egt_indicator
                ),

                "cht": float(
                    degradation
                    .cht_indicator
                ),

                "oil_pressure": float(
                    degradation
                    .oil_pressure_indicator
                ),

                "vibration": float(
                    degradation
                    .vibration_indicator
                ),

                "performance": float(
                    degradation
                    .performance_indicator
                ),
            },
        },

        # -----------------------------------------------------
        # REMAINING USEFUL LIFE
        # -----------------------------------------------------

        "rul": {

            "rul_samples": float(
                rul
                .rul_samples
            ),

            "rul_hours": float(
                rul
                .rul_hours
            ),

            "degradation_index": float(
                rul
                .degradation_index
            ),

            "degradation_rate": float(
                rul
                .degradation_rate
            ),

            "confidence": float(
                rul
                .confidence
            ),

            "status": (
                rul
                .status
            ),
        },

        # -----------------------------------------------------
        # ML ANOMALY
        # -----------------------------------------------------

        "ml_anomaly": {

            "score": float(
                ml_result
                .anomaly_score
            ),

            "is_anomaly": bool(
                ml_result
                .is_anomaly
            ),
        },

        # -----------------------------------------------------
        # DIAGNOSTIC FUSION
        # -----------------------------------------------------

        "diagnostic": {

            "status": (
                diagnostic
                .status
            ),

            "confidence": float(
                diagnostic
                .confidence
            ),

            "primary_signal": (
                diagnostic
                .primary_signal
            ),

            "message": (
                diagnostic
                .message
            ),
        },

        # -----------------------------------------------------
        # FAULT DIAGNOSIS
        # -----------------------------------------------------

        "fault_diagnosis": {

            "fault": (
                fault_diagnosis
                .fault
            ),

            "confidence": (
                float(
                    fault_diagnosis
                    .confidence
                )
            ),

            "severity": (
                fault_diagnosis
                .severity
            ),

            "evidence": (
                fault_diagnosis
                .evidence
            ),

            "recommendation": (
                fault_diagnosis
                .recommendation
            ),
        },

        # -----------------------------------------------------
        # PARAMETER STATUS
        # -----------------------------------------------------

        "parameters": {

            "rpm": (
                assessment
                .health
                .rpm_status
            ),

            "cht": (
                assessment
                .health
                .cht_status
            ),

            "egt": (
                assessment
                .health
                .egt_status
            ),

            "oil_pressure": (
                assessment
                .health
                .oil_pressure_status
            ),

            "oil_temperature": (
                assessment
                .health
                .oil_temperature_status
            ),

            "fuel_flow": (
                assessment
                .health
                .fuel_flow_status
            ),

            "vibration": (
                assessment
                .health
                .vibration_status
            ),
        },

        # -----------------------------------------------------
        # DEVIATIONS
        # -----------------------------------------------------

        "deviation": {

            "rpm": (
                twin_state
                .deviation
                .rpm
            ),

            "cht_c": (
                twin_state
                .deviation
                .cht_c
            ),

            "egt_c": (
                twin_state
                .deviation
                .egt_c
            ),

            "oil_pressure_kpa": (
                twin_state
                .deviation
                .oil_pressure_kpa
            ),

            "oil_temperature_c": (
                twin_state
                .deviation
                .oil_temperature_c
            ),

            "fuel_flow_gph": (
                twin_state
                .deviation
                .fuel_flow_gph
            ),

            "vibration_g": (
                twin_state
                .deviation
                .vibration_g
            ),
        },

        # -----------------------------------------------------
        # EXPECTED STATE
        # -----------------------------------------------------

        "expected": {

            "rpm": (
                twin_state
                .expected
                .rpm
            ),

            "cht_c": (
                twin_state
                .expected
                .cht_c
            ),

            "egt_c": (
                twin_state
                .expected
                .egt_c
            ),

            "oil_pressure_kpa": (
                twin_state
                .expected
                .oil_pressure_kpa
            ),

            "oil_temperature_c": (
                twin_state
                .expected
                .oil_temperature_c
            ),

            "fuel_flow_gph": (
                twin_state
                .expected
                .fuel_flow_gph
            ),

            "vibration_g": (
                twin_state
                .expected
                .vibration_g
            ),
        },

        # -----------------------------------------------------
        # TRENDS
        # -----------------------------------------------------

        "trends": {

            "egt": {

                "slope": (
                    assessment
                    .egt_trend
                    .slope
                ),

                "direction": (
                    assessment
                    .egt_trend
                    .direction
                ),

                "severity": (
                    assessment
                    .egt_trend
                    .severity
                ),
            },

            "cht": {

                "slope": (
                    assessment
                    .cht_trend
                    .slope
                ),

                "direction": (
                    assessment
                    .cht_trend
                    .direction
                ),

                "severity": (
                    assessment
                    .cht_trend
                    .severity
                ),
            },
        },
    }


# =============================================================
# SIMULATION - INJECT FAULT
# =============================================================

@app.post("/simulation/fault")
def simulation_fault(
    request: FaultInjectionRequest,
    db: Session = Depends(get_db),
):
    current_mission = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.engine_id == request.engine_id,
                EngineMissionModel.status == "ACTIVE",
            )
        )
        .scalar_one_or_none()
    )
    latest_telemetry = (
        db.execute(
            select(EngineTelemetryModel)
            .where(EngineTelemetryModel.engine_id == request.engine_id)
            .order_by(EngineTelemetryModel.timestamp.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    result = inject_fault(
        fault=request.fault,
        severity=request.severity,
        engine_id=request.engine_id,
        mission_id=(
            current_mission.mission_id
            if current_mission
            else latest_telemetry.mission_id
            if latest_telemetry
            else None
        ),
        vehicle_id=(
            current_mission.vehicle_id
            if current_mission
            else latest_telemetry.vehicle_id
            if latest_telemetry
            else DEFAULT_VEHICLE_ID
        ),
    )

    if result["status"] == "FAULT_ALREADY_ACTIVE":
        active_events = (
            db.execute(
                select(EngineFaultEventModel).where(
                    EngineFaultEventModel.engine_id == request.engine_id,
                    EngineFaultEventModel.fault == request.fault,
                    EngineFaultEventModel.status == "ACTIVE",
                )
            )
            .scalars()
            .all()
        )
        for event in active_events:
            event.severity = result["severity"]
        if active_events:
            db.commit()
        return result

    transition_time = result["started_at"]
    active_events = (
        db.execute(
            select(EngineFaultEventModel).where(
                EngineFaultEventModel.engine_id == request.engine_id,
                EngineFaultEventModel.status == "ACTIVE",
            )
        )
        .scalars()
        .all()
    )
    for event in active_events:
        event.status = "CLEARED"
        event.cleared_at = transition_time

    db.add(
        EngineFaultEventModel(
            engine_id=request.engine_id,
            vehicle_id=result["vehicle_id"],
            mission_id=(
                result.get("mission_id", DEFAULT_MISSION_ID)
            ),
            fault=request.fault,
            severity=result["severity"],
            status="ACTIVE",
            started_at=transition_time,
            created_at=transition_time,
        )
    )
    db.commit()
    return result

# =============================================================
# SIMULATION - CLEAR FAULT
# =============================================================

@app.post("/simulation/clear")
def simulation_clear(
    engine_id: str = DEFAULT_ENGINE_ID,
    db: Session = Depends(get_db),
):
    result = clear_fault(engine_id=engine_id)
    cleared_at = datetime.now(timezone.utc)

    active_events = (
        db.execute(
            select(EngineFaultEventModel).where(
                EngineFaultEventModel.engine_id == engine_id,
                EngineFaultEventModel.status == "ACTIVE",
            )
        )
        .scalars()
        .all()
    )
    for event in active_events:
        event.status = "CLEARED"
        event.cleared_at = cleared_at

    db.commit()
    return result


@app.get("/simulation/fault")
def simulation_fault_state(
    engine_id: str = DEFAULT_ENGINE_ID,
):
    return get_fault_state(engine_id=engine_id)


@app.get("/simulation/fault-events")
def simulation_fault_events(
    engine_id: str | None = None,
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
):
    statement = select(EngineFaultEventModel)
    if engine_id is not None:
        statement = statement.where(
            EngineFaultEventModel.engine_id == engine_id
        )

    events = (
        db.execute(
            statement.order_by(
                EngineFaultEventModel.created_at.desc(),
                EngineFaultEventModel.id.desc(),
            ).limit(limit)
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": event.id,
            "engine_id": event.engine_id,
            "vehicle_id": event.vehicle_id,
            "mission_id": event.mission_id,
            "fault": event.fault,
            "severity": event.severity,
            "status": event.status,
            "started_at": event.started_at,
            "cleared_at": event.cleared_at,
            "created_at": event.created_at,
            "metadata": event.event_metadata,
        }
        for event in events
    ]


@app.get(
    "/notifications",
    response_model=list[NotificationResponse],
)
def notifications(
    engine_id: str | None = None,
    limit: int = Query(default=50, ge=1),
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    statement = select(EngineFaultEventModel)
    if engine_id is not None:
        statement = statement.where(
            EngineFaultEventModel.engine_id == engine_id
        )
    if active_only:
        statement = statement.where(
            EngineFaultEventModel.status == "ACTIVE"
        )

    events = (
        db.execute(
            statement.order_by(
                EngineFaultEventModel.created_at.desc(),
                EngineFaultEventModel.id.desc(),
            ).limit(limit)
        )
        .scalars()
        .all()
    )

    return [
        NotificationResponse(
            id=event.id,
            engine_id=event.engine_id,
            vehicle_id=event.vehicle_id,
            mission_id=event.mission_id,
            fault=event.fault,
            severity=event.severity,
            status=event.status,
            started_at=event.started_at,
            cleared_at=event.cleared_at,
            created_at=event.created_at,
            metadata=event.event_metadata,
        )
        for event in events
    ]


def _mission_response(mission: EngineMissionModel) -> dict:
    return {
        "id": mission.id,
        "mission_id": mission.mission_id,
        "engine_id": mission.engine_id,
        "vehicle_id": mission.vehicle_id,
        "status": mission.status,
        "started_at": mission.started_at,
        "ended_at": mission.ended_at,
        "created_at": mission.created_at,
        "metadata": mission.mission_metadata,
    }


@app.get("/engines")
def list_engines(db: Session = Depends(get_db)):
    engine_ids = set(
        db.execute(
            select(EngineTelemetryModel.engine_id).distinct()
        ).scalars().all()
    )
    engine_ids.update(
        db.execute(
            select(EngineMissionModel.engine_id).distinct()
        ).scalars().all()
    )
    engine_ids.update(
        db.execute(
            select(EngineFaultEventModel.engine_id).distinct()
        ).scalars().all()
    )
    engine_ids.add(DEFAULT_ENGINE_ID)
    return {"engine_ids": sorted(engine_ids)}


@app.post("/missions/start")
def start_mission(
    request: MissionStartRequest,
    db: Session = Depends(get_db),
):
    active = (
        db.execute(
            select(EngineMissionModel)
            .where(
                EngineMissionModel.engine_id == request.engine_id,
                EngineMissionModel.status == "ACTIVE",
            )
            .with_for_update()
        )
        .scalar_one_or_none()
    )
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "MISSION_ALREADY_ACTIVE",
                "mission_id": active.mission_id,
            },
        )

    mission_id = (
        request.mission_id.strip()
        if request.mission_id
        else f"MISSION-{uuid4().hex[:12].upper()}"
    )
    if not mission_id:
        raise HTTPException(
            status_code=422,
            detail="mission_id must not be empty",
        )
    existing = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.mission_id == mission_id
            )
        )
        .scalar_one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "MISSION_ID_ALREADY_EXISTS",
                "mission_id": mission_id,
            },
        )

    started_at = datetime.now(timezone.utc)
    mission = EngineMissionModel(
        mission_id=mission_id,
        engine_id=request.engine_id,
        vehicle_id=request.vehicle_id,
        status="ACTIVE",
        started_at=started_at,
        created_at=started_at,
        mission_metadata=request.metadata,
    )
    try:
        set_mission_context(
            engine_id=request.engine_id,
            vehicle_id=request.vehicle_id,
            mission_id=mission_id,
        )
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "MISSION_COMMAND_FAILED",
                "message": "The simulator did not accept the mission start command.",
            },
        ) from exc

    db.add(mission)
    db.commit()
    return _mission_response(mission)


@app.post("/missions/end")
def end_mission(
    request: MissionEndRequest,
    db: Session = Depends(get_db),
):
    statement = select(EngineMissionModel).where(
        EngineMissionModel.engine_id == request.engine_id,
        EngineMissionModel.status == "ACTIVE",
    )
    if request.mission_id is not None:
        statement = statement.where(
            EngineMissionModel.mission_id == request.mission_id
        )
    mission = (
        db.execute(statement.with_for_update())
        .scalar_one_or_none()
    )
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail="No matching active mission was found.",
        )

    try:
        end_mission_context(
            engine_id=request.engine_id,
            mission_id=mission.mission_id,
        )
    except (OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "MISSION_COMMAND_FAILED",
                "message": "The simulator did not accept the mission end command.",
            },
        ) from exc

    mission.status = "COMPLETED"
    mission.ended_at = datetime.now(timezone.utc)
    db.commit()
    return _mission_response(mission)


@app.get("/missions/current")
def current_mission(
    engine_id: str = DEFAULT_ENGINE_ID,
    db: Session = Depends(get_db),
):
    mission = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.engine_id == engine_id,
                EngineMissionModel.status == "ACTIVE",
            )
        )
        .scalar_one_or_none()
    )
    if mission is None:
        history = (
            db.execute(
                select(EngineMissionModel.id)
                .where(EngineMissionModel.engine_id == engine_id)
                .limit(1)
            )
            .scalar_one_or_none()
        )
        if engine_id != DEFAULT_ENGINE_ID or history is not None:
            return None
        latest_telemetry = (
            db.execute(
                select(EngineTelemetryModel)
                .where(EngineTelemetryModel.engine_id == engine_id)
                .order_by(EngineTelemetryModel.timestamp.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        mission = EngineMissionModel(
            mission_id=(
                latest_telemetry.mission_id
                if latest_telemetry
                else DEFAULT_MISSION_ID
            ),
            engine_id=engine_id,
            vehicle_id=(
                latest_telemetry.vehicle_id
                if latest_telemetry
                else DEFAULT_VEHICLE_ID
            ),
            status="ACTIVE",
            started_at=(
                latest_telemetry.timestamp
                if latest_telemetry
                else datetime.now(timezone.utc)
            ),
            created_at=datetime.now(timezone.utc),
            mission_metadata={"source": "default-simulator"},
        )
        db.add(mission)
        db.commit()
    return _mission_response(mission)


@app.get("/missions")
def list_missions(
    engine_id: str | None = None,
    limit: int = Query(default=50, ge=1),
    db: Session = Depends(get_db),
):
    statement = select(EngineMissionModel)
    if engine_id is not None:
        statement = statement.where(
            EngineMissionModel.engine_id == engine_id
        )
    missions = (
        db.execute(
            statement.order_by(
                EngineMissionModel.started_at.desc(),
                EngineMissionModel.id.desc(),
            ).limit(limit)
        )
        .scalars()
        .all()
    )
    return [_mission_response(mission) for mission in missions]


def _load_mission(
    db: Session,
    mission_id: str,
) -> EngineMissionModel:
    mission = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.mission_id == mission_id
            )
        )
        .scalar_one_or_none()
    )
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "MISSION_NOT_FOUND",
                "mission_id": mission_id,
            },
        )
    return mission


def _load_mission_telemetry(
    db: Session,
    mission: EngineMissionModel,
):
    return (
        db.execute(
            select(EngineTelemetryModel)
            .where(
                EngineTelemetryModel.engine_id == mission.engine_id,
                EngineTelemetryModel.mission_id == mission.mission_id,
            )
            .order_by(
                EngineTelemetryModel.timestamp.asc(),
                EngineTelemetryModel.sequence.asc(),
            )
        )
        .scalars()
        .all()
    )


def _load_mission_events(
    db: Session,
    mission: EngineMissionModel,
):
    return (
        db.execute(
            select(EngineFaultEventModel)
            .where(
                EngineFaultEventModel.engine_id == mission.engine_id,
                EngineFaultEventModel.mission_id == mission.mission_id,
            )
            .order_by(
                EngineFaultEventModel.started_at.asc(),
                EngineFaultEventModel.id.asc(),
            )
        )
        .scalars()
        .all()
    )


@app.get("/missions/{mission_id}")
def get_mission(
    mission_id: str,
    db: Session = Depends(get_db),
):
    mission = _load_mission(db, mission_id)
    telemetry_rows = _load_mission_telemetry(db, mission)
    events = _load_mission_events(db, mission)
    last_timestamp = (
        telemetry_rows[-1].timestamp if telemetry_rows else mission.ended_at
    )
    return {
        **_mission_response(mission),
        "telemetry_samples": len(telemetry_rows),
        "duration_seconds": (
            max(
                0.0,
                (last_timestamp - mission.started_at).total_seconds(),
            )
            if last_timestamp
            else 0.0
        ),
        "fault_event_count": len(events),
    }


@app.get(
    "/missions/{mission_id}/telemetry",
    response_model=list[TelemetryResponse],
)
def get_mission_telemetry(
    mission_id: str,
    db: Session = Depends(get_db),
):
    mission = _load_mission(db, mission_id)
    return _load_mission_telemetry(db, mission)


@app.get("/missions/{mission_id}/events")
def get_mission_events(
    mission_id: str,
    db: Session = Depends(get_db),
):
    mission = _load_mission(db, mission_id)
    return [
        {
            "id": event.id,
            "engine_id": event.engine_id,
            "vehicle_id": event.vehicle_id,
            "mission_id": event.mission_id,
            "fault": event.fault,
            "severity": event.severity,
            "status": event.status,
            "started_at": event.started_at,
            "cleared_at": event.cleared_at,
            "created_at": event.created_at,
            "metadata": event.event_metadata,
        }
        for event in _load_mission_events(db, mission)
    ]


@app.get("/missions/{mission_id}/replay")
def get_mission_replay(
    mission_id: str,
    db: Session = Depends(get_db),
):
    mission = _load_mission(db, mission_id)
    rows = _load_mission_telemetry(db, mission)
    events = _load_mission_events(db, mission)
    twin = EngineDigitalTwin()
    health_engine = EngineHealthEngine()
    degradation_tracker = EngineDegradationTracker()
    rul_estimator = EngineRULEstimator()
    operating_conditions = OperatingConditionTracker()
    operating_conditions.reset()
    egt_history: list[float] = []
    cht_history: list[float] = []
    health_timeline = []
    replay_telemetry = []
    degradation_timeline = []
    rul_timeline = []
    important_changes = []
    previous_status = None

    for index, row in enumerate(rows):
        telemetry = TelemetryResponse.model_validate(row)
        twin_state = twin.compare(telemetry)
        egt_history.append(telemetry.egt_c)
        cht_history.append(telemetry.cht_c)
        health = health_engine.assess(
            twin_state,
            egt_history,
            cht_history,
        )
        operating_condition = operating_conditions.update(
            throttle_pct=telemetry.throttle_pct,
            altitude_m=telemetry.altitude_m,
            ambient_temperature_c=telemetry.ambient_temperature_c,
        )
        health = MissionAnalysisPipeline._apply_transient_context(
            health=health,
            twin_state=twin_state,
            operating_condition=operating_condition,
            is_initialization=index == 0,
        )
        degradation = degradation_tracker.update(
            twin_state,
            is_transition=operating_condition.is_transition,
        )
        rul = rul_estimator.update(degradation.degradation_index)
        assessment = health.health
        time_seconds = max(
            0.0,
            (telemetry.timestamp - mission.started_at).total_seconds(),
        )
        point = {
            "timestamp": telemetry.timestamp,
            "sequence": telemetry.sequence,
            "time_seconds": time_seconds,
            "segment_name": "MISSION",
            "status": assessment.status,
            "health_score": assessment.health_score,
            "anomaly_score": assessment.anomaly_score,
            "operating_mode": "RECORDED",
            "thermal_state": assessment.cht_status,
            "lubrication_state": assessment.oil_pressure_status,
            "combustion_state": assessment.egt_status,
            "mechanical_state": assessment.vibration_status,
            "degradation_index": degradation.degradation_index,
            "degradation_level": degradation.degradation_level,
            "degradation_trend": degradation.trend,
            "degradation_rate": degradation.trend_rate,
            "rul_hours": rul.rul_hours,
            "rul_degradation_index": rul.degradation_index,
            "rul_degradation_rate": rul.degradation_rate,
        }
        health_timeline.append(point)
        replay_telemetry.append(
            {
                **telemetry.model_dump(mode="json"),
                "time_seconds": time_seconds,
                "segment_name": "MISSION",
                "expected_rpm": twin_state.expected.rpm,
                "expected_cht_c": twin_state.expected.cht_c,
                "expected_egt_c": twin_state.expected.egt_c,
                "expected_oil_pressure_kpa": (
                    twin_state.expected.oil_pressure_kpa
                ),
                "expected_oil_temperature_c": (
                    twin_state.expected.oil_temperature_c
                ),
                "expected_fuel_flow_gph": (
                    twin_state.expected.fuel_flow_gph
                ),
                "expected_vibration_g": (
                    twin_state.expected.vibration_g
                ),
            }
        )
        degradation_timeline.append(
            {
                "time_seconds": time_seconds,
                "degradation_index": degradation.degradation_index,
                "degradation_level": degradation.degradation_level,
                "trend": degradation.trend,
                "trend_rate": degradation.trend_rate,
            }
        )
        rul_timeline.append(
            {
                "time_seconds": time_seconds,
                "rul_hours": rul.rul_hours,
                "rul_samples": rul.rul_samples,
                "confidence": rul.confidence,
                "status": rul.status,
                "degradation_index": rul.degradation_index,
                "degradation_rate": rul.degradation_rate,
            }
        )
        if assessment.status != previous_status:
            important_changes.append(
                {
                    "type": "HEALTH_STATUS",
                    "timestamp": telemetry.timestamp,
                    "status": assessment.status,
                    "health_score": assessment.health_score,
                }
            )
            previous_status = assessment.status

    serialized_telemetry = replay_telemetry
    serialized_events = [
        {
            "id": event.id,
            "engine_id": event.engine_id,
            "vehicle_id": event.vehicle_id,
            "mission_id": event.mission_id,
            "fault": event.fault,
            "severity": event.severity,
            "status": event.status,
            "started_at": event.started_at,
            "cleared_at": event.cleared_at,
            "created_at": event.created_at,
            "metadata": event.event_metadata,
        }
        for event in events
    ]
    for event in events:
        important_changes.append(
            {
                "type": "FAULT_INJECTED",
                "timestamp": event.started_at,
                "fault": event.fault,
                "severity": event.severity,
                "status": event.status,
            }
        )
        if event.cleared_at is not None:
            important_changes.append(
                {
                    "type": "FAULT_CLEARED",
                    "timestamp": event.cleared_at,
                    "fault": event.fault,
                    "status": "CLEARED",
                }
            )
    important_changes.sort(key=lambda change: change["timestamp"])

    last_timestamp = rows[-1].timestamp if rows else mission.ended_at
    duration = (
        max(
            0.0,
            (last_timestamp - mission.started_at).total_seconds(),
        )
        if last_timestamp
        else 0.0
    )
    return {
        "mission": _mission_response(mission),
        "mission_id": mission.mission_id,
        "engine_id": mission.engine_id,
        "scenario_id": (mission.mission_metadata or {}).get("scenario_id"),
        "scenario_name": (mission.mission_metadata or {}).get("scenario_name"),
        "duration_seconds": duration,
        "mission_duration_seconds": duration,
        "total_samples": len(serialized_telemetry),
        "telemetry": serialized_telemetry,
        "events": serialized_events,
        "health": health_timeline,
        "degradation": degradation_timeline,
        "rul": rul_timeline,
        "fault_events": [
            {
                "fault": event.fault,
                "time_seconds": max(
                    0.0,
                    (event.started_at - mission.started_at).total_seconds(),
                ),
                "end_time_seconds": max(
                    0.0,
                    (
                        (event.cleared_at or last_timestamp or event.started_at)
                        - mission.started_at
                    ).total_seconds(),
                ),
                "confidence": event.severity,
                "severity": (
                    "CRITICAL"
                    if event.severity >= 0.7
                    else "WARNING"
                    if event.severity >= 0.3
                    else "NORMAL"
                ),
                "evidence": (event.event_metadata or {}).get("evidence", []),
                "status": event.status,
            }
            for event in events
        ],
        "important_state_changes": important_changes,
    }

# =============================================================
# MISSION SIMULATION - LIST SCENARIOS
# =============================================================

@app.get("/mission/scenarios")
def mission_scenarios():

    return {
        "scenarios": [
            {
                "id": scenario.scenario_id,
                "name": scenario.name,
                "description": getattr(
                    scenario,
                    "description",
                    "",
                ),
            }
            for scenario in SCENARIOS.values()
        ]
    }


# =============================================================
# MISSION SIMULATION - RUN
# =============================================================

@app.post("/mission/run/{scenario_id}")
def run_mission(
    scenario_id: str,
):

    scenario = SCENARIOS.get(
        scenario_id
    )

    if scenario is None:

        raise HTTPException(
            status_code=404,
            detail={
                "error": "SCENARIO_NOT_FOUND",
                "scenario_id": scenario_id,
                "available_scenarios": list(
                    SCENARIOS.keys()
                ),
            },
        )

    pipeline = MissionAnalysisPipeline()

    result = pipeline.run(
        scenario
    )

    summary = build_mission_summary(
        result
    )

    replay = build_mission_replay(
        result
    )

    return {
        "scenario": {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "description": getattr(
                scenario,
                "description",
                "",
            ),
        },
        "summary": summary_to_dict(
            summary
        ),
        "replay": replay_to_dict(
            replay
        ),
    }


def _resize_scenario(
    scenario: MissionScenario,
    duration: int | None,
) -> MissionScenario:
    if duration is None:
        return scenario
    if duration < len(scenario.segments):
        raise HTTPException(
            status_code=422,
            detail="duration must allow at least one second per scenario segment",
        )

    total_duration = sum(
        segment.duration_seconds for segment in scenario.segments
    )
    resized_segments = []
    elapsed_original = 0
    elapsed_resized = 0
    for index, segment in enumerate(scenario.segments):
        elapsed_original += segment.duration_seconds
        if index == len(scenario.segments) - 1:
            segment_end = duration
        else:
            segment_end = round(
                duration * elapsed_original / total_duration
            )
            segment_end = max(
                elapsed_resized + 1,
                segment_end,
            )
            segment_end = min(
                duration - (len(scenario.segments) - index - 1),
                segment_end,
            )
        resized_segments.append(
            MissionSegment(
                name=segment.name,
                duration_seconds=segment_end - elapsed_resized,
                throttle_pct=segment.throttle_pct,
                altitude_m=segment.altitude_m,
                ambient_temperature_c=segment.ambient_temperature_c,
                fault=segment.fault,
                fault_severity=segment.fault_severity,
            )
        )
        elapsed_resized = segment_end

    return MissionScenario(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        description=scenario.description,
        segments=tuple(resized_segments),
    )


@app.post("/simulation/scenario")
def run_simulation_scenario(
    request: MissionScenarioRequest,
    db: Session = Depends(get_db),
):
    scenario_id = (
        "normal_mission"
        if request.scenario == "normal"
        else request.scenario
    )
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "SCENARIO_NOT_FOUND",
                "scenario_id": request.scenario,
                "available_scenarios": [*SCENARIOS, "normal"],
            },
        )

    scenario = _resize_scenario(scenario, request.duration)
    mission_id = (
        request.mission_id.strip()
        if request.mission_id
        else f"MISSION-{uuid4().hex[:12].upper()}"
    )
    if not mission_id:
        raise HTTPException(
            status_code=422,
            detail="mission_id must not be empty",
        )
    existing = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.mission_id == mission_id
            )
        )
        .scalar_one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "MISSION_ID_ALREADY_EXISTS",
                "mission_id": mission_id,
            },
        )

    current_mission = (
        db.execute(
            select(EngineMissionModel).where(
                EngineMissionModel.engine_id == request.engine_id,
                EngineMissionModel.status == "ACTIVE",
            )
        )
        .scalar_one_or_none()
    )
    vehicle_id = (
        current_mission.vehicle_id
        if current_mission
        else DEFAULT_VEHICLE_ID
    )
    result = MissionAnalysisPipeline(
        engine_id=request.engine_id,
        mission_id=mission_id,
        vehicle_id=vehicle_id,
    ).run(scenario)
    if not result.steps:
        raise HTTPException(
            status_code=422,
            detail="Scenario produced no telemetry samples.",
        )

    telemetry_rows = []
    for step in result.steps:
        telemetry = step.twin_state.observed
        telemetry_rows.append(
            EngineTelemetryModel(
                schema_version=telemetry.schema_version,
                vehicle_id=telemetry.vehicle_id,
                engine_id=telemetry.engine_id,
                mission_id=telemetry.mission_id,
                sequence=telemetry.sequence,
                timestamp=telemetry.timestamp,
                rpm=telemetry.rpm,
                cht_c=telemetry.cht_c,
                egt_c=telemetry.egt_c,
                oil_pressure_kpa=telemetry.oil_pressure_kpa,
                oil_temperature_c=telemetry.oil_temperature_c,
                fuel_flow_gph=telemetry.fuel_flow_gph,
                vibration_g=telemetry.vibration_g,
                battery_voltage_v=telemetry.battery_voltage_v,
                alternator_current_a=telemetry.alternator_current_a,
                injection_timing_deg=telemetry.injection_timing_deg,
                altitude_m=telemetry.altitude_m,
                ambient_temperature_c=telemetry.ambient_temperature_c,
                throttle_pct=telemetry.throttle_pct,
                quality_flags=[
                    flag.value for flag in telemetry.quality_flags
                ],
            )
        )

    first_timestamp = (
        result.steps[0].twin_state.observed.timestamp
        - timedelta(seconds=1)
    )
    last_timestamp = result.steps[-1].twin_state.observed.timestamp
    mission = EngineMissionModel(
        mission_id=mission_id,
        engine_id=request.engine_id,
        vehicle_id=vehicle_id,
        status="COMPLETED",
        started_at=first_timestamp,
        ended_at=last_timestamp,
        created_at=first_timestamp,
        mission_metadata={
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "model": "SYNTHETIC_DEVELOPMENT",
        },
    )
    db.add(mission)
    db.add_all(telemetry_rows)

    segment_steps: dict[str, list] = {}
    for step in result.steps:
        segment_steps.setdefault(step.segment_name, []).append(step)
    for segment in scenario.segments:
        if segment.fault is None:
            continue
        samples = segment_steps.get(segment.name, [])
        if not samples:
            continue
        started_at = samples[0].twin_state.observed.timestamp
        cleared_at = samples[-1].twin_state.observed.timestamp
        db.add(
            EngineFaultEventModel(
                engine_id=request.engine_id,
                vehicle_id=vehicle_id,
                mission_id=mission_id,
                fault=segment.fault,
                severity=segment.fault_severity,
                status="CLEARED",
                started_at=started_at,
                cleared_at=cleared_at,
                created_at=started_at,
                event_metadata={
                    "scenario_id": scenario.scenario_id,
                    "segment": segment.name,
                },
            )
        )

    db.commit()
    summary = build_mission_summary(result)
    replay = build_mission_replay(result)
    return {
        "mission_id": mission_id,
        "scenario": {
            "id": scenario.scenario_id,
            "name": scenario.name,
            "description": scenario.description,
        },
        "summary": summary_to_dict(summary),
        "replay": replay_to_dict(replay),
        "persisted": True,
    }

# =============================================================
# MISSION SIMULATION - REPLAY
# =============================================================

@app.get("/mission/replay/{scenario_id}")
def mission_replay(
    scenario_id: str,
):

    scenario = SCENARIOS.get(
        scenario_id
    )

    if scenario is None:

        raise HTTPException(
            status_code=404,
            detail={
                "error": "SCENARIO_NOT_FOUND",
                "scenario_id": scenario_id,
                "available_scenarios": list(
                    SCENARIOS.keys()
                ),
            },
        )

    pipeline = MissionAnalysisPipeline()

    result = pipeline.run(
        scenario
    )

    replay = build_mission_replay(
        result
    )

    return replay_to_dict(
        replay
    )
