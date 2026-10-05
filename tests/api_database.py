from sqlalchemy import text

from services.api.db.database import engine


def test_database_connection():

    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT COUNT(*) FROM engine_telemetry")
        )

        count = result.scalar_one()

    print("\n--- API DATABASE TEST ---")
    print(f"Telemetry rows: {count}")

    assert count >= 0

    print("FastAPI database connection successful.")