import os
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

import paho.mqtt.client as mqtt

from services.simulator.engine_simulator import EngineSimulator


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = 1883
DEFAULT_ENGINE_ID = "ENGINE-001"
DEFAULT_VEHICLE_ID = "UAV-DEMO-001"
DEFAULT_MISSION_ID = "MISSION-DEMO-001"


@dataclass
class LiveFaultState:
    engine_id: str
    active_fault: str | None = None
    severity: float = 0.0
    started_at: datetime | None = None
    fault_duration: float = 0.0
    mission_id: str | None = DEFAULT_MISSION_ID
    vehicle_id: str = DEFAULT_VEHICLE_ID

    @property
    def active(self) -> bool:
        return self.active_fault is not None


class LiveSimulationController:
    """Tracks live fault state by engine and forwards controls over MQTT."""

    def __init__(self):
        self._states: dict[str, LiveFaultState] = {}
        self._lock = RLock()

    @staticmethod
    def _control_topic(
        engine_id: str,
        vehicle_id: str = DEFAULT_VEHICLE_ID,
    ) -> str:
        return (
            f"aerotwin/uav/{vehicle_id}/"
            f"engine/{engine_id}/control"
        )

    def _publish_command(
        self,
        engine_id: str,
        payload: dict,
        vehicle_id: str = DEFAULT_VEHICLE_ID,
    ) -> dict:
        topic = self._control_topic(engine_id, vehicle_id)
        client_id = f"aerotwin-api-controller-{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )

        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            result = client.publish(
                topic,
                payload=json.dumps(payload),
                qos=1,
            )
            result.wait_for_publish()

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(
                    f"MQTT publish failed: rc={result.rc}"
                )

            time.sleep(0.1)
            return {
                "status": "COMMAND_SENT",
                "topic": topic,
                "command": payload,
            }
        finally:
            client.loop_stop()
            client.disconnect()

    def inject_fault(
        self,
        fault: str,
        severity: float = 1.0,
        engine_id: str = DEFAULT_ENGINE_ID,
        mission_id: str | None = None,
        vehicle_id: str = DEFAULT_VEHICLE_ID,
    ) -> dict:
        if fault not in EngineSimulator.SUPPORTED_FAULTS:
            raise ValueError(
                f"Unsupported fault '{fault}'. "
                f"Supported faults: {sorted(EngineSimulator.SUPPORTED_FAULTS)}"
            )

        severity = max(0.0, min(1.0, float(severity)))
        with self._lock:
            previous = self._states.get(engine_id)
            if previous and previous.active_fault == fault:
                if previous.severity != severity:
                    command = self._publish_command(
                        engine_id,
                        {
                            "command": "inject_fault",
                            "fault": fault,
                            "severity": severity,
                            "engine_id": engine_id,
                            "mission_id": previous.mission_id,
                            "vehicle_id": previous.vehicle_id,
                        },
                        vehicle_id=previous.vehicle_id,
                    )
                    previous.severity = severity
                else:
                    command = {}
                return {
                    **command,
                    **self.get_state(engine_id),
                    "status": "FAULT_ALREADY_ACTIVE",
                }

            mission_id = (
                mission_id
                if mission_id is not None
                else (
                    previous.mission_id
                    if previous
                    else DEFAULT_MISSION_ID
                )
            )
            vehicle_id = previous.vehicle_id if previous else vehicle_id
            command = self._publish_command(
                engine_id,
                {
                    "command": "inject_fault",
                    "fault": fault,
                    "severity": severity,
                    "engine_id": engine_id,
                    "mission_id": mission_id,
                    "vehicle_id": vehicle_id,
                },
                vehicle_id=vehicle_id,
            )

            state = LiveFaultState(
                engine_id=engine_id,
                active_fault=fault,
                severity=severity,
                started_at=datetime.now(timezone.utc),
                mission_id=mission_id,
                vehicle_id=vehicle_id,
            )
            self._states[engine_id] = state
            return {
                **command,
                "status": "FAULT_INJECTED",
                "engine_id": engine_id,
                "fault": fault,
                "severity": severity,
                "started_at": state.started_at,
                "mission_id": state.mission_id,
                "vehicle_id": state.vehicle_id,
            }

    def clear_fault(self, engine_id: str = DEFAULT_ENGINE_ID) -> dict:
        with self._lock:
            state = self._states.get(engine_id)
            vehicle_id = (
                state.vehicle_id if state else DEFAULT_VEHICLE_ID
            )
            command = self._publish_command(
                engine_id,
                {
                    "command": "clear_fault",
                    "engine_id": engine_id,
                },
                vehicle_id=vehicle_id,
            )
            if state:
                state.active_fault = None
                state.severity = 0.0
                state.started_at = None
                state.fault_duration = 0.0
            return {
                **command,
                "status": "FAULT_CLEARED",
                "engine_id": engine_id,
            }

    def set_mission(
        self,
        engine_id: str,
        vehicle_id: str,
        mission_id: str,
    ) -> dict:
        with self._lock:
            state = self._states.get(engine_id)
            current_vehicle = state.vehicle_id if state else vehicle_id
            command = self._publish_command(
                engine_id,
                {
                    "command": "set_mission",
                    "engine_id": engine_id,
                    "vehicle_id": vehicle_id,
                    "mission_id": mission_id,
                },
                vehicle_id=vehicle_id,
            )
            if state is None:
                state = LiveFaultState(engine_id=engine_id)
                self._states[engine_id] = state
            state.vehicle_id = vehicle_id or current_vehicle
            state.mission_id = mission_id
            return command

    def end_mission(
        self,
        engine_id: str,
        mission_id: str | None = None,
    ) -> dict:
        with self._lock:
            state = self._states.get(engine_id)
            vehicle_id = state.vehicle_id if state else DEFAULT_VEHICLE_ID
            command = self._publish_command(
                engine_id,
                {
                    "command": "end_mission",
                    "engine_id": engine_id,
                    "mission_id": mission_id,
                    "vehicle_id": vehicle_id,
                },
                vehicle_id=vehicle_id,
            )
            if state:
                state.mission_id = None
            return command

    def get_state(self, engine_id: str = DEFAULT_ENGINE_ID) -> dict:
        with self._lock:
            state = self._states.get(engine_id)
            if state is None:
                state = LiveFaultState(engine_id=engine_id)
                self._states[engine_id] = state

            duration = 0.0
            if state.started_at is not None:
                duration = max(
                    0.0,
                    (datetime.now(timezone.utc) - state.started_at).total_seconds(),
                )
                state.fault_duration = duration

            return {
                "engine_id": engine_id,
                "active": state.active,
                "active_fault": state.active_fault,
                "fault": state.active_fault,
                "severity": state.severity,
                "started_at": state.started_at,
                "fault_duration": state.fault_duration,
                "mission_id": state.mission_id,
                "vehicle_id": state.vehicle_id,
                "status": "ACTIVE" if state.active else "CLEARED",
            }


live_simulation_controller = LiveSimulationController()


def inject_fault(
    fault: str,
    severity: float = 1.0,
    engine_id: str = DEFAULT_ENGINE_ID,
    mission_id: str | None = None,
    vehicle_id: str = DEFAULT_VEHICLE_ID,
) -> dict:
    return live_simulation_controller.inject_fault(
        fault=fault,
        severity=severity,
        engine_id=engine_id,
        mission_id=mission_id,
        vehicle_id=vehicle_id,
    )


def clear_fault(engine_id: str = DEFAULT_ENGINE_ID) -> dict:
    return live_simulation_controller.clear_fault(engine_id=engine_id)


def get_fault_state(engine_id: str = DEFAULT_ENGINE_ID) -> dict:
    return live_simulation_controller.get_state(engine_id=engine_id)


def set_mission_context(
    engine_id: str,
    vehicle_id: str,
    mission_id: str,
) -> dict:
    return live_simulation_controller.set_mission(
        engine_id=engine_id,
        vehicle_id=vehicle_id,
        mission_id=mission_id,
    )


def end_mission_context(
    engine_id: str,
    mission_id: str | None = None,
) -> dict:
    return live_simulation_controller.end_mission(
        engine_id=engine_id,
        mission_id=mission_id,
    )



