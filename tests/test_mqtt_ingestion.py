from collections import OrderedDict
from datetime import datetime, timezone

import services.ingestion.mqtt_ingestion as ingestion
from packages.contracts.telemetry import EngineTelemetry


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.sequence = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        if query.lstrip().startswith("SELECT MAX(sequence)"):
            self.sequence = self.connection.last_sequences.get(params[0])
        else:
            self.connection.inserts.append(params)

    def fetchone(self):
        return (self.sequence,)


class FakeConnection:
    def __init__(self, last_sequences):
        self.last_sequences = last_sequences
        self.inserts = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


def make_telemetry(engine_id, sequence):
    return EngineTelemetry(
        vehicle_id="UAV-DEMO-001",
        engine_id=engine_id,
        mission_id="MISSION-TEST",
        sequence=sequence,
        timestamp=datetime.now(timezone.utc),
        rpm=2520.0,
        cht_c=170.0,
        egt_c=690.0,
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


def test_persisted_sequence_continues_after_simulator_restart(monkeypatch):
    connection = FakeConnection({"ENGINE-001": 13_212, "ENGINE-002": None})
    monkeypatch.setattr(ingestion, "db_connection", connection)
    monkeypatch.setattr(ingestion, "last_sequences", OrderedDict())

    first = ingestion.store_telemetry(make_telemetry("ENGINE-001", 0))
    second = ingestion.store_telemetry(make_telemetry("ENGINE-001", 1))
    other_engine = ingestion.store_telemetry(make_telemetry("ENGINE-002", 0))

    assert (first, second, other_engine) == (13_213, 13_214, 0)
    assert [row["sequence"] for row in connection.inserts] == [
        13_213,
        13_214,
        0,
    ]
    assert connection.commits == 3
