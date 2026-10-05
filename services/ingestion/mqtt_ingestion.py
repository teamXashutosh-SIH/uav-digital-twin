import json
from collections import OrderedDict

import paho.mqtt.client as mqtt
import psycopg

from packages.contracts.telemetry import EngineTelemetry


MQTT_HOST = "localhost"
MQTT_PORT = 1883

MQTT_TOPIC = (
    "aerotwin/uav/"
    "+/"
    "engine/"
    "+/"
    "telemetry"
)

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "aerotwin",
    "user": "aerotwin",
    "password": "aerotwin_dev_password",
}


db_connection = None
last_sequences: OrderedDict[str, int] = OrderedDict()
MAX_CACHED_ENGINE_SEQUENCES = 128


def connect_database():
    global db_connection

    db_connection = psycopg.connect(**DB_CONFIG)

    print("Connected to PostgreSQL.")


def store_telemetry(telemetry: EngineTelemetry) -> int:
    query = """
        INSERT INTO engine_telemetry (
            schema_version,
            vehicle_id,
            engine_id,
            mission_id,
            sequence,
            timestamp,
            rpm,
            cht_c,
            egt_c,
            oil_pressure_kpa,
            oil_temperature_c,
            fuel_flow_gph,
            vibration_g,
            battery_voltage_v,
            alternator_current_a,
            injection_timing_deg,
            altitude_m,
            ambient_temperature_c,
            throttle_pct,
            quality_flags
        )
        VALUES (
            %(schema_version)s,
            %(vehicle_id)s,
            %(engine_id)s,
            %(mission_id)s,
            %(sequence)s,
            %(timestamp)s,
            %(rpm)s,
            %(cht_c)s,
            %(egt_c)s,
            %(oil_pressure_kpa)s,
            %(oil_temperature_c)s,
            %(fuel_flow_gph)s,
            %(vibration_g)s,
            %(battery_voltage_v)s,
            %(alternator_current_a)s,
            %(injection_timing_deg)s,
            %(altitude_m)s,
            %(ambient_temperature_c)s,
            %(throttle_pct)s,
            %(quality_flags)s
        )
    """

    with db_connection.cursor() as cursor:
        last_sequence = last_sequences.get(telemetry.engine_id)
        if last_sequence is None:
            cursor.execute(
                """
                SELECT MAX(sequence)
                FROM engine_telemetry
                WHERE engine_id = %s
                """,
                (telemetry.engine_id,),
            )
            row = cursor.fetchone()
            last_sequence = row[0] if row else None

        sequence = (
            telemetry.sequence
            if last_sequence is None
            else max(telemetry.sequence, last_sequence + 1)
        )

    values = {
        "schema_version": telemetry.schema_version,
        "vehicle_id": telemetry.vehicle_id,
        "engine_id": telemetry.engine_id,
        "mission_id": telemetry.mission_id,
        "sequence": sequence,
        "timestamp": telemetry.timestamp,
        "rpm": telemetry.rpm,
        "cht_c": telemetry.cht_c,
        "egt_c": telemetry.egt_c,
        "oil_pressure_kpa": telemetry.oil_pressure_kpa,
        "oil_temperature_c": telemetry.oil_temperature_c,
        "fuel_flow_gph": telemetry.fuel_flow_gph,
        "vibration_g": telemetry.vibration_g,
        "battery_voltage_v": telemetry.battery_voltage_v,
        "alternator_current_a": telemetry.alternator_current_a,
        "injection_timing_deg": telemetry.injection_timing_deg,
        "altitude_m": telemetry.altitude_m,
        "ambient_temperature_c": telemetry.ambient_temperature_c,
        "throttle_pct": telemetry.throttle_pct,
        "quality_flags": json.dumps(
            [flag.value for flag in telemetry.quality_flags]
        ),
    }

    with db_connection.cursor() as cursor:
        cursor.execute(query, values)

    db_connection.commit()
    last_sequences[telemetry.engine_id] = sequence
    last_sequences.move_to_end(telemetry.engine_id)
    while len(last_sequences) > MAX_CACHED_ENGINE_SEQUENCES:
        last_sequences.popitem(last=False)
    return sequence


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker. reason_code={reason_code}")

    client.subscribe(MQTT_TOPIC, qos=1)

    print(f"Subscribed to: {MQTT_TOPIC}")


def on_message(client, userdata, message):
    try:
        payload = json.loads(
            message.payload.decode("utf-8")
        )

        telemetry = EngineTelemetry.model_validate(payload)

        sequence = store_telemetry(telemetry)

        print(
            f"[STORED] "
            f"seq={sequence} | "
            f"RPM={telemetry.rpm:.1f} | "
            f"CHT={telemetry.cht_c:.1f}°C | "
            f"EGT={telemetry.egt_c:.1f}°C | "
            f"Vibration={telemetry.vibration_g:.3f} g"
        )

    except Exception as exc:
        print(f"[ERROR] {exc}")

        if db_connection:
            db_connection.rollback()


def main():
    connect_database()

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="aerotwin-ingestion-service",
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

    print("Starting ingestion service...")

    try:
        client.loop_forever()

    except KeyboardInterrupt:
        print("\nStopping ingestion service...")

    finally:
        if db_connection:
            db_connection.close()
            print("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()