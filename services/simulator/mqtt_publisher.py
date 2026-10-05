import json
import queue
import time

import paho.mqtt.client as mqtt

from services.simulator.engine_simulator import EngineSimulator


MQTT_HOST = "localhost"
MQTT_PORT = 1883

TELEMETRY_TOPIC = (
    "aerotwin/uav/"
    "UAV-DEMO-001/"
    "engine/"
    "ENGINE-001/"
    "telemetry"
)

CONTROL_TOPIC = (
    "aerotwin/uav/"
    "UAV-DEMO-001/"
    "engine/"
    "ENGINE-001/"
    "control"
)

CONTROL_SUBSCRIPTION = (
    "aerotwin/uav/"
    "+/"
    "engine/+/control"
)

# =========================================================
# SHARED SIMULATOR
# =========================================================

simulator = EngineSimulator()
simulators: dict[str, EngineSimulator] = {"ENGINE-001": simulator}
mission_ids: dict[str, str | None] = {
    "ENGINE-001": "MISSION-DEMO-001",
}
vehicle_ids: dict[str, str] = {"ENGINE-001": "UAV-DEMO-001"}

# Commands received by MQTT are placed here.
command_queue = queue.Queue()


# =========================================================
# MQTT CONNECT
# =========================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties,
):

    if reason_code == 0:

        print("Connected to MQTT broker.")

        client.subscribe(
            CONTROL_SUBSCRIPTION,
            qos=1,
        )

        print(
            f"Subscribed to control topic: "
            f"{CONTROL_SUBSCRIPTION}"
        )

    else:

        print(
            "MQTT connection failed. "
            f"reason_code={reason_code}"
        )


# =========================================================
# MQTT CONTROL MESSAGE
# =========================================================

def on_message(
    client,
    userdata,
    message,
):

    try:

        payload = json.loads(
            message.payload.decode("utf-8")
        )

        print(
            f"CONTROL MESSAGE RECEIVED: {payload}"
        )

        command_queue.put(payload)

    except Exception as exc:

        print(
            f"CONTROL MESSAGE ERROR: {exc}"
        )


# =========================================================
# APPLY PENDING COMMANDS
# =========================================================

def process_commands():

    while True:

        try:

            payload = command_queue.get_nowait()

        except queue.Empty:

            break

        command = payload.get("command")
        engine_id = payload.get("engine_id", "ENGINE-001")
        if not isinstance(engine_id, str) or not engine_id:
            print(f"INVALID ENGINE ID IN CONTROL COMMAND: {payload}")
            continue

        engine_simulator = simulators.get(engine_id)
        if engine_simulator is None:
            engine_simulator = EngineSimulator()
            simulators[engine_id] = engine_simulator
        vehicle_ids[engine_id] = payload.get(
            "vehicle_id",
            vehicle_ids.get(engine_id, "UAV-DEMO-001"),
        )

        if command == "set_mission":
            mission_ids[engine_id] = payload["mission_id"]
        elif command == "end_mission":
            mission_ids[engine_id] = None
        elif command == "inject_fault":
            mission_ids[engine_id] = payload.get(
                "mission_id",
                mission_ids.get(engine_id, "MISSION-DEMO-001"),
            )

        # -------------------------------------------------
        # INJECT FAULT
        # -------------------------------------------------

        if command == "inject_fault":

            fault = payload.get("fault")

            severity = float(
                payload.get(
                    "severity",
                    1.0,
                )
            )

            engine_simulator.inject_fault(
                fault=fault,
                severity=severity,
            )

            print(
                "CONTROL APPLIED: "
                f"engine={engine_id} | "
                f"fault={engine_simulator.active_fault} | "
                f"severity={engine_simulator.fault_severity} | "
                f"duration={engine_simulator.fault_duration}"
            )

        # -------------------------------------------------
        # CLEAR FAULT
        # -------------------------------------------------

        elif command == "clear_fault":

            engine_simulator.clear_fault()

            print(
                "CONTROL APPLIED: "
                f"fault cleared for {engine_id}"
            )

        elif command == "set_mission":

            print(
                "MISSION COMMAND APPLIED: "
                f"engine={engine_id} | "
                f"mission={mission_ids[engine_id]}"
            )

        elif command == "end_mission":

            print(
                "MISSION COMMAND APPLIED: "
                f"engine={engine_id} | mission ended"
            )

        else:

            print(
                f"UNKNOWN CONTROL COMMAND: {command}"
            )


# =========================================================
# MAIN
# =========================================================

def main():

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="aerotwin-engine-simulator",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print(
        f"Connecting to MQTT broker at "
        f"{MQTT_HOST}:{MQTT_PORT}..."
    )

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        keepalive=60,
    )

    client.loop_start()

    print(
        "MQTT simulator controller started."
    )

    try:

        while True:

            # -------------------------------------------------
            # APPLY CONTROL COMMANDS
            # -------------------------------------------------

            process_commands()

            # -------------------------------------------------
            # GENERATE TELEMETRY
            # -------------------------------------------------

            for engine_id, engine_simulator in list(simulators.items()):
                telemetry = engine_simulator.step(
                    engine_id=engine_id,
                    mission_id=mission_ids.get(
                        engine_id,
                        "MISSION-DEMO-001",
                    ) or "MISSION-UNASSIGNED",
                    vehicle_id=vehicle_ids.get(
                        engine_id,
                        "UAV-DEMO-001",
                    ),
                )

                telemetry_topic = (
                    f"aerotwin/uav/{telemetry.vehicle_id}/"
                    f"engine/{engine_id}/telemetry"
                )
                result = client.publish(
                    telemetry_topic,
                    payload=telemetry.model_dump_json(),
                    qos=1,
                )
                result.wait_for_publish()

                print(
                    f"Published engine={engine_id} "
                    f"sequence={telemetry.sequence} "
                    f"RPM={telemetry.rpm:.1f} "
                    f"EGT={telemetry.egt_c:.1f}°C "
                    f"CHT={telemetry.cht_c:.1f}°C"
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print(
            "\nStopping simulator..."
        )

    finally:

        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":

    main()