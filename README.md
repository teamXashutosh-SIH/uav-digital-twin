# AeroTwin

## AI-Enabled Real-Time Digital Twin for UAV Engine Health Monitoring

AeroTwin is an engineering demonstrator for real-time health monitoring, anomaly detection, fault diagnosis, degradation tracking, and maintenance decision support for aero piston engines used in MALE UAVs.

The system combines a Digital Twin-based expected-state model with telemetry analysis and machine-learning anomaly detection to move beyond conventional threshold-based engine monitoring.

## Key Features

- **Real-Time Engine Monitoring**
  - RPM, CHT, EGT, oil pressure, oil temperature, fuel flow, vibration, and electrical parameters
  - Operating context including altitude, ambient temperature, and throttle

- **Digital Twin**
  - Estimates expected engine behaviour under current operating conditions
  - Calculates observed-versus-expected deviations for health assessment

- **Engine Health Monitoring**
  - Overall engine health scoring
  - Thermal, lubrication, combustion, mechanical, electrical, and sensor health states

- **AI/ML Anomaly Detection**
  - Machine-learning-based detection of abnormal operating behaviour
  - Combines telemetry features, Digital Twin residuals, and thermal trends

- **Fault Diagnosis**
  - Controlled detection of overheating, low oil pressure, abnormal vibration, combustion anomaly, and sensor drift
  - Confidence, severity, supporting evidence, and recommended actions

- **Live Fault Injection**
  - Controlled fault injection through the dashboard
  - Real-time MQTT-based simulation and telemetry response

- **Mission Simulation**
  - Normal mission
  - Hot weather
  - High altitude
  - Rapid throttle conditions

- **Mission Replay & Post-Flight Analysis**
  - Replay completed missions
  - Review parameter behaviour and developing anomalies

- **Degradation & RUL**
  - Degradation trend monitoring
  - Remaining Useful Life estimation for predictive maintenance

- **3D Engine Visualization**
  - Interactive Digital Twin representation
  - Subsystem-level health and diagnostic visualization

- **Maintenance Decision Support**
  - Converts detected conditions into actionable maintenance recommendations

- **Engineering Dashboard**
  - React-based interface for telemetry, health, diagnostics, simulation, missions, maintenance, and reports

## Technology Stack

- **Frontend:** React, Vite
- **Backend:** Python, FastAPI
- **Digital Twin & Simulation:** Python
- **Machine Learning:** Scikit-learn
- **Real-Time Messaging:** MQTT
- **Database:** PostgreSQL
- **Containerization:** Docker
- **Version Control:** Git & GitHub

## Current Prototype Status

AeroTwin currently demonstrates an end-to-end development pipeline using synthetic telemetry and controlled fault scenarios.

The prototype successfully demonstrates:

- Real-time telemetry monitoring
- Digital Twin state estimation
- Engine health assessment
- ML-assisted anomaly detection
- Fault diagnosis
- Live fault injection
- Mission simulation and replay
- Degradation and RUL estimation
- Maintenance recommendations
- Interactive engineering visualization

The current Digital Twin and fault models are **development models and are not validated for operational aircraft use**.

## Future Scope

The next stage of AeroTwin can focus on:

- Integration with real ECU, FADEC, CAN, or flight-test telemetry
- Calibration and validation using real engine test-cell data
- Real-world fault and degradation datasets
- Improved physics-informed Digital Twin models
- More robust RUL and remaining-life prediction
- Lightweight Edge AI for onboard UAV deployment
- Secure telemetry using authentication and encryption
- Fleet-level engine health monitoring
- Continuous model improvement and deployment
- Integration with real maintenance and operational workflows

## Disclaimer

AeroTwin is currently an engineering prototype and research demonstrator. Its synthetic telemetry, Digital Twin models, fault models, anomaly detection, and RUL estimates require validation against real engine and flight-test data before any operational aviation use.

## Project Goal

AeroTwin aims to transform engine telemetry into actionable health intelligence and support a transition from reactive fault monitoring toward predictive and condition-based maintenance.

**Monitor. Predict. Prevent.**
