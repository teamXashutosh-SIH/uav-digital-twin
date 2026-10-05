\# AeroTwin



\## AI-Enabled Real-Time Digital Twin System for Health Monitoring, Fault Prediction \& Mission Reliability Enhancement of Aero Piston Engines used in MALE UAVs



AeroTwin is a software-based Digital Twin demonstrator for monitoring the health and operating condition of an aero piston engine used in a MALE UAV.



The system combines engine telemetry, Digital Twin based expected-state estimation, health monitoring, trend analysis, machine-learning anomaly detection, fault diagnosis, degradation tracking, Remaining Useful Life (RUL) estimation, mission simulation, mission replay and maintenance advisory.



> \*\*Development Status:\*\* Engineering demonstrator / research prototype.

> The current implementation uses synthetic engine telemetry and development-stage models. It is not validated or certified for real aircraft operation.



\---



\## 1. Problem Statement



Conventional engine monitoring systems often depend heavily on fixed thresholds and reactive fault detection.



AeroTwin aims to demonstrate a more intelligent monitoring architecture by combining:



\- Engine telemetry

\- Digital Twin based expected-state estimation

\- Health monitoring

\- Trend analysis

\- Machine-learning anomaly detection

\- Fault diagnosis

\- Degradation estimation

\- Remaining Useful Life estimation

\- Mission simulation

\- Mission replay

\- Maintenance advisory

\- Engineering dashboard visualization



The objective is to demonstrate a transition from simple threshold monitoring toward condition-aware and predictive engine health monitoring.



\---



\## 2. System Architecture



The overall AeroTwin workflow is:



```text

┌──────────────────────┐

│ Engine / Simulator   │

└──────────┬───────────┘

&#x20;          │

&#x20;          ▼

┌──────────────────────┐

│ Telemetry Generation │

│ \& Data Ingestion     │

└──────────┬───────────┘

&#x20;          │

&#x20;          ▼

┌────────────────────────────┐

│ Digital Twin               │

│ Expected State Estimation  │

└────────────┬───────────────┘

&#x20;            │

&#x20;            ▼

┌────────────────────────────┐

│ Observed vs Expected       │

│ Deviation / Residuals      │

└────────────┬───────────────┘

&#x20;            │

&#x20;      ┌─────┴──────┐

&#x20;      ▼            ▼

┌─────────────┐ ┌────────────────┐

│ Health      │ │ ML Anomaly     │

│ Monitoring  │ │ Detection      │

└──────┬──────┘ └───────┬────────┘

&#x20;      │                │

&#x20;      └───────┬────────┘

&#x20;              ▼

&#x20;     ┌──────────────────┐

&#x20;     │ Diagnostic Fusion│

&#x20;     │ \& Fault Diagnosis│

&#x20;     └────────┬─────────┘

&#x20;              │

&#x20;       ┌──────┴──────┐

&#x20;       ▼             ▼

┌──────────────┐ ┌──────────────┐

│ Degradation  │ │ RUL          │

│ Tracking     │ │ Estimation   │

└──────┬───────┘ └──────┬───────┘

&#x20;      │                │

&#x20;      └───────┬────────┘

&#x20;              ▼

&#x20;     ┌──────────────────┐

&#x20;     │ Mission Simulation│

&#x20;     │ \& Mission Replay  │

&#x20;     └────────┬─────────┘

&#x20;              │

&#x20;              ▼

&#x20;     ┌──────────────────┐

&#x20;     │ AeroTwin         │

&#x20;     │ Engineering      │

&#x20;     │ Dashboard        │

&#x20;     └──────────────────┘

3\. Core Engine Parameters



AeroTwin works with the following telemetry:



Parameter	Unit	Purpose

RPM	rpm	Engine rotational speed

CHT	°C	Cylinder Head Temperature

EGT	°C	Exhaust Gas Temperature

Oil Pressure	kPa	Lubrication-system condition

Oil Temperature	°C	Thermal/lubrication condition

Fuel Flow	GPH	Fuel consumption behaviour

Vibration	g	Mechanical vibration monitoring

Battery Voltage	V	Electrical system monitoring

Alternator Current	A	Electrical generation monitoring

Injection Timing	deg	Engine control/combustion parameter

Altitude	m	Operating environment

Ambient Temperature	°C	Environmental condition

Throttle	%	Engine operating demand



The Digital Twin uses operating conditions such as throttle, altitude and ambient temperature to estimate expected engine behaviour.



The basic comparison is:



Deviation = Observed State - Expected State



These deviations are used by the health, trend, diagnostic and ML layers.



4\. Digital Twin



The Digital Twin estimates the expected engine state for the current operating condition.



Inputs

Throttle %

Altitude

Ambient Temperature

Expected engine state

RPM

CHT

EGT

Oil Pressure

Oil Temperature

Fuel Flow

Vibration



The system compares:



Observed Engine Behaviour

&#x20;         VS

Expected Engine Behaviour



This produces parameter-level deviations/residuals.



The current performance model is a development-stage physics-inspired model and is not a validated thermodynamic model of a certified aircraft engine.



5\. Health Monitoring



The health-monitoring layer evaluates engine parameters and classifies them as:



NORMAL

WARNING

CRITICAL



The monitored parameters include:



RPM

CHT

EGT

Oil pressure

Oil temperature

Fuel flow

Vibration



An aggregate health score is represented on a 0–100 scale.



The system also maintains parameter-level status so that an individual abnormal parameter can be investigated without automatically treating every transient as a permanent engine failure.



6\. Operating-Condition Awareness



AeroTwin considers operating transitions before interpreting abnormalities as faults.



Examples include:



Startup

Rapid throttle increase

Rapid throttle decrease

Altitude transition

Temperature transition



Conceptually:



Operating Transition

&#x20;       ↓

Temporary parameter deviation

&#x20;       ↓

Operating-condition tracker

&#x20;       ↓

Transient-aware interpretation

&#x20;       ↓

Reduced false fault classification



This is important because engine parameters can temporarily deviate from their steady-state expectations during changes in operating conditions.



7\. AI / ML Anomaly Detection



AeroTwin includes an unsupervised anomaly detector using:



Scikit-learn Isolation Forest



The model learns the statistical pattern of normal synthetic engine operation.



Training data



The current development implementation trains using approximately:



300 synthetic normal-operation samples



generated across multiple operating regions involving:



Throttle

Altitude

Ambient temperature

ML feature vector



The current anomaly detector uses 16 features:



7 Raw Telemetry Features

\+

7 Digital Twin Deviation Features

\+

2 Thermal Trend Features

Raw telemetry

RPM

CHT

EGT

Oil Pressure

Oil Temperature

Fuel Flow

Vibration

Digital Twin deviations

RPM deviation

CHT deviation

EGT deviation

Oil pressure deviation

Oil temperature deviation

Fuel-flow deviation

Vibration deviation

Trend features

EGT trend slope

CHT trend slope



The ML layer provides an additional anomaly signal rather than replacing the Digital Twin and physics-based health assessment.



8\. Diagnostic Fusion



AeroTwin combines multiple sources of evidence:



Digital Twin / Physics Health

&#x20;         +

Thermal Trend Analysis

&#x20;         +

ML Anomaly Detection

&#x20;         +

Fault Classification



The diagnostic layer prioritizes strong physics-based health and thermal evidence.



ML provides an additional anomaly signal when the physics-based health assessment remains normal.



9\. Fault Diagnosis



The current development system supports these fault scenarios:



1\. Overheating

2\. Low Oil Pressure

3\. Abnormal Vibration

4\. Combustion Anomaly

5\. Sensor Drift



Each diagnosis can provide:



Fault

Confidence

Severity

Evidence

Recommended Action



Example:



Fault:

OVERHEATING



Evidence:

\- Elevated EGT deviation

\- Elevated CHT deviation

\- Increased oil temperature



Recommendation:

Inspect thermal, combustion and lubrication behaviour.

10\. Degradation Tracking



AeroTwin tracks a development-stage degradation index.



The system considers abnormal behaviour and trends involving parameters such as:



EGT

CHT

Oil pressure

Vibration

Performance-related deviations



The degradation layer can identify developing abnormal behaviour and provide a trend indication.



11\. Remaining Useful Life (RUL)



AeroTwin includes a development-stage RUL estimator.



The system reports:



RUL in hours

RUL confidence

RUL status

Degradation index

Degradation rate



Example:



RUL:

5000 h



Status:

STABLE



Confidence:

90%



The current RUL implementation is a prototype estimator and should not be interpreted as a certified aircraft maintenance prediction.



Real-world deployment would require:



Long-term engine datasets

Validated degradation models

Real failure histories

Engine-specific calibration

Extensive validation and verification

12\. Mission Simulation



AeroTwin supports controlled mission scenarios.



Environmental scenarios

Normal Mission

Hot Weather

High Altitude

Rapid Throttle

Fault scenarios

Overheating

Low Oil Pressure

Abnormal Vibration

Combustion Anomaly

Sensor Drift



Mission scenarios allow the complete Digital Twin pipeline to be evaluated under controlled conditions.



13\. Mission Replay



After a mission is executed, AeroTwin can replay mission telemetry and health evolution.



Replay allows engineers to inspect:



Mission timeline

Engine parameters

Health score

Degradation

RUL

Fault diagnosis

Operating conditions



This supports post-flight engineering analysis.



14\. Dashboard



The AeroTwin dashboard contains engineering-oriented modules:



Dashboard

Live Telemetry

Engine Health

AI Diagnostics

3D Engine View

Flight \& Mission

Maintenance

Reports

Settings



The dashboard is designed to expose both real-time monitoring and deeper engineering diagnostics.



15\. Technology Stack

Frontend

React

Vite

JavaScript / JSX

Lucide React

CSS

Backend

Python

FastAPI

Pydantic

Numerical / Digital Twin Processing

Python

NumPy



Machine Learning

Scikit-learn

Isolation Forest

Messaging

MQTT

Paho MQTT

Database

PostgreSQL

Infrastructure

Docker

Docker Compose

Testing

Pytest

Version Control

Git

GitHub

16\. Project Structure

AeroTwin/

│

├── apps/

│   └── dashboard/

│       ├── src/

│       │   ├── App.jsx

│       │   ├── App.css

│       │   ├── index.css

│       │   └── main.jsx

│       └── package.json

│

├── services/

│   ├── api/

│   │   └── main.py

│   │

│   ├── simulator/

│   │   ├── engine\_simulator.py

│   │   └── mqtt\_publisher.py

│   │

│   └── ml/

│       ├── anomaly\_detector.py

│       └── features.py

│

├── packages/

│   ├── contracts/

│   │   └── telemetry.py

│   │

│   ├── digital\_twin/

│   │   ├── performance\_model.py

│   │   └── core.py

│   │

│   ├── health/

│   │   ├── monitor.py

│   │   └── diagnostics.py

│   │

│   └── simulation/

│

├── infra/

│   ├── docker-compose.yml

│   └── mosquitto.conf

│

├── tests/

│

└── docs/

17\. API



The backend is implemented using FastAPI.



Important API capabilities include:



GET  /

GET  /health

GET  /engine/status

GET  /telemetry/latest

GET  /telemetry/recent



GET  /mission/scenarios



POST /mission/run/{scenario\_id}

GET  /mission/replay/{scenario\_id}



POST /simulation/clear

POST /simulation/fault

GET /simulation/fault

GET /simulation/fault-events

POST /missions/start

POST /missions/end

GET /missions

GET /missions/current?engine_id=ENGINE-001

GET /missions/{mission_id}

GET /missions/{mission_id}/telemetry

GET /missions/{mission_id}/events

GET /missions/{mission_id}/replay

GET /engines

GET /notifications

POST /simulation/scenario

Mission lifecycle and telemetry are scoped by engine. ENGINE-001 keeps its
MISSION-DEMO-001 default; other engines can be started through the mission
lifecycle API. Completed mission telemetry, fault events, and replay timelines
are retained in the existing PostgreSQL telemetry and fault-event tables.

`POST /simulation/scenario` runs a supported synthetic scenario through the
existing EngineSimulator/MissionAnalysisPipeline, records its telemetry and
fault intervals, and returns a persistent mission ID for stored replay.
Live fault injection remains available through `POST /simulation/fault` and
`POST /simulation/clear`; notifications are served from the historical fault
events.

The engine performance model, simulator, fault thresholds, health/degradation
calculations, and RUL estimates are synthetic/development models. They are not
validated or certified for aircraft-engine operation.


FastAPI provides interactive API documentation through Swagger/OpenAPI.



18\. Running the Project

Backend



From the project root:



.venv\\Scripts\\Activate.ps1



Start the API:



python -m uvicorn services.api.main:app --reload



Backend:



http://127.0.0.1:8000



API documentation:



http://127.0.0.1:8000/docs

Frontend



Open another terminal:



cd apps/dashboard

npm install

npm run dev



Open the Vite URL shown in the terminal.



19\. Infrastructure



AeroTwin uses Docker Compose for infrastructure services.



Development infrastructure includes:



MQTT Broker

PostgreSQL



Start infrastructure:



docker compose -f infra/docker-compose.yml up -d



Check running containers:



docker ps

20\. Testing



From the repository root:



python -m pytest



The test suite covers important Digital Twin, health, mission and ML components.



21\. Demonstration Flow



A typical AeroTwin demonstration can follow this sequence:



Normal Mission

Normal Mission

&#x20;     ↓

Telemetry

&#x20;     ↓

Digital Twin

&#x20;     ↓

Healthy Engine

&#x20;     ↓

Stable Degradation

&#x20;     ↓

Stable RUL

Overheating

Normal Operation

&#x20;     ↓

Thermal degradation

&#x20;     ↓

EGT / CHT deviation increases

&#x20;     ↓

Health deteriorates

&#x20;     ↓

Overheating detected

&#x20;     ↓

Maintenance advisory

Low Oil Pressure

Normal Operation

&#x20;     ↓

Oil pressure decreases

&#x20;     ↓

Twin residual increases

&#x20;     ↓

Health warning/critical state

&#x20;     ↓

Low Oil Pressure diagnosis

Abnormal Vibration

Normal Operation

&#x20;     ↓

Vibration increases

&#x20;     ↓

Mechanical anomaly

&#x20;     ↓

Fault diagnosis

Mission Replay

Mission execution

&#x20;     ↓

Telemetry history

&#x20;     ↓

Replay

&#x20;     ↓

Timeline analysis

&#x20;     ↓

Post-flight diagnosis

22\. Engineering Limitations



The current AeroTwin implementation is a development-stage software demonstrator.



Important limitations:



Telemetry is synthetic.

Engine performance equations are development-stage models.

The ML model is trained on synthetic normal-operation data.

RUL estimation is a prototype.

Fault thresholds are development assumptions.

No certification claim is made.

Real aircraft integration requires validated engine-specific data.

Real-world deployment requires hardware-in-the-loop testing and extensive verification and validation.



AeroTwin should therefore be treated as an engineering research and demonstration platform rather than an operational aircraft control or certified maintenance system.



23\. Future Development



Potential future development includes:



Real ECU / FADEC / CAN telemetry integration

Real engine test-cell datasets

Validated thermodynamic engine models

Physics-informed machine learning

Advanced time-series models

Improved RUL estimation

Hardware-in-the-loop testing

Edge AI deployment

Onboard lightweight inference

Explainable AI

Secure telemetry

Federated learning

Engine-specific model calibration

Digital Twin synchronization with physical test engines

Cloud-based fleet analytics

24\. Validation Roadmap



A real-world deployment would require a validation process such as:



Data Validation

&#x20;       ↓

Model Validation

&#x20;       ↓

Hardware-in-the-Loop Testing

&#x20;       ↓

Engine Test-Cell Validation

&#x20;       ↓

Verification \& Validation

&#x20;       ↓

Safety Assessment

&#x20;       ↓

Certification / Regulatory Compliance

25\. Project Objective



The long-term objective of AeroTwin is to demonstrate how Digital Twin technology, AI/ML and real-time telemetry can be combined to move aero-engine health monitoring from:



Reactive Monitoring

&#x20;       ↓

Condition Monitoring

&#x20;       ↓

Predictive Diagnostics

&#x20;       ↓

Predictive Maintenance

26\. Project Status

Component	Status

Telemetry Contract	Implemented

Engine Simulator	Implemented

Digital Twin	Implemented

Health Monitoring	Implemented

Operating Condition Tracking	Implemented

Fault Simulation	Implemented

Fault Diagnosis	Implemented

ML Anomaly Detection	Implemented

Degradation Tracking	Implemented

RUL Estimation	Prototype

Mission Simulation	Implemented

Mission Replay	Implemented

FastAPI Backend	Implemented

React Dashboard	Implemented

MQTT Infrastructure	Development

PostgreSQL Infrastructure	Development

Real Engine Integration	Future

Certified Aircraft Deployment	Future

27\. Safety Disclaimer



AeroTwin is a development-stage research and engineering demonstrator.



The current system uses synthetic telemetry and simplified/development-stage models where validated aircraft-engine data and models are unavailable.



AeroTwin is not a certified aircraft monitoring, control or maintenance system and must not be used to make real aircraft operational or maintenance decisions.



Project Information



Project: AeroTwin



Domain: AI + Digital Twin + UAV Aero-Engine Health Monitoring



Application: MALE UAV Aero Piston Engine



Status: Engineering Demonstrator



Repository: uav-digital-twin



License



This project is currently maintained as a project/research repository.
