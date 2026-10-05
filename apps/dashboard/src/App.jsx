import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  Bell,
  Box,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Clock3,
  Cpu,
  Droplets,
  FileText,
  Fuel,
  Gauge,
  HeartPulse,
  Menu,
  Moon,
  Pause,
  Palette,
  Plane,
  Play,
  Radio,
  RotateCcw,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Sun,
  Thermometer,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

const NAV_ITEMS = [
  { id: "Dashboard", icon: BarChart3 },
  { id: "Live Telemetry", icon: Activity },
  { id: "Engine Health", icon: HeartPulse },
  { id: "AI Diagnostics", icon: Sparkles },
  { id: "3D Engine View", icon: Box },
  { id: "Flight & Mission", icon: Plane },
  { id: "Maintenance", icon: Wrench },
  { id: "Reports", icon: FileText },
  { id: "Settings", icon: Settings },
];

const THEMES = [
  { id: "sky", label: "Aero Sky", icon: Sun },
  { id: "ice", label: "Ice Blue", icon: Palette },
  { id: "midnight", label: "Midnight", icon: Moon },
  { id: "slate", label: "Slate", icon: Palette },
  { id: "warm", label: "Warm White", icon: Sun },
];

const FAULT_SCENARIO_IDS = new Set([
  "overheating",
  "low_oil_pressure",
  "abnormal_vibration",
  "combustion_anomaly",
  "sensor_drift",
]);

const FAULT_LABELS = {
  overheating: "Overheating",
  low_oil_pressure: "Low Oil Pressure",
  abnormal_vibration: "Abnormal Vibration",
  combustion_anomaly: "Combustion Anomaly",
  sensor_drift: "Sensor Drift",
};

const ENVIRONMENT_SCENARIO_IDS = new Set([
  "normal_mission",
  "hot_weather",
  "high_altitude",
  "rapid_throttle",
]);

// These descriptions mirror the controlled scenarios implemented by the
// backend simulator. They are used only for clearer dashboard presentation.
const SCENARIO_DISPLAY = {
  normal_mission: { label: "Normal Mission", group: "Mission Conditions", detail: "Climb â†’ cruise â†’ descent under nominal conditions." },
  hot_weather: { label: "Hot Weather", group: "Mission Conditions", detail: "High ambient temperature operating condition." },
  high_altitude: { label: "High Altitude", group: "Mission Conditions", detail: "High-altitude operating condition." },
  rapid_throttle: { label: "Rapid Throttle", group: "Mission Conditions", detail: "Rapid throttle transitions." },
  overheating: { label: "Overheating", group: "Fault / Degradation", detail: "Progressive thermal fault injection." },
  low_oil_pressure: { label: "Low Oil Pressure", group: "Fault / Degradation", detail: "Lubrication pressure fault injection." },
  abnormal_vibration: { label: "Abnormal Vibration", group: "Fault / Degradation", detail: "Mechanical vibration fault injection." },
  combustion_anomaly: { label: "Combustion Anomaly", group: "Fault / Degradation", detail: "Combustion instability fault injection." },
  sensor_drift: { label: "Sensor Drift", group: "Fault / Degradation", detail: "Sensor measurement drift fault injection." },
};

function displayScenarioName(scenario) {
  return SCENARIO_DISPLAY[scenario?.id]?.label || scenario?.name || String(scenario?.id || "Scenario");
}

function formatNotificationTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function scenarioGroup(scenario) {
  if (SCENARIO_DISPLAY[scenario?.id]?.group) return SCENARIO_DISPLAY[scenario.id].group;
  return FAULT_SCENARIO_IDS.has(scenario?.id) ? "Fault / Degradation" : "Mission Conditions";
}

function expectedOperatingPoint(frame, liveEngine = null) {
  const replayExpected = {
    rpm: n(frame?.expected_rpm, 0),
    cht_c: n(frame?.expected_cht_c, 0),
    egt_c: n(frame?.expected_egt_c, 0),
    oil_pressure_kpa: n(frame?.expected_oil_pressure_kpa, 0),
    oil_temperature_c: n(frame?.expected_oil_temperature_c, 0),
    fuel_flow_gph: n(frame?.expected_fuel_flow_gph, 0),
    vibration_g: n(frame?.expected_vibration_g, 0),
  };
  if (frame && replayExpected.rpm > 0 && replayExpected.cht_c > 0) {
    return replayExpected;
  }

  const liveExpected = liveEngine?.expected || {};
  const hasLiveExpected = Object.keys(liveExpected).length > 0;
  if (hasLiveExpected && !frame?.mission_time_seconds) {
    return {
      rpm: n(liveExpected.rpm, 2520),
      cht_c: n(liveExpected.cht_c, 172),
      egt_c: n(liveExpected.egt_c, 682.5),
      oil_pressure_kpa: n(liveExpected.oil_pressure_kpa, 481.6),
      oil_temperature_c: n(liveExpected.oil_temperature_c, 91),
      fuel_flow_gph: n(liveExpected.fuel_flow_gph, 9.7),
      vibration_g: n(liveExpected.vibration_g, 0.25),
    };
  }

  // Same nominal performance equations used by
  // packages/digital_twin/performance_model.py.
  const throttlePct = clamp(n(frame?.throttle_pct, 60), 0, 100);
  const altitude = Math.max(0, n(frame?.altitude_m, 2000));
  const ambient = n(frame?.ambient_temperature_c, 25);
  const throttle = throttlePct / 100;

  const rpm = 1200 + throttlePct * 22;
  const cht_c = ambient + 85 + 100 * throttle + (altitude / 10000) * 10;
  const egt_c = 400 + 450 * throttle + ambient * 0.5;
  const oil_pressure_kpa = 280 + rpm * 0.08;
  const oil_temperature_c = 70 + throttlePct * 0.35;
  const fuel_flow_gph = 2.5 + throttlePct * 0.12;

  return { rpm, cht_c, egt_c, oil_pressure_kpa, oil_temperature_c, fuel_flow_gph, vibration_g: 0.25 };
}

function inferReplayAmbient(scenarioId, timeSeconds, currentAmbient = 25) {
  const t = n(timeSeconds, 0);
  if (scenarioId === "hot_weather") return t <= 40 ? 45 : 42;
  if (scenarioId === "high_altitude") return t <= 45 ? 5 : -5;
  if (scenarioId === "normal_mission") {
    if (t <= 30) return 20;
    if (t <= 90) return 15;
    return 22;
  }
  if (scenarioId === "overheating") return t <= 30 ? 25 : 30;
  return currentAmbient;
}

const FALLBACK_ENGINE = {
  engine_id: "ENGINE-001",
  mission_id: "MISSION-DEMO-001",
  engine_state: {
    operating_mode: "CRUISE",
    overall_health: "CRITICAL",
    thermal_state: "CRITICAL",
    lubrication_state: "CRITICAL",
    combustion_state: "CRITICAL",
    mechanical_state: "CRITICAL",
    electrical_state: "NORMAL",
    sensor_confidence: "MEDIUM",
  },
  health_score: 0,
  status: "CRITICAL",
  anomaly_score: 1,
  ml_anomaly: { score: 1, is_anomaly: true },
  diagnostic: {
    status: "CRITICAL",
    confidence: 0.95,
    primary_signal: "PHYSICS_HEALTH",
    message: "Critical engine condition detected.",
  },
  fault_diagnosis: {
    fault: "OVERHEATING",
    confidence: 0.95,
    severity: "CRITICAL",
    evidence: [
      "EGT deviation is elevated",
      "CHT deviation is elevated",
      "Oil temperature is above expected",
    ],
    recommendation:
      "Reduce engine load and inspect cooling, combustion and lubrication systems.",
  },
  degradation: {
    index: 0.592,
    level: "MODERATE",
    trend: "STABLE",
    trend_rate: 0,
  },
  rul: {
    rul_hours: 5000,
    confidence: 0.8,
    status: "STABLE",
    degradation_index: 0.592,
  },
  parameters: {},
  deviation: {},
  expected: {},
  trends: {},
};

const FALLBACK_TELEMETRY = {
  rpm: 2526,
  cht_c: 253,
  egt_c: 866,
  oil_pressure_kpa: 470,
  oil_temperature_c: 127,
  fuel_flow_gph: 9.7,
  vibration_g: 0.59,
  altitude_m: 2000,
  ambient_temperature_c: 25,
};

function n(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function pick(object, paths, fallback = 0) {
  for (const path of paths) {
    const parts = path.split(".");
    let value = object;
    for (const part of parts) {
      value = value?.[part];
    }
    if (value !== undefined && value !== null) return value;
  }
  return fallback;
}

function actualValue(engine, telemetry, key, expectedKey, deviationKey, fallback) {
  const direct = pick(telemetry, [key], undefined);
  if (direct !== undefined) return n(direct, fallback);

  const status = engine || {};
  const expected = n(pick(status, [`expected.${expectedKey}`, expectedKey], 0), 0);
  const deviation = n(
    pick(status, [`deviation.${deviationKey}`, deviationKey], 0),
    0
  );

  if (expected || deviation) return expected + deviation;
  return fallback;
}

function statusClass(value) {
  const text = String(value || "NORMAL").toUpperCase();
  if (text.includes("CRITICAL") || text.includes("FAULT")) return "critical";
  if (text.includes("WARNING") || text.includes("MEDIUM")) return "warning";
  return "normal";
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function GaugeRing({ value, label = "Health Score", tone = "blue" }) {
  const safe = clamp(n(value), 0, 100);
  return (
    <div className={`gauge-ring ${tone}`} style={{ "--progress": `${safe * 3.6}deg` }}>
      <div className="gauge-inner">
        <strong>{Math.round(safe)}</strong>
        <span>%</span>
        <small>{label}</small>
      </div>
    </div>
  );
}

function StatusBadge({ value, compact = false }) {
  const cls = statusClass(value);
  return (
    <span className={`status-badge ${cls} ${compact ? "compact" : ""}`}>
      <span className="status-dot" />
      {String(value || "NORMAL").toUpperCase()}
    </span>
  );
}

function SectionHeader({ icon: Icon, title, subtitle, action, onAction, tone = "blue" }) {
  return (
    <div className="section-header">
      <div className={`section-icon ${tone}`}>
        <Icon size={20} strokeWidth={2.2} />
      </div>
      <div className="section-heading">
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action && (
        <button className="text-button" onClick={onAction} type="button">
          {action}
          <ChevronRight size={16} />
        </button>
      )}
    </div>
  );
}

function InfoCard({ icon: Icon, label, value, sub, tone = "blue", onClick }) {
  return (
    <button className={`info-card ${tone}`} onClick={onClick} type="button">
      <div className="info-icon">
        <Icon size={23} />
      </div>
      <div className="info-content">
        <span>{label}</span>
        <strong title={String(value)}>{value}</strong>
        <small>{sub}</small>
      </div>
      <ChevronRight className="info-arrow" size={18} />
    </button>
  );
}

function ParameterCard({ label, value, unit, target, state, icon: Icon, onClick }) {
  const stateCls = statusClass(state);
  return (
    <button className="parameter-card" onClick={onClick} type="button">
      <div className="parameter-top">
        <span>{label}</span>
        <Icon size={18} />
      </div>
      <div className="parameter-value">
        <strong>{value}</strong>
        <em>{unit}</em>
      </div>
      <div className="parameter-bar">
        <span className={stateCls} style={{ width: `${clamp(n(state === "CRITICAL" ? 88 : state === "WARNING" ? 65 : 42), 8, 96)}%` }} />
      </div>
      <div className="parameter-status">
        <StatusBadge value={state} compact />
      </div>
      <small>Model target: {target} {unit}</small>
    </button>
  );
}

function TrendChart({ history }) {
  const points = useMemo(() => {
    const source = history.slice(-40);
    if (!source.length) return { egt: "", cht: "" };

    const egtValues = source.map((item) => n(item.egt_c, 0));
    const chtValues = source.map((item) => n(item.cht_c, 0));
    const minE = Math.min(...egtValues);
    const maxE = Math.max(...egtValues);
    const minC = Math.min(...chtValues);
    const maxC = Math.max(...chtValues);

    const toPath = (values, min, max) =>
      values
        .map((value, index) => {
          const x = (index / Math.max(values.length - 1, 1)) * 100;
          const y = 88 - ((value - min) / Math.max(max - min, 1)) * 68;
          return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
        })
        .join(" ");

    return {
      egt: toPath(egtValues, minE, maxE),
      cht: toPath(chtValues, minC, maxC),
    };
  }, [history]);

  return (
    <div className="trend-chart">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Engine parameter trends">
        <line x1="0" y1="20" x2="100" y2="20" className="grid-line" />
        <line x1="0" y1="42" x2="100" y2="42" className="grid-line" />
        <line x1="0" y1="64" x2="100" y2="64" className="grid-line" />
        <line x1="0" y1="86" x2="100" y2="86" className="grid-line" />
        {points.egt && <path d={points.egt} className="trend-line egt-line" />}
        {points.cht && <path d={points.cht} className="trend-line cht-line" />}
      </svg>
      <div className="trend-legend">
        <span><i className="legend-dot egt" /> EGT</span>
        <span><i className="legend-dot cht" /> CHT</span>
      </div>
    </div>
  );
}

function EngineIllustration({
  viewMode,
  setViewMode,
  values = {},
  targetSource = {},
  state = {},
  health = 100,
  diagnosis = {},
}) {
  const [selectedPart, setSelectedPart] = useState("Combustion");
  const exploded = viewMode === "explode";
  const thermal = viewMode === "thermal";
  const sensors = viewMode === "sensors";
  const rotating = viewMode === "rotate";

  const partData = {
    Fan: {
      function: "Air intake and initial flow",
      valueLabel: "RPM",
      value: n(values.rpm, 0).toFixed(0),
      expected: n(targetSource.rpm, 0).toFixed(0),
      unit: "RPM",
      status: state.mechanical_state || "MONITORING",
    },
    Compressor: {
      function: "Compresses incoming air before combustion",
      valueLabel: "RPM",
      value: n(values.rpm, 0).toFixed(0),
      expected: n(targetSource.rpm, 0).toFixed(0),
      unit: "RPM",
      status: state.operating_mode || "MONITORING",
    },
    Combustion: {
      function: "Fuel-air combustion and thermal energy release",
      valueLabel: "EGT",
      value: n(values.egt, 0).toFixed(0),
      expected: n(targetSource.egt_c, 0).toFixed(0),
      unit: "Â°C",
      status: state.combustion_state || "MONITORING",
    },
    Turbine: {
      function: "Extracts energy from hot exhaust flow",
      valueLabel: "CHT",
      value: n(values.cht, 0).toFixed(0),
      expected: n(targetSource.cht_c, 0).toFixed(0),
      unit: "Â°C",
      status: state.thermal_state || "MONITORING",
    },
    Exhaust: {
      function: "Discharges exhaust gases from the engine",
      valueLabel: "EGT",
      value: n(values.egt, 0).toFixed(0),
      expected: n(targetSource.egt_c, 0).toFixed(0),
      unit: "Â°C",
      status: state.thermal_state || "MONITORING",
    },
  };

  const selected = partData[selectedPart] || partData.Combustion;
  const deviation = Number(selected.value) - Number(selected.expected);
  const statusTone = /CRITICAL|FAIL/i.test(String(selected.status))
    ? "critical"
    : /WARNING|HIGH/i.test(String(selected.status))
      ? "warning"
      : "normal";

  const selectPart = (part) => {
    setSelectedPart(part);
    setViewMode("sensors");
  };

  return (
    <div className={`engine-stage-real ${viewMode}`}>
      <div className="engine-grid-glow" />

      <div className="engine-live-hud">
        <span className="engine-live-dot" />
        <strong>LIVE DIGITAL TWIN</strong>
        <span>Health {n(health, 100).toFixed(0)}%</span>
      </div>

      <svg
        className={`engine-svg ${rotating ? "engine-rotating" : ""}`}
        viewBox="0 0 760 390"
        role="img"
        aria-label="Interactive Aero engine digital twin visualization"
      >
        <defs>
          <linearGradient id="metalBody" x1="0" x2="1">
            <stop offset="0" stopColor="#142b45" />
            <stop offset="0.18" stopColor="#7891aa" />
            <stop offset="0.33" stopColor="#d9e2ea" />
            <stop offset="0.48" stopColor="#526b83" />
            <stop offset="0.68" stopColor="#e6edf3" />
            <stop offset="1" stopColor="#344d65" />
          </linearGradient>
          <linearGradient id="darkMetal" x1="0" x2="1">
            <stop offset="0" stopColor="#071625" />
            <stop offset="0.5" stopColor="#46627d" />
            <stop offset="1" stopColor="#0a1828" />
          </linearGradient>
          <radialGradient id="fanMetal">
            <stop offset="0" stopColor="#cfe0ed" />
            <stop offset="0.25" stopColor="#5e7893" />
            <stop offset="0.55" stopColor="#182e45" />
            <stop offset="0.82" stopColor="#9db2c5" />
            <stop offset="1" stopColor="#1a3048" />
          </radialGradient>
          <radialGradient id="hotGlow">
            <stop offset="0" stopColor="#fff4a6" stopOpacity="1" />
            <stop offset="0.22" stopColor="#ffb32e" stopOpacity=".95" />
            <stop offset="0.55" stopColor="#ff5a1f" stopOpacity=".6" />
            <stop offset="1" stopColor="#ff3c16" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="blueEdge" x1="0" x2="1">
            <stop offset="0" stopColor="#32c8ff" />
            <stop offset="1" stopColor="#4d77ff" />
          </linearGradient>
          <filter id="softGlow"><feGaussianBlur stdDeviation="8" /></filter>
          <filter id="shadow"><feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#000" floodOpacity=".45" /></filter>
        </defs>

        <ellipse cx="380" cy="338" rx="320" ry="22" fill="#35aaff" opacity=".12" filter="url(#softGlow)" />
        <ellipse cx="380" cy="342" rx="285" ry="8" fill="#48c8ff" opacity=".25" />

        <g filter="url(#shadow)" transform={exploded ? "translate(0,-5)" : undefined}>
          <path d="M105 165 C125 108 185 82 248 84 L570 101 C620 105 665 137 688 177 L650 222 C620 255 585 274 535 282 L238 292 C172 294 120 259 102 213 Z" fill="url(#metalBody)" stroke="#8fa8bd" strokeWidth="2" />
          <path d="M230 94 L530 108 L557 276 L235 290 Z" fill="#102338" opacity=".52" />
          <path d="M280 104 L485 114 L505 270 L290 280 Z" fill="#0b1726" opacity=".75" />

          <ellipse cx="140" cy="189" rx="77" ry="101" fill="url(#fanMetal)" stroke="#b7d0e2" strokeWidth="3" />
          <ellipse cx="140" cy="189" rx="61" ry="83" fill="#071524" stroke="#52c8ff" strokeWidth="3" />
          <ellipse cx="140" cy="189" rx="18" ry="24" fill="#a7bdcf" stroke="#e7f3fb" strokeWidth="2" />
          {Array.from({ length: 12 }).map((_, i) => (
            <path key={i} d="M140 164 C126 140 111 133 98 136 C111 151 122 174 126 189 C131 184 136 174 140 164Z" fill="#7895ad" stroke="#bfd4e2" strokeWidth="1" transform={`rotate(${i * 30} 140 189)`} />
          ))}
          <circle cx="140" cy="189" r="92" fill="none" stroke="#2fc6ff" strokeOpacity=".28" strokeWidth="5" />

          <g opacity=".9">
            {[0,1,2,3,4].map((i) => <ellipse key={i} cx={218 + i * 17} cy="188" rx="10" ry="83" fill="none" stroke="#93a9bd" strokeWidth="3" />)}
          </g>

          <g>
            <path d="M300 120 L345 118 L362 263 L315 269 Z" fill="#233c55" stroke="#91a9bc" />
            <path d="M355 116 L405 118 L415 258 L367 263 Z" fill="#d2dce4" opacity=".78" />
            <path d="M415 118 L463 123 L470 250 L420 257 Z" fill="#253c53" stroke="#8ea5b9" />
          </g>

          <ellipse cx="392" cy="190" rx="42" ry="64" fill="#151f2b" />
          <ellipse cx="392" cy="190" rx="30" ry="52" fill="url(#hotGlow)" opacity={thermal ? "1" : ".8"} />
          <ellipse cx="392" cy="190" rx="17" ry="36" fill="#ffb52e" opacity=".8" />
          <ellipse cx="392" cy="190" rx="9" ry="24" fill="#fff3ad" opacity=".85" />

          <g opacity=".9">
            {[0,1,2,3,4,5,6].map((i) => <line key={i} x1={480 + i * 9} y1="127" x2={489 + i * 9} y2="250" stroke="#9bb0c1" strokeWidth="4" />)}
          </g>
          <path d="M520 130 C548 139 576 153 601 172 L655 189 L601 205 C577 221 550 235 520 245 Z" fill="url(#darkMetal)" stroke="#91a7ba" />
          <path d="M654 176 L716 190 L654 204 Z" fill="#7c98ae" stroke="#bdd0de" />

          {sensors && [
            [245,112],[318,103],[392,105],[470,112],[540,126],[603,157],[610,221],[525,255],[315,271],[230,254]
          ].map(([cx,cy],i) => (
            <g key={i}>
              <circle cx={cx} cy={cy} r="7" fill="#35d5ff" stroke="#fff" strokeWidth="2" />
              <circle cx={cx} cy={cy} r="15" fill="none" stroke="#35d5ff" strokeOpacity=".45" />
            </g>
          ))}

          {/* Invisible engineering hit zones */}
          {[
            ["Fan", 75, 105, 135, 175],
            ["Compressor", 205, 105, 110, 170],
            ["Combustion", 345, 105, 100, 170],
            ["Turbine", 445, 105, 100, 170],
            ["Exhaust", 555, 125, 150, 115],
          ].map(([name, x, y, width, height]) => (
            <rect
              key={name}
              x={x}
              y={y}
              width={width}
              height={height}
              fill="transparent"
              onClick={() => selectPart(name)}
              style={{ cursor: "pointer" }}
            />
          ))}
        </g>

        <g fontFamily="Inter, Arial, sans-serif" fontSize="12" fontWeight="700">
          {[[128,72,"Fan"],[284,54,"Compressor"],[390,45,"Combustion"],[515,72,"Turbine"],[646,122,"Exhaust"]].map(([x,y,t]) => (
            <g key={t} onClick={() => selectPart(t)} style={{ cursor: "pointer" }}>
              <line x1={x} y1={y + 12} x2={x} y2={y + 31} stroke="#4dc9ff" strokeWidth="1.5" strokeDasharray="3 3" opacity=".75" />
              <rect x={x - 42} y={y - 4} width="84" height="25" rx="12" fill={selectedPart === t ? "#1677e8" : "#0b2844"} stroke="#3cbcff" strokeOpacity=".65" />
              <circle cx={x - 28} cy={y + 8} r="4" fill="#38d4ff" />
              <text x={x - 19} y={y + 12} fill="#eef9ff">{t}</text>
            </g>
          ))}
        </g>
      </svg>

      <div className="engine-controls-real">
        {[
          ["rotate", RotateCcw, "Rotate"],
          ["explode", Box, "Explode"],
          ["thermal", Thermometer, "Thermal"],
          ["sensors", Radio, "Show Sensors"],
        ].map(([id, Icon, label]) => (
          <button key={id} type="button" className={viewMode === id ? "active" : ""} onClick={() => setViewMode(id)}>
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      <div className="engine-inspector">
        <div className="engine-inspector-title">
          <div>
            <span>COMPONENT INSPECTOR</span>
            <strong>{selectedPart}</strong>
          </div>
          <StatusBadge value={selected.status} compact />
        </div>
        <p>{selected.function}</p>
        <div className="engine-inspector-grid">
          <div><span>{selected.valueLabel}</span><strong>{selected.value} {selected.unit}</strong></div>
          <div><span>Expected</span><strong>{selected.expected} {selected.unit}</strong></div>
          <div><span>Deviation</span><strong className={statusTone}>{deviation >= 0 ? "+" : ""}{deviation.toFixed(1)} {selected.unit}</strong></div>
          <div><span>Overall Health</span><strong>{n(health, 100).toFixed(0)}%</strong></div>
        </div>
        {diagnosis?.fault && diagnosis.fault !== "NO_SPECIFIC_FAULT" && (
          <div className="engine-fault-strip">
            <CircleAlert size={15} />
            <span>{diagnosis.fault}</span>
            <small>{Math.round(n(diagnosis.confidence, 0) * 100)}% confidence</small>
          </div>
        )}
      </div>
    </div>
  );
}
function Modal({ title, children, onClose }) {
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>{title}</h3>
            <p>AeroTwin Digital Twin</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            <X size={20} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function App() {
  const [engine, setEngine] = useState(FALLBACK_ENGINE);
  const [telemetry, setTelemetry] = useState(FALLBACK_TELEMETRY);
  const [history, setHistory] = useState([]);
  const [connected, setConnected] = useState(false);
  const [activePage, setActivePage] = useState("Dashboard");
  const [mobileNav, setMobileNav] = useState(false);
  const [viewMode, setViewMode] = useState("rotate");
  const [theme, setTheme] = useState(() => localStorage.getItem("aerotwin-theme") || "sky");
  const [themeOpen, setThemeOpen] = useState(false);
  const [modal, setModal] = useState(null);
  const [notice, setNotice] = useState("");
  const [notificationPanelOpen, setNotificationPanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState(false);
  const [engineIds, setEngineIds] = useState([
    "ENGINE-001",
    "ENGINE-002",
    "ENGINE-003",
  ]);
  const [selectedEngineId, setSelectedEngineId] = useState("ENGINE-001");
  const [currentMission, setCurrentMission] = useState(null);
  const [missionHistory, setMissionHistory] = useState([]);
  const [selectedHistoryMission, setSelectedHistoryMission] = useState("");
  const [missionContextError, setMissionContextError] = useState(false);
  const [faultSelection, setFaultSelection] = useState("overheating");
  const [faultSeverity, setFaultSeverity] = useState(0.8);
  const [faultControlLoading, setFaultControlLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [missionScenarios, setMissionScenarios] = useState([]);
  const [selectedScenario, setSelectedScenario] = useState("normal_mission");
  const [missionResult, setMissionResult] = useState(null);
  const [missionReplay, setMissionReplay] = useState(null);
  const [missionRunning, setMissionRunning] = useState(false);
  const [replayMode, setReplayMode] = useState(false);
  const [replayCursor, setReplayCursor] = useState(0);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [telemetryAvailable, setTelemetryAvailable] = useState(false);
  const [liveEngine, setLiveEngine] = useState(FALLBACK_ENGINE);
  const [liveTelemetry, setLiveTelemetry] = useState(FALLBACK_TELEMETRY);

  const normalizeReplaySamples = (replay, scenarioId) => {
    // The replay API deliberately returns telemetry, health, degradation and
    // RUL as aligned time-series.  Merge those streams into one frame so the
    // dashboard never mixes replay telemetry with stale live-engine state.
    const telemetryPoints = Array.isArray(replay?.telemetry) ? replay.telemetry : [];
    const healthPoints = Array.isArray(replay?.health) ? replay.health : [];
    const degradationPoints = Array.isArray(replay?.degradation) ? replay.degradation : [];
    const rulPoints = Array.isArray(replay?.rul) ? replay.rul : [];
    const faultEvents = Array.isArray(replay?.fault_events) ? replay.fault_events : [];

    const nearestPoint = (points, time, index) => {
      if (!points.length) return {};
      if (points[index]) return points[index];
      return points.reduce((best, point) => {
        const bestDistance = Math.abs(n(best?.time_seconds, 0) - time);
        const pointDistance = Math.abs(n(point?.time_seconds, 0) - time);
        return pointDistance < bestDistance ? point : best;
      }, points[0]);
    };

    return telemetryPoints.map((telemetry, index) => {
      const time = n(telemetry?.time_seconds, index);
      const health = nearestPoint(healthPoints, time, index);
      const degradation = nearestPoint(degradationPoints, time, index);
      const rul = nearestPoint(rulPoints, time, index);

      // Fault events are intervals.  Find the fault that is actually active
      // at this replay timestamp instead of using the mission's final fault.
      const activeFault = faultEvents.find((event) => {
        const start = n(event?.time_seconds, -1);
        const end = n(event?.end_time_seconds ?? event?.time_seconds, start);
        return time >= start && time <= end;
      });

      const ambientTemperature = n(
        telemetry?.ambient_temperature_c,
        inferReplayAmbient(scenarioId, time, 25)
      );

      return {
        ...telemetry,
        ambient_temperature_c: ambientTemperature,
        expected_rpm: n(telemetry?.expected_rpm, 0),
        expected_cht_c: n(telemetry?.expected_cht_c, 0),
        expected_egt_c: n(telemetry?.expected_egt_c, 0),
        expected_oil_pressure_kpa: n(telemetry?.expected_oil_pressure_kpa, 0),
        expected_oil_temperature_c: n(telemetry?.expected_oil_temperature_c, 0),
        expected_fuel_flow_gph: n(telemetry?.expected_fuel_flow_gph, 0),
        expected_vibration_g: n(telemetry?.expected_vibration_g, 0),
        mission_time_seconds: time,
        segment_name: telemetry?.segment_name || health?.segment_name || "MISSION",
        health_score: n(health?.health_score, 100),
        health_status: health?.status || "HEALTHY",
        anomaly_score: n(health?.anomaly_score, 0),
        engine_state: {
          operating_mode: health?.operating_mode || "CRUISE",
          overall_health: health?.status || "HEALTHY",
          thermal_state: health?.thermal_state || "NORMAL",
          lubrication_state: health?.lubrication_state || "NORMAL",
          combustion_state: health?.combustion_state || "NORMAL",
          mechanical_state: health?.mechanical_state || "NORMAL",
          electrical_state: health?.electrical_state || "NORMAL",
          sensor_confidence: health?.sensor_confidence || "HIGH",
        },
        degradation_index: n(degradation?.degradation_index, 0),
        degradation_level: degradation?.degradation_level || "NORMAL",
        degradation_trend: degradation?.trend || "STABLE",
        degradation_rate: n(degradation?.trend_rate, 0),
        rul_hours: n(rul?.rul_hours, 5000),
        rul_samples: n(rul?.rul_samples, 0),
        rul_confidence: n(rul?.confidence, 0.2),
        rul_status: rul?.status || "STABLE",
        fault: activeFault?.fault || "NO_SPECIFIC_FAULT",
        fault_confidence: n(activeFault?.confidence, 0),
        fault_severity: activeFault?.severity || "NORMAL",
        fault_evidence: Array.isArray(activeFault?.evidence) ? activeFault.evidence : [],
        fault_recommendation: activeFault?.recommendation || "Continue monitoring engine parameters.",
      };
    });
  };

  const applyMissionFrame = (frame, summary = null) => {
    if (!frame) return;

    const nextTelemetry = {
      ...liveTelemetry,
      ...frame,
      rpm: n(frame.rpm, liveTelemetry.rpm),
      cht_c: n(frame.cht_c, liveTelemetry.cht_c),
      egt_c: n(frame.egt_c, liveTelemetry.egt_c),
      oil_pressure_kpa: n(frame.oil_pressure_kpa, liveTelemetry.oil_pressure_kpa),
      oil_temperature_c: n(frame.oil_temperature_c, liveTelemetry.oil_temperature_c),
      fuel_flow_gph: n(frame.fuel_flow_gph, liveTelemetry.fuel_flow_gph),
      vibration_g: n(frame.vibration_g, liveTelemetry.vibration_g),
      altitude_m: n(frame.altitude_m, liveTelemetry.altitude_m),
      ambient_temperature_c: n(frame.ambient_temperature_c, liveTelemetry.ambient_temperature_c),
      throttle_pct: n(frame.throttle_pct, liveTelemetry.throttle_pct),
    };

    const activeFault = frame.fault || "NO_SPECIFIC_FAULT";
    const activeSeverity = frame.fault_severity || "NORMAL";
    const activeConfidence = n(frame.fault_confidence, 0);
    const replayStatus = frame.health_status || "HEALTHY";
    const replayHealthScore = n(frame.health_score, 100);

    const nextEngine = {
      ...liveEngine,
      engine_id: liveEngine.engine_id || "ENGINE-001",
      mission_id: summary?.scenario_id || summary?.mission_id || liveEngine.mission_id,
      health_score: replayHealthScore,
      status: replayStatus,
      anomaly_score: n(frame.anomaly_score, 0),
      ml_anomaly: {
        score: n(frame.anomaly_score, 0),
        is_anomaly: n(frame.anomaly_score, 0) >= 0.5,
      },
      engine_state: {
        ...(liveEngine.engine_state || {}),
        ...(frame.engine_state || {}),
        overall_health: replayStatus,
      },
      diagnostic: {
        ...(liveEngine.diagnostic || {}),
        status: replayStatus,
        confidence: activeFault === "NO_SPECIFIC_FAULT" ? 1 : activeConfidence,
        primary_signal: activeFault === "NO_SPECIFIC_FAULT" ? "PHYSICS_HEALTH" : "FAULT_DIAGNOSIS",
        message:
          activeFault === "NO_SPECIFIC_FAULT"
            ? "Engine behavior is within the Digital Twin expected operating envelope."
            : `${activeFault.replaceAll("_", " ")} detected during mission replay.`,
      },
      degradation: {
        ...(liveEngine.degradation || {}),
        index: n(frame.degradation_index, 0),
        level: frame.degradation_level || "NORMAL",
        trend: frame.degradation_trend || "STABLE",
        trend_rate: n(frame.degradation_rate, 0),
      },
      rul: {
        ...(liveEngine.rul || {}),
        rul_hours: n(frame.rul_hours, 5000),
        rul_samples: n(frame.rul_samples, 0),
        degradation_index: n(frame.degradation_index, 0),
        confidence: n(frame.rul_confidence, 0.2),
        status: frame.rul_status || "STABLE",
      },
      fault_diagnosis: {
        fault: activeFault,
        confidence: activeFault === "NO_SPECIFIC_FAULT" ? 1 : activeConfidence,
        severity: activeSeverity,
        evidence:
          frame.fault_evidence?.length
            ? frame.fault_evidence
            : activeFault === "NO_SPECIFIC_FAULT"
              ? ["Telemetry is consistent with the simulated operating condition."]
              : ["Fault event is active at the selected mission timestamp."],
        recommendation: frame.fault_recommendation || "Continue monitoring engine parameters.",
      },
    };

    setTelemetry(nextTelemetry);
    setEngine(nextEngine);
  };

  const loadMissionScenarios = async () => {
    try {
      const response = await fetch(`${API_BASE}/mission/scenarios`, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const scenarios = Array.isArray(data.scenarios) ? data.scenarios : [];
      setMissionScenarios(scenarios);
      if (scenarios.length && !scenarios.some((item) => item.id === selectedScenario)) {
        setSelectedScenario(scenarios[0].id);
      }
    } catch {
      // The live dashboard remains usable if mission discovery is temporarily unavailable.
    }
  };

  const runMission = async () => {
    if (!selectedScenario || missionRunning) return;
    setReplayPlaying(false);
    setMissionRunning(true);
    setNotice(`Running synthetic ${selectedScenario.replaceAll("_", " ")} mission...`);
    try {
      const response = await fetch(`${API_BASE}/simulation/scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario: selectedScenario,
          engine_id: selectedEngineId,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail?.error || "Mission simulation failed");

      const replayResponse = await fetch(
        `${API_BASE}/missions/${encodeURIComponent(data.mission_id)}/replay`,
        { cache: "no-store" }
      );
      if (!replayResponse.ok) throw new Error("Stored mission replay could not be loaded");
      const replayData = await replayResponse.json();
      const samples = normalizeReplaySamples(replayData, selectedScenario);
      const summary = data.summary || {};
      const first = samples[0];
      const final = samples[samples.length - 1];
      const representative = final || first;

      setMissionResult(data);
      setMissionReplay({ ...replayData, samples });
      setReplayCursor(Math.max(0, samples.length - 1));
      setReplayPlaying(false);
      setReplayMode(true);
      if (representative) applyMissionFrame(representative, summary);
      setHistory(samples.map((sample, index) => ({
        timestamp: new Date(sample.timestamp).getTime(),
        rpm: n(sample.rpm),
        cht_c: n(sample.cht_c),
        egt_c: n(sample.egt_c),
        oil_pressure_kpa: n(sample.oil_pressure_kpa),
        oil_temperature_c: n(sample.oil_temperature_c),
        fuel_flow_gph: n(sample.fuel_flow_gph),
        vibration_g: n(sample.vibration_g),
      })).slice(-60));
      loadMissionContext();
      setNotice(`${data.scenario?.name || selectedScenario} mission stored and ready for replay.`);
    } catch (error) {
      setNotice(error.message || "Mission simulation failed.");
    } finally {
      setMissionRunning(false);
    }
  };

  const returnToLive = () => {
    setReplayPlaying(false);
    setReplayMode(false);
    setMissionResult(null);
    setMissionReplay(null);
    setEngine(liveEngine);
    setTelemetry(liveTelemetry);
    setNotice("Returned to live engine telemetry.");
  };

  const selectReplayFrame = (index) => {
    const samples = missionReplay?.samples || [];
    if (!samples.length) return;
    const safeIndex = clamp(Number(index), 0, samples.length - 1);
    setReplayCursor(safeIndex);
    applyMissionFrame(samples[safeIndex], missionResult?.summary);
  };

  const loadData = async () => {
    try {
      const engineParam = encodeURIComponent(selectedEngineId);
      const [statusResponse, telemetryResponse] = await Promise.all([
        fetch(`${API_BASE}/engine/status?engine_id=${engineParam}`, { cache: "no-store" }),
        fetch(`${API_BASE}/telemetry/latest?engine_id=${engineParam}`, { cache: "no-store" }),
      ]);

      if (!statusResponse.ok) throw new Error("Engine status request failed");

      const statusData = await statusResponse.json();
      let telemetryData = {};

      if (statusData.status === "NO_DATA" || !telemetryResponse.ok) {
        setConnected(true);
        setTelemetryAvailable(false);
        setLiveEngine({ engine_id: selectedEngineId, status: "NO_DATA" });
        setLiveTelemetry({});
        if (!replayMode) {
          setEngine({ engine_id: selectedEngineId, status: "NO_DATA" });
          setTelemetry({});
        }
        return;
      }

      telemetryData = await telemetryResponse.json();
      setLiveEngine(statusData);
      setLiveTelemetry((previous) => ({ ...previous, ...telemetryData }));
      setTelemetryAvailable(true);
      if (!replayMode) {
        setEngine(statusData);
        setTelemetry((previous) => ({ ...previous, ...telemetryData }));
      }
      setConnected(true);

      const current = {
        timestamp: Date.now(),
        rpm: actualValue(statusData, telemetryData, "rpm", "rpm", "rpm", FALLBACK_TELEMETRY.rpm),
        cht_c: actualValue(statusData, telemetryData, "cht_c", "cht_c", "cht_c", FALLBACK_TELEMETRY.cht_c),
        egt_c: actualValue(statusData, telemetryData, "egt_c", "egt_c", "egt_c", FALLBACK_TELEMETRY.egt_c),
        oil_pressure_kpa: actualValue(
          statusData,
          telemetryData,
          "oil_pressure_kpa",
          "oil_pressure_kpa",
          "oil_pressure_kpa",
          FALLBACK_TELEMETRY.oil_pressure_kpa
        ),
        oil_temperature_c: actualValue(
          statusData,
          telemetryData,
          "oil_temperature_c",
          "oil_temperature_c",
          "oil_temperature_c",
          FALLBACK_TELEMETRY.oil_temperature_c
        ),
        fuel_flow_gph: actualValue(
          statusData,
          telemetryData,
          "fuel_flow_gph",
          "fuel_flow_gph",
          "fuel_flow_gph",
          FALLBACK_TELEMETRY.fuel_flow_gph
        ),
        vibration_g: actualValue(
          statusData,
          telemetryData,
          "vibration_g",
          "vibration_g",
          "vibration_g",
          FALLBACK_TELEMETRY.vibration_g
        ),
      };

      setHistory((previous) => [...previous, current].slice(-60));
    } catch {
      setConnected(false);
    }
  };

  const loadNotifications = async (showLoading = false) => {
    if (showLoading) setNotificationsLoading(true);
    setNotificationsError(false);
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (selectedEngineId) params.set("engine_id", selectedEngineId);
      const response = await fetch(`${API_BASE}/notifications?${params}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Notification request failed");
      const data = await response.json();
      if (!Array.isArray(data)) throw new Error("Invalid notification response");
      setNotifications(data);
    } catch {
      setNotificationsError(true);
    } finally {
      if (showLoading) setNotificationsLoading(false);
    }
  };

  const loadEngineOptions = async () => {
    try {
      const response = await fetch(`${API_BASE}/engines`, { cache: "no-store" });
      if (!response.ok) throw new Error("Engine discovery request failed");
      const data = await response.json();
      const ids = Array.isArray(data.engine_ids) ? data.engine_ids : [];
      setEngineIds([
        ...new Set(["ENGINE-001", "ENGINE-002", "ENGINE-003", ...ids, selectedEngineId]),
      ].sort());
    } catch {
      setEngineIds((previous) => [...new Set([...previous, selectedEngineId])].sort());
    }
  };

  const loadMissionContext = async () => {
    setMissionContextError(false);
    try {
      const engineParam = encodeURIComponent(selectedEngineId);
      const currentResponse = await fetch(
        `${API_BASE}/missions/current?engine_id=${engineParam}`,
        { cache: "no-store" }
      );
      if (!currentResponse.ok) {
        throw new Error("Mission context request failed");
      }
      const current = await currentResponse.json();
      const historyResponse = await fetch(
        `${API_BASE}/missions?engine_id=${engineParam}&limit=50`,
        { cache: "no-store" }
      );
      if (!historyResponse.ok) throw new Error("Mission history request failed");
      const historyData = await historyResponse.json();
      setCurrentMission(current);
      const rows = Array.isArray(historyData) ? historyData : [];
      setMissionHistory(rows);
      setSelectedHistoryMission((previous) =>
        rows.some((mission) => mission.mission_id === previous)
          ? previous
          : rows[0]?.mission_id || ""
      );
    } catch {
      setMissionContextError(true);
    }
  };

  const setMissionLifecycle = async () => {
    if (missionRunning) return;
    setMissionRunning(true);
    try {
      const ending = currentMission?.status === "ACTIVE";
      const response = await fetch(
        `${API_BASE}/missions/${ending ? "end" : "start"}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            ending
              ? {
                  engine_id: selectedEngineId,
                  mission_id: currentMission.mission_id,
                }
              : {
                  engine_id: selectedEngineId,
                  vehicle_id: "UAV-DEMO-001",
                }
          ),
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail?.error || data?.detail || "Mission update failed");
      }
      await Promise.all([loadMissionContext(), loadData()]);
      setNotice(
        ending
          ? `Mission ${data.mission_id} ended.`
          : `Mission ${data.mission_id} started.`
      );
    } catch (error) {
      setNotice(error.message || "Unable to update mission.");
    } finally {
      setMissionRunning(false);
    }
  };

  const controlLiveFault = async (clear = false) => {
    if (faultControlLoading) return;
    setFaultControlLoading(true);
    try {
      const response = await fetch(
        clear
          ? `${API_BASE}/simulation/clear?engine_id=${encodeURIComponent(selectedEngineId)}`
          : `${API_BASE}/simulation/fault`,
        clear
          ? { method: "POST" }
          : {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                fault: faultSelection,
                severity: Number(faultSeverity),
                engine_id: selectedEngineId,
              }),
            }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail?.error || data?.detail || "Fault control failed");
      }
      setNotice(
        clear
          ? `Fault cleared for ${selectedEngineId}.`
          : `${FAULT_LABELS[faultSelection]} injected for ${selectedEngineId}.`
      );
      loadData();
      loadNotifications(true);
    } catch (error) {
      setNotice(error.message || "Unable to control engine fault.");
    } finally {
      setFaultControlLoading(false);
    }
  };

  const playStoredMission = async () => {
    if (!selectedHistoryMission) return;
    setReplayPlaying(false);
    setMissionRunning(true);
    try {
      const response = await fetch(
        `${API_BASE}/missions/${encodeURIComponent(selectedHistoryMission)}/replay`,
        { cache: "no-store" }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail?.error || "Mission replay could not be loaded");
      }
      const scenarioId = data.scenario_id || "stored_mission";
      const samples = normalizeReplaySamples(data, scenarioId);
      const finalHealth = data.health?.[data.health.length - 1];
      const finalDegradation = data.degradation?.[data.degradation.length - 1];
      const finalRul = data.rul?.[data.rul.length - 1];
      const summary = {
        mission_duration_seconds: data.mission_duration_seconds,
        total_samples: data.total_samples,
        final_health_score: finalHealth?.health_score ?? 0,
        final_degradation: finalDegradation?.degradation_index ?? 0,
        final_rul_hours: finalRul?.rul_hours ?? 0,
        primary_fault: data.fault_events?.[0]?.fault || "NO_SPECIFIC_FAULT",
      };
      setMissionResult({ summary });
      setMissionReplay({ ...data, samples });
      setReplayCursor(0);
      setReplayPlaying(false);
      setReplayMode(true);
      if (samples.length) {
        applyMissionFrame(samples[0], summary);
        setHistory(samples.map((sample) => ({
          timestamp: new Date(sample.timestamp).getTime(),
          rpm: n(sample.rpm),
          cht_c: n(sample.cht_c),
          egt_c: n(sample.egt_c),
          oil_pressure_kpa: n(sample.oil_pressure_kpa),
          oil_temperature_c: n(sample.oil_temperature_c),
          fuel_flow_gph: n(sample.fuel_flow_gph),
          vibration_g: n(sample.vibration_g),
        })).slice(-60));
      }
      setNotice(`Loaded stored mission ${data.mission_id}.`);
    } catch (error) {
      setNotice(error.message || "Unable to load stored mission replay.");
    } finally {
      setMissionRunning(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = window.setInterval(loadData, 1000);
    return () => window.clearInterval(timer);
  }, [replayMode, selectedEngineId]);

  useEffect(() => {
    const sampleCount = missionReplay?.samples?.length || 0;
    if (!replayMode || !replayPlaying || sampleCount < 2) return undefined;
    const timer = window.setTimeout(() => {
      const nextIndex = replayCursor + 1;
      if (nextIndex >= sampleCount) {
        setReplayPlaying(false);
        return;
      }
      selectReplayFrame(nextIndex);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [replayMode, replayPlaying, replayCursor, missionReplay?.samples?.length]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => loadNotifications(), 0);
    const timer = window.setInterval(() => loadNotifications(), 10000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [selectedEngineId]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => {
      loadMissionScenarios();
      loadEngineOptions();
      loadMissionContext();
    }, 0);
    const timer = window.setInterval(() => {
      loadEngineOptions();
      loadMissionContext();
    }, 10000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [selectedEngineId]);

  useEffect(() => {
    localStorage.setItem("aerotwin-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(""), 3000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const latestTelemetryTime = Date.parse(liveTelemetry.timestamp || "");
  const telemetryStale =
    connected &&
    telemetryAvailable &&
    Number.isFinite(latestTelemetryTime) &&
    Date.now() - latestTelemetryTime > 10000;
  const health = clamp(n(engine.health_score, 0), 0, 100);
  const connectionLabel = !connected
    ? "Backend Offline"
    : !telemetryAvailable
      ? "No Telemetry"
      : telemetryStale
        ? "Telemetry Stale"
        : "Backend Connected";
  const connectionClass = !connected || !telemetryAvailable
    ? "disconnected"
    : telemetryStale
      ? "stale"
      : "connected";
  const anomalyScore = clamp(
    n(pick(engine, ["ml_anomaly.score", "anomaly_score"], 0), 0),
    0,
    1
  );
  const degradation = clamp(
    n(pick(engine, ["degradation.index", "rul.degradation_index"], 0), 0),
    0,
    1
  );
  const rulHours = n(pick(engine, ["rul.rul_hours"], 5000), 5000);
  const diagnosis = engine.fault_diagnosis || FALLBACK_ENGINE.fault_diagnosis;
  const state = engine.engine_state || FALLBACK_ENGINE.engine_state;

  const values = {
    rpm: actualValue(engine, telemetry, "rpm", "rpm", "rpm", FALLBACK_TELEMETRY.rpm),
    cht: actualValue(engine, telemetry, "cht_c", "cht_c", "cht_c", FALLBACK_TELEMETRY.cht_c),
    egt: actualValue(engine, telemetry, "egt_c", "egt_c", "egt_c", FALLBACK_TELEMETRY.egt_c),
    oilPressure: actualValue(
      engine,
      telemetry,
      "oil_pressure_kpa",
      "oil_pressure_kpa",
      "oil_pressure_kpa",
      FALLBACK_TELEMETRY.oil_pressure_kpa
    ),
    oilTemp: actualValue(
      engine,
      telemetry,
      "oil_temperature_c",
      "oil_temperature_c",
      "oil_temperature_c",
      FALLBACK_TELEMETRY.oil_temperature_c
    ),
    fuelFlow: actualValue(
      engine,
      telemetry,
      "fuel_flow_gph",
      "fuel_flow_gph",
      "fuel_flow_gph",
      FALLBACK_TELEMETRY.fuel_flow_gph
    ),
    vibration: actualValue(
      engine,
      telemetry,
      "vibration_g",
      "vibration_g",
      "vibration_g",
      FALLBACK_TELEMETRY.vibration_g
    ),
  };

  const replaySamples = missionReplay?.samples || [];
  const replayFrame = replaySamples[replayCursor];
  const hasDisplayData = replayMode || (connected && telemetryAvailable);

  const targetSource = replayMode
    ? expectedOperatingPoint(replayFrame, null)
    : expectedOperatingPoint(null, engine);

  const parameterCards = [
    ["RPM", hasDisplayData ? values.rpm.toFixed(0) : "—", "RPM", hasDisplayData ? targetSource.rpm.toFixed(0) : "—", hasDisplayData ? "NORMAL" : "UNKNOWN", Gauge],
    ["CHT", hasDisplayData ? values.cht.toFixed(0) : "—", "Â°C", hasDisplayData ? targetSource.cht_c.toFixed(0) : "—", hasDisplayData ? state.thermal_state : "UNKNOWN", Thermometer],
    ["EGT", hasDisplayData ? values.egt.toFixed(0) : "—", "Â°C", hasDisplayData ? targetSource.egt_c.toFixed(0) : "—", hasDisplayData ? state.combustion_state : "UNKNOWN", Thermometer],
    ["Oil Pressure", hasDisplayData ? values.oilPressure.toFixed(0) : "—", "kPa", hasDisplayData ? targetSource.oil_pressure_kpa.toFixed(0) : "—", hasDisplayData ? state.lubrication_state : "UNKNOWN", Activity],
    ["Oil Temp", hasDisplayData ? values.oilTemp.toFixed(0) : "—", "Â°C", hasDisplayData ? targetSource.oil_temperature_c.toFixed(0) : "—", hasDisplayData ? state.lubrication_state : "UNKNOWN", Thermometer],
    ["Fuel Flow", hasDisplayData ? values.fuelFlow.toFixed(1) : "—", "gph", hasDisplayData ? targetSource.fuel_flow_gph.toFixed(1) : "—", hasDisplayData ? "NORMAL" : "UNKNOWN", Fuel],
    ["Vibration", hasDisplayData ? values.vibration.toFixed(2) : "—", "g", hasDisplayData ? targetSource.vibration_g.toFixed(2) : "—", hasDisplayData ? state.mechanical_state : "UNKNOWN", Activity],
  ];

  const openNotice = (message) => setNotice(message);

  const openNotificationDetails = (event) => {
    const faultLabel = FAULT_LABELS[event.fault] || event.fault.replaceAll("_", " ");
    const evidence = Array.isArray(event.metadata?.evidence)
      ? event.metadata.evidence
      : [];
    const message =
      event.metadata?.message ||
      evidence.join(" · ") ||
      `${faultLabel} reported for ${event.engine_id}.`;

    setNotificationPanelOpen(false);
    setModal({
      title: `${faultLabel} · ${event.status}`,
      body: (
        <div className="diagnosis-modal notification-details">
          <p>{message}</p>
          <div className="detail-grid">
            <div><span>Engine</span><strong>{event.engine_id}</strong></div>
            <div><span>Vehicle</span><strong>{event.vehicle_id || "—"}</strong></div>
            <div><span>Mission</span><strong>{event.mission_id || "—"}</strong></div>
            <div><span>Severity</span><strong>{Math.round(n(event.severity, 0) * 100)}%</strong></div>
            <div><span>Status</span><StatusBadge value={event.status} /></div>
            <div><span>Started</span><strong>{formatNotificationTime(event.started_at)}</strong></div>
            {event.cleared_at && (
              <div><span>Cleared</span><strong>{formatNotificationTime(event.cleared_at)}</strong></div>
            )}
          </div>
          {evidence.length > 0 && (
            <div className="notification-evidence">
              <strong>Evidence</strong>
              <ul>{evidence.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
            </div>
          )}
        </div>
      ),
    });
  };

  const handleNav = (page) => {
    setActivePage(page);
    setMobileNav(false);

    if (page === "Dashboard") {
      setModal(null);
      return;
    }

    const parameterRows = [
      ["RPM", values.rpm.toFixed(0), "RPM", targetSource.rpm.toFixed(0), state.operating_mode],
      ["CHT", values.cht.toFixed(0), "Â°C", targetSource.cht_c.toFixed(0), state.thermal_state],
      ["EGT", values.egt.toFixed(0), "Â°C", targetSource.egt_c.toFixed(0), state.combustion_state],
      ["Oil Pressure", values.oilPressure.toFixed(0), "kPa", targetSource.oil_pressure_kpa.toFixed(0), state.lubrication_state],
      ["Oil Temperature", values.oilTemp.toFixed(0), "Â°C", targetSource.oil_temperature_c.toFixed(0), state.lubrication_state],
      ["Fuel Flow", values.fuelFlow.toFixed(1), "gph", targetSource.fuel_flow_gph.toFixed(1), "MONITORING"],
      ["Vibration", values.vibration.toFixed(2), "g", targetSource.vibration_g.toFixed(2), state.mechanical_state],
    ];

    const diagnosticEvidence = Array.isArray(diagnosis.evidence)
      ? diagnosis.evidence
      : [String(diagnosis.evidence || "No diagnostic evidence available.")];

    const commonFooter = (
      <button className="secondary-button" type="button" onClick={() => setModal(null)}>
        Close Module
      </button>
    );

    if (page === "Live Telemetry") {
      setModal({
        title: "Live Telemetry",
        body: (
          <div className="telemetry-table">
            <div className="detail-grid">
              <div><span>Engine</span><strong>{engine.engine_id || "ENGINE-001"}</strong></div>
              <div><span>Mission</span><strong>{engine.mission_id || "MISSION-DEMO-001"}</strong></div>
              <div><span>Altitude</span><strong>{n(telemetry.altitude_m, 2000).toFixed(0)} m</strong></div>
              <div><span>Ambient</span><strong>{n(telemetry.ambient_temperature_c, 25).toFixed(0)} Â°C</strong></div>
            </div>
            {parameterRows.map(([label, value, unit, target, stateValue]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value} {unit}</strong>
                <em>{stateValue}</em>
                <small>Target {target} {unit}</small>
              </div>
            ))}
            {commonFooter}
          </div>
        ),
      });
      return;
    }

    if (page === "Engine Health") {
      setModal({
        title: "Engine Health",
        body: (
          <div className="diagnosis-modal">
            <div className="health-center">
              <GaugeRing value={health} label="Digital Twin Health" tone={health < 40 ? "red" : "blue"} />
              <StatusBadge value={engine.status || "UNKNOWN"} />
              <p>Current health derived from the Digital Twin and backend health assessment.</p>
            </div>
            <div className="telemetry-table">
              {parameterRows.map(([label, value, unit, target, stateValue]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value} {unit}</strong>
                  <em>{stateValue}</em>
                  <small>Expected {target} {unit}</small>
                </div>
              ))}
            </div>
            <div className="detail-grid">
              <div><span>Anomaly Score</span><strong>{(anomalyScore * 100).toFixed(1)}%</strong></div>
              <div><span>Degradation</span><strong>{(degradation * 100).toFixed(1)}%</strong></div>
              <div><span>RUL</span><strong>{rulHours.toFixed(0)} h</strong></div>
              <div><span>RUL Status</span><StatusBadge value={engine.rul?.status || "STABLE"} compact /></div>
            </div>
            {commonFooter}
          </div>
        ),
      });
      return;
    }

    if (page === "AI Diagnostics") {
      setModal({
        title: "AI Diagnostics",
        body: (
          <div className="diagnosis-modal">
            <div className="detail-grid">
              <div><span>Diagnostic Status</span><StatusBadge value={engine.diagnostic?.status || engine.status || "HEALTHY"} /></div>
              <div><span>Confidence</span><strong>{Math.round(n(diagnosis.confidence, 0.95) * 100)}%</strong></div>
              <div><span>ML Anomaly Score</span><strong>{(anomalyScore * 100).toFixed(1)}%</strong></div>
              <div><span>Primary Signal</span><strong>{engine.diagnostic?.primary_signal || "PHYSICS_HEALTH"}</strong></div>
            </div>
            <h4>{diagnosis.fault || "NO_SPECIFIC_FAULT"}</h4>
            <p>{engine.diagnostic?.message || diagnosis.recommendation || "Engine behavior is being monitored continuously."}</p>
            <div className="evidence-list">
              {diagnosticEvidence.map((item, index) => (
                <div key={index}><CircleAlert size={16} /> {item}</div>
              ))}
            </div>
            <div className="recommended-action">
              <CircleCheck size={18} />
              <div><span>Recommended Action</span><strong>{diagnosis.recommendation || "Continue monitoring engine parameters."}</strong></div>
            </div>
            {commonFooter}
          </div>
        ),
      });
      return;
    }

    if (page === "3D Engine View") {
      setModal({
        title: "3D Engine View",
        body: <EngineIllustration viewMode={viewMode} setViewMode={setViewMode} values={values} targetSource={targetSource} state={state} health={health} diagnosis={diagnosis} />,
      });
      return;
    }

    if (page === "Flight & Mission") {
      setModal({
        title: "Flight & Mission",
        body: (
          <div className="diagnosis-modal">
            <div className="detail-grid">
              <div><span>Selected Scenario</span><strong>{activeScenarioDisplay.label || selectedScenario}</strong></div>
              <div><span>Scenario Group</span><strong>{activeScenarioDisplay.group || "Mission Conditions"}</strong></div>
              <div><span>Mission Status</span><StatusBadge value={replayMode ? "REPLAY" : "LIVE"} compact /></div>
              <div><span>Samples</span><strong>{replaySamples.length || missionSummary.total_samples || 0}</strong></div>
            </div>
            <p>{activeScenarioDisplay.detail || selectedScenarioInfo?.description || "Select and run a controlled Digital Twin mission scenario."}</p>
            <div className="mission-result-grid">
              <div><span>Health</span><strong>{n(missionSummary.final_health_score, health).toFixed(0)}%</strong></div>
              <div><span>Degradation</span><strong>{(n(missionSummary.final_degradation, degradation) * 100).toFixed(1)}%</strong></div>
              <div><span>RUL</span><strong>{n(missionSummary.final_rul_hours, rulHours).toFixed(0)} h</strong></div>
              <div><span>Primary Fault</span><strong>{missionSummary.primary_fault || diagnosis.fault || "NO_SPECIFIC_FAULT"}</strong></div>
            </div>
            <div className="modal-actions">
              <button className="primary-button" type="button" onClick={runMission} disabled={missionRunning}>
                {missionRunning ? "Running..." : "Run Selected Mission"}
              </button>
              {replayMode && (
                <button className="secondary-button" type="button" onClick={returnToLive}>
                  Return to Live
                </button>
              )}
              {commonFooter}
            </div>
          </div>
        ),
      });
      return;
    }

    if (page === "Maintenance") {
      setModal({
        title: "Maintenance Advisory",
        body: (
          <div className="diagnosis-modal">
            <StatusBadge value={diagnosis.severity || engine.status || "HEALTHY"} />
            <h4>{diagnosis.fault || "NO_SPECIFIC_FAULT"}</h4>
            <p>Advisory generated from the current Digital Twin health and fault-diagnosis state.</p>
            <div className="detail-grid">
              <div><span>Health</span><strong>{health.toFixed(0)}%</strong></div>
              <div><span>Degradation</span><strong>{(degradation * 100).toFixed(1)}%</strong></div>
              <div><span>RUL</span><strong>{rulHours.toFixed(0)} h</strong></div>
              <div><span>Trend</span><strong>{engine.degradation?.trend || "STABLE"}</strong></div>
            </div>
            <div className="recommended-action">
              <CircleCheck size={18} />
              <div><span>Recommended Action</span><strong>{diagnosis.recommendation || "Continue monitoring engine parameters."}</strong></div>
            </div>
            <small>Maintenance advisory is a development-stage decision-support feature and is not a certified aircraft maintenance instruction.</small>
            {commonFooter}
          </div>
        ),
      });
      return;
    }

    if (page === "Reports") {
      setModal({
        title: "AeroTwin Mission Report",
        body: (
          <div className="report-modal">
            <div><span>Engine</span><strong>{engine.engine_id || "ENGINE-001"}</strong></div>
            <div><span>Mission</span><strong>{engine.mission_id || "MISSION-DEMO-001"}</strong></div>
            <div><span>Health</span><strong>{health.toFixed(0)}%</strong></div>
            <div><span>Degradation</span><strong>{(degradation * 100).toFixed(1)}%</strong></div>
            <div><span>RUL</span><strong>{rulHours.toFixed(0)} hours</strong></div>
            <div><span>Primary Fault</span><strong>{diagnosis.fault || "NO_SPECIFIC_FAULT"}</strong></div>
            <div><span>Diagnostic Confidence</span><strong>{Math.round(n(diagnosis.confidence, 0.95) * 100)}%</strong></div>
            <p>{missionResult ? `Mission ${activeScenarioDisplay.label || selectedScenario} completed with ${n(missionSummary.total_samples, replaySamples.length)} samples.` : "No mission replay is currently loaded. The report reflects the current live engine state."}</p>
            {commonFooter}
          </div>
        ),
      });
      return;
    }

    if (page === "Settings") {
      setModal({
        title: "AeroTwin Settings",
        body: (
          <div className="diagnosis-modal">
            <div className="detail-grid">
              <div><span>Backend</span><StatusBadge value={connected ? "CONNECTED" : "OFFLINE"} /></div>
              <div><span>API</span><strong>{API_BASE}</strong></div>
              <div><span>Refresh</span><strong>1 second</strong></div>
              <div><span>Theme</span><strong>{THEMES.find((item) => item.id === theme)?.label || theme}</strong></div>
            </div>
            <p>Dashboard settings are currently local to the frontend. Backend calculations and ML modules are unchanged.</p>
            <button className="secondary-button" type="button" onClick={() => setThemeOpen(true)}>
              Change Background
            </button>
            {commonFooter}
          </div>
        ),
      });
    }
  };

  const selectedScenarioInfo = missionScenarios.find((item) => item.id === selectedScenario);
  const missionConditionScenarios = missionScenarios.filter((item) => ENVIRONMENT_SCENARIO_IDS.has(item.id));
  const faultScenarios = missionScenarios.filter((item) => FAULT_SCENARIO_IDS.has(item.id));
  const activeScenarioDisplay = SCENARIO_DISPLAY[selectedScenario] || {};
  const missionSummary = missionResult?.summary || {};

  const setThemeAndClose = (id) => {
    setTheme(id);
    setThemeOpen(false);
    setNotice(`Background changed to ${THEMES.find((item) => item.id === id)?.label}.`);
  };

  return (
    <div className={`app-shell theme-${theme}`}>
      <aside className={`sidebar ${mobileNav ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Plane size={22} /></div>
          <div>
            <strong>AeroTwin</strong>
            <span>ENGINE INTELLIGENCE</span>
          </div>
        </div>

        <div className="nav-label">Workspace</div>
        <nav>
          {NAV_ITEMS.map(({ id, icon: Icon }) => (
            <button
              key={id}
              type="button"
              className={activePage === id ? "nav-item active" : "nav-item"}
              onClick={() => handleNav(id)}
            >
              <Icon size={18} />
              <span>{id}</span>
              {id === "AI Diagnostics" && <b>AI</b>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-card">
            <span className={connectionClass === "connected" ? "online-dot" : "offline-dot"} />
            <div>
              <strong>{connectionLabel}</strong>
              <small>FastAPI Â· Live telemetry</small>
            </div>
          </div>
          <button className="theme-launcher" type="button" onClick={() => setThemeOpen((open) => !open)}>
            <Palette size={18} />
            <span>Change Background</span>
            <ChevronDown size={16} />
          </button>
        </div>
      </aside>

      <div className="mobile-top">
        <button className="icon-button" type="button" onClick={() => setMobileNav((open) => !open)}>
          <Menu size={22} />
        </button>
        <strong>AeroTwin</strong>
        <button className="icon-button" type="button" onClick={() => setThemeOpen((open) => !open)}>
          <Palette size={19} />
        </button>
      </div>

      <main className="main-area">
        <header className="topbar">
          <div className="search-box">
            <Search size={18} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  const query = searchQuery.trim().toLowerCase();
                  const match = NAV_ITEMS.find((item) => item.id.toLowerCase().includes(query));
                  if (match) handleNav(match.id);
                  else if (query) openNotice(`Searching AeroTwin for â€œ${searchQuery.trim()}â€`);
                }
              }}
              placeholder="Search parameters, faults, missions, reports..."
            />
            <kbd>Ctrl K</kbd>
          </div>

          <div className="topbar-right">
            <div className={`connection-status ${connectionClass}`}>
              <span />
              {connectionLabel}
            </div>
            <span className="date-text">
              {new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
            </span>
            <span className="time-text">
              {new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
            <div className="notification-center">
              <button
                className="notification-button"
                type="button"
                aria-label="Engine notifications"
                aria-expanded={notificationPanelOpen}
                onClick={() => {
                  const willOpen = !notificationPanelOpen;
                  setNotificationPanelOpen(willOpen);
                  if (willOpen) loadNotifications(true);
                }}
              >
                <Bell size={20} />
                {notifications.filter((event) => event.status === "ACTIVE").length > 0 && (
                  <b>
                    {Math.min(
                      notifications.filter((event) => event.status === "ACTIVE").length,
                      99
                    )}
                  </b>
                )}
              </button>
              {notificationPanelOpen && (
                <section className="notification-panel" aria-label="Engine notifications">
                  <div className="notification-panel-header">
                    <div>
                      <strong>Engine Notifications</strong>
                      <span>
                        {notifications.filter((event) => event.status === "ACTIVE").length} active
                      </span>
                    </div>
                    <button
                      className="notification-refresh"
                      type="button"
                      aria-label="Refresh notifications"
                      onClick={() => loadNotifications(true)}
                      disabled={notificationsLoading}
                    >
                      <RotateCcw size={15} />
                    </button>
                  </div>
                  {notificationsLoading ? (
                    <p className="notification-state">Loading notifications...</p>
                  ) : notificationsError ? (
                    <p className="notification-state error">Unable to load notifications</p>
                  ) : notifications.length === 0 ? (
                    <p className="notification-state">No recent notifications</p>
                  ) : (
                    <div className="notification-list">
                      {notifications.map((event) => {
                        const active = event.status === "ACTIVE";
                        const faultLabel = FAULT_LABELS[event.fault] || event.fault.replaceAll("_", " ");
                        const evidence = Array.isArray(event.metadata?.evidence)
                          ? event.metadata.evidence.join(" · ")
                          : "";
                        const message =
                          event.metadata?.message ||
                          evidence ||
                          `${faultLabel} reported for ${event.engine_id}.`;
                        return (
                          <button
                            className={`notification-item ${active ? "active" : "cleared"}`}
                            type="button"
                            key={event.id}
                            onClick={() => openNotificationDetails(event)}
                          >
                            <span className="notification-item-top">
                              <strong>{faultLabel}</strong>
                              <span className={`notification-status ${active ? "active" : "cleared"}`}>
                                {event.status}
                              </span>
                            </span>
                            <span className="notification-item-meta">
                              {event.engine_id} · Severity {Math.round(n(event.severity, 0) * 100)}%
                            </span>
                            <span className="notification-item-message">{message}</span>
                            <time>{formatNotificationTime(event.created_at || event.started_at)}</time>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </section>
              )}
            </div>
            <button className="profile-button" type="button" onClick={() => openNotice("Profile menu opened.")}>
              <span>SS</span>
              <strong>Shubham</strong>
              <ChevronDown size={15} />
            </button>
          </div>
        </header>

        <section className="page-content">
          <div className="breadcrumb">AEROTWIN <span>/</span> {activePage}</div>
          {!hasDisplayData && (
            <div className="telemetry-status-banner" role="status">
              {connected
                ? "No telemetry is available for this engine. Live health and parameter readings are unavailable."
                : "Backend unavailable. Live readings are unavailable; reconnect to resume monitoring."}
            </div>
          )}
          {telemetryStale && !replayMode && (
            <div className="telemetry-status-banner warning" role="status">
              Latest telemetry is more than 10 seconds old. Current engine condition may have changed.
            </div>
          )}

          <div className="hero-heading">
            <div>
              <h1>Real-Time Aero Engine <span>Digital Twin</span></h1>
              <p>Monitor <b>|</b> Predict <b>|</b> Prevent <b>|</b> For a Safer Tomorrow</p>
            </div>
            <div className="hero-slogan-wrap">
              <div className="hero-slogan">Turning Data into<br /><strong>safer skies.</strong></div>
            </div>
          </div>

          <div className="info-grid">
            <InfoCard
              icon={Cpu}
              label="Engine ID"
              value={hasDisplayData ? engine.engine_id || selectedEngineId : selectedEngineId}
              sub="Aero Piston Engine"
              onClick={() => openNotice(`Engine ${hasDisplayData ? engine.engine_id || selectedEngineId : selectedEngineId} selected.`)}
            />
            <InfoCard
              icon={Radio}
              label="Mission ID"
              value={hasDisplayData
                ? engine.mission_id || currentMission?.mission_id || "—"
                : currentMission?.mission_id || "—"}
              sub={currentMission?.status === "ACTIVE" ? "Active Mission" : "Mission"}
              tone="red"
              onClick={() => openNotice("Mission telemetry selected.")}
            />
            <InfoCard
              icon={Gauge}
              label="Operating Mode"
              value={hasDisplayData ? state.operating_mode || "CRUISE" : "—"}
              sub={hasDisplayData ? "Digital Twin State" : "Awaiting telemetry"}
              tone="purple"
              onClick={() => setModal({
                title: "Operating Mode",
                body: (
                  <div className="detail-grid">
                    <div><span>Mode</span><strong>{hasDisplayData ? state.operating_mode || "CRUISE" : "—"}</strong></div>
                    <div><span>Throttle</span><strong>{hasDisplayData ? "Live telemetry" : "Unavailable"}</strong></div>
                    <div><span>Engine health</span>{hasDisplayData ? <StatusBadge value={state.overall_health} /> : <strong>—</strong>}</div>
                  </div>
                ),
              })}
            />
            <InfoCard
              icon={Plane}
              label="Altitude"
              value={hasDisplayData ? `${n(pick(telemetry, ["altitude_m"], 2000), 2000).toFixed(0)} m` : "—"}
              sub={hasDisplayData ? `Ambient ${n(pick(telemetry, ["ambient_temperature_c"], 25), 25).toFixed(0)}Â°C` : "Telemetry unavailable"}
              tone="green"
              onClick={() => openNotice("Altitude and ambient telemetry selected.")}
            />
          </div>

          <section className="panel mission-control-panel">
            <div className="mission-control-header">
              <SectionHeader
                icon={Plane}
                title="Mission Simulation"
                subtitle="Run the Digital Twin through controlled flight scenarios"
              />
              <div className="mission-mode-badge">
                <span className={replayMode ? "replay-dot" : "live-dot"} />
                {replayMode ? "MISSION REPLAY" : "LIVE ENGINE"}
              </div>
            </div>
            <div className="mission-control-grid">
              <div className="mission-selector">
                <label htmlFor="engine-select">Engine</label>
                <select
                  id="engine-select"
                  value={selectedEngineId}
                  onChange={(event) => {
                    setSelectedEngineId(event.target.value);
                    setReplayPlaying(false);
                    setReplayMode(false);
                    setMissionReplay(null);
                    setMissionResult(null);
                  }}
                  disabled={missionRunning}
                >
                  {engineIds.map((engineId) => (
                    <option key={engineId} value={engineId}>{engineId}</option>
                  ))}
                </select>
                <div className="mission-context-row">
                  <span>
                    {missionContextError
                      ? "Mission data unavailable"
                      : currentMission?.status === "ACTIVE"
                        ? `Current mission · ${currentMission.mission_id}`
                        : "No active mission"}
                  </span>
                  <button
                    className="secondary-button mission-lifecycle-button"
                    type="button"
                    onClick={setMissionLifecycle}
                    disabled={missionRunning || missionContextError}
                  >
                    {currentMission?.status === "ACTIVE" ? "End Mission" : "Start Mission"}
                  </button>
                </div>
                <div className="live-fault-control">
                  <div className="live-fault-heading">
                    <strong>Live fault control</strong>
                    <span>
                      {engine.active_fault
                        ? `${FAULT_LABELS[engine.active_fault.fault] || engine.active_fault.fault} · ${Math.round(n(engine.active_fault.severity, 0) * 100)}%`
                        : "No active fault"}
                    </span>
                  </div>
                  <div className="live-fault-inputs">
                    <select
                      aria-label="Live fault"
                      value={faultSelection}
                      onChange={(event) => setFaultSelection(event.target.value)}
                      disabled={faultControlLoading}
                    >
                      {Object.entries(FAULT_LABELS).map(([fault, label]) => (
                        <option key={fault} value={fault}>{label}</option>
                      ))}
                    </select>
                    <label>
                      Severity {Math.round(faultSeverity * 100)}%
                      <input
                        type="range"
                        min="0.1"
                        max="1"
                        step="0.1"
                        value={faultSeverity}
                        onChange={(event) => setFaultSeverity(Number(event.target.value))}
                        disabled={faultControlLoading}
                      />
                    </label>
                  </div>
                  <div className="live-fault-actions">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => controlLiveFault(false)}
                      disabled={faultControlLoading}
                    >
                      {faultControlLoading ? "Applying..." : "Inject Fault"}
                    </button>
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => controlLiveFault(true)}
                      disabled={faultControlLoading || !engine.active_fault}
                    >
                      Clear Fault
                    </button>
                  </div>
                </div>
                <label htmlFor="scenario-select">Scenario</label>
                <select
                  id="scenario-select"
                  value={selectedScenario}
                  onChange={(event) => setSelectedScenario(event.target.value)}
                  disabled={missionRunning}
                >
                  {missionScenarios.length ? (
                    <>
                      <optgroup label="Mission Conditions">
                        {missionConditionScenarios.map((scenario) => (
                          <option key={scenario.id} value={scenario.id}>{displayScenarioName(scenario)}</option>
                        ))}
                      </optgroup>
                      <optgroup label="Fault / Degradation Scenarios">
                        {faultScenarios.map((scenario) => (
                          <option key={scenario.id} value={scenario.id}>{displayScenarioName(scenario)}</option>
                        ))}
                      </optgroup>
                    </>
                  ) : (
                    <option value="normal_mission">Normal Mission</option>
                  )}
                </select>
                <small className="synthetic-simulation-note">
                  Synthetic / Development Simulation · not validated for aircraft operation
                </small>
                <div className="scenario-meta">
                  <span className="scenario-group-badge">{activeScenarioDisplay.group || scenarioGroup(selectedScenarioInfo)}</span>
                  <p>{activeScenarioDisplay.detail || selectedScenarioInfo?.description || "Select a controlled engine scenario and run the Digital Twin simulation."}</p>
                </div>

                {missionScenarios.length > 0 && (
                  <div className="scenario-quick-groups">
                    {missionConditionScenarios.length > 0 && (
                      <div className="scenario-quick-list">
                        <span>Mission conditions</span>
                        <div>
                          {missionConditionScenarios.map((scenario) => (
                            <button
                              key={scenario.id}
                              type="button"
                              className={selectedScenario === scenario.id ? "scenario-chip active" : "scenario-chip"}
                              onClick={() => setSelectedScenario(scenario.id)}
                              disabled={missionRunning}
                            >
                              {displayScenarioName(scenario)}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {faultScenarios.length > 0 && (
                      <div className="scenario-quick-list">
                        <span>Fault / degradation</span>
                        <div>
                          {faultScenarios.map((scenario) => (
                            <button
                              key={scenario.id}
                              type="button"
                              className={selectedScenario === scenario.id ? "scenario-chip active fault" : "scenario-chip fault"}
                              onClick={() => setSelectedScenario(scenario.id)}
                              disabled={missionRunning}
                            >
                              {displayScenarioName(scenario)}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <button className="primary-button mission-run-button" type="button" onClick={runMission} disabled={missionRunning}>
                {missionRunning ? <><RotateCcw size={17} className="spin" /> Running Simulation...</> : <><Activity size={17} /> Run Mission</>}
              </button>
              {replayMode && (
                <button className="secondary-button mission-live-button" type="button" onClick={returnToLive}>
                  <Radio size={17} /> Return to Live
                </button>
              )}
            </div>

            {replayMode && replayFrame && (
              <div className="mission-operating-strip">
                <div><span>Throttle</span><strong>{n(replayFrame.throttle_pct, 0).toFixed(0)}%</strong></div>
                <div><span>Altitude</span><strong>{n(replayFrame.altitude_m, 0).toFixed(0)} m</strong></div>
                <div><span>Ambient</span><strong>{n(replayFrame.ambient_temperature_c, 25).toFixed(0)} Â°C</strong></div>
                <div><span>Model</span><strong>Physics / Performance</strong></div>
              </div>
            )}

            {missionResult && (
              <div className="mission-result-grid">
                <div><span>Duration</span><strong>{n(missionSummary.mission_duration_seconds, 0).toFixed(0)} s</strong></div>
                <div><span>Health</span><strong>{n(missionSummary.final_health_score, health).toFixed(0)}%</strong></div>
                <div><span>Degradation</span><strong>{(n(missionSummary.final_degradation, degradation) * 100).toFixed(1)}%</strong></div>
                <div><span>RUL</span><strong>{n(missionSummary.final_rul_hours, rulHours).toFixed(0)} h</strong></div>
                <div><span>Primary Fault</span><strong>{missionSummary.primary_fault || diagnosis.fault || "NO_SPECIFIC_FAULT"}</strong></div>
                <div><span>Samples</span><strong>{n(missionSummary.total_samples, replaySamples.length)}</strong></div>
              </div>
            )}

            <div className="mission-history-control">
              <label htmlFor="mission-history-select">Stored mission replay</label>
              <select
                id="mission-history-select"
                value={selectedHistoryMission}
                onChange={(event) => setSelectedHistoryMission(event.target.value)}
                disabled={missionRunning || missionHistory.length === 0}
              >
                {missionHistory.length === 0 ? (
                  <option value="">No mission history</option>
                ) : missionHistory.map((mission) => (
                  <option key={mission.mission_id} value={mission.mission_id}>
                    {mission.mission_id} · {mission.status}
                  </option>
                ))}
              </select>
              <button
                className="secondary-button"
                type="button"
                onClick={playStoredMission}
                disabled={missionRunning || !selectedHistoryMission}
              >
                {missionRunning ? "Loading..." : "Load Replay"}
              </button>
            </div>

            {replayMode && replaySamples.length > 1 && (
              <div className="mission-replay-strip">
                <div className="replay-title">
                  <span>Mission Timeline</span>
                  <strong>
                    {replayFrame?.segment_name || "MISSION"} · {n(replayFrame?.mission_time_seconds, 0)}s
                    {replayFrame?.timestamp && ` · ${new Date(replayFrame.timestamp).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })}`}
                  </strong>
                </div>
                <button
                  className="secondary-button replay-toggle"
                  type="button"
                  aria-label={replayPlaying ? "Pause mission replay" : "Play mission replay"}
                  onClick={() => {
                    if (!replayPlaying && replayCursor >= replaySamples.length - 1) {
                      selectReplayFrame(0);
                    }
                    setReplayPlaying(!replayPlaying);
                  }}
                >
                  {replayPlaying ? <Pause size={14} /> : <Play size={14} />}
                  {replayPlaying ? "Pause" : "Play"}
                </button>
                <input
                  type="range"
                  min="0"
                  max={replaySamples.length - 1}
                  value={replayCursor}
                  onChange={(event) => {
                    setReplayPlaying(false);
                    selectReplayFrame(event.target.value);
                  }}
                />
                <div className="replay-scale"><span>START</span><span>{replaySamples.length} telemetry samples</span><span>END</span></div>
                {missionReplay?.fault_events?.length > 0 && (
                  <div className="replay-event-markers" aria-label="Fault event markers">
                    {missionReplay.fault_events.map((event, index) => (
                      <button
                        key={`${event.fault}-${event.time_seconds}-${index}`}
                        type="button"
                        onClick={() => {
                          setReplayPlaying(false);
                          const nearestIndex = replaySamples.reduce(
                            (bestIndex, sample, sampleIndex) =>
                              Math.abs(n(sample.mission_time_seconds, 0) - n(event.time_seconds, 0)) <
                              Math.abs(n(replaySamples[bestIndex]?.mission_time_seconds, 0) - n(event.time_seconds, 0))
                                ? sampleIndex
                                : bestIndex,
                            0
                          );
                          selectReplayFrame(nearestIndex);
                        }}
                        title={`Jump to ${event.fault} at ${event.time_seconds}s`}
                      >
                        {FAULT_LABELS[event.fault] || event.fault.replaceAll("_", " ")} · {event.time_seconds}s
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <div className="hero-grid">
            <section className="panel engine-panel immersive-panel">
              <SectionHeader
                icon={Box}
                title="3D Engine View"
                subtitle="Digital Twin visualization"
                action={hasDisplayData ? "Open View" : undefined}
                onAction={() => setModal({
                  title: "3D Engine View",
                  body: <EngineIllustration viewMode={viewMode} setViewMode={setViewMode} values={values} targetSource={targetSource} state={state} health={health} diagnosis={diagnosis} />,
                })}
              />
              {hasDisplayData ? (
                <EngineIllustration viewMode={viewMode} setViewMode={setViewMode} values={values} targetSource={targetSource} state={state} health={health} diagnosis={diagnosis} />
              ) : (
                <div className="telemetry-empty-state">
                  Digital Twin visualization unavailable until telemetry is received.
                </div>
              )}
            </section>

            <section className="panel health-panel">
              <SectionHeader icon={HeartPulse} title="Engine Health" subtitle="Overall Digital Twin health" tone="red" />
              <div className="health-center">
                {hasDisplayData ? (
                  <>
                    <GaugeRing value={health} label="Digital Twin Health" tone={health < 40 ? "red" : "blue"} />
                    <StatusBadge value={engine.status || "CRITICAL"} />
                    <p>Overall Digital Twin health score</p>
                  </>
                ) : (
                  <p>Health unavailable until telemetry is received.</p>
                )}
              </div>
            </section>

            <section className="panel assistant-panel">
              <SectionHeader icon={Sparkles} title="AI Assistant" subtitle="Physics + ML diagnostics" tone="purple" />
              <div className="assistant-alert">
                <div className="assistant-icon"><Sparkles size={21} /></div>
                <div>
                  <strong>{hasDisplayData ? diagnosis.message : "Diagnosis unavailable until telemetry is received."}</strong>
                  <p>{hasDisplayData ? "Physics-based analysis and ML diagnostics are monitoring engine behavior continuously." : "No diagnostic result is available for the selected engine."}</p>
                </div>
              </div>
              <div className="assistant-row">
                <span>Primary Fault</span>
                <strong className="red-text">{hasDisplayData ? diagnosis.fault || "NO_SPECIFIC_FAULT" : "UNAVAILABLE"}</strong>
              </div>
              <div className="assistant-row">
                <span>Confidence</span>
                <strong>{hasDisplayData ? `${Math.round(n(diagnosis.confidence, 0) * 100)}%` : "—"}</strong>
              </div>
              <div className="assistant-row recommendation">
                <span>Recommendation</span>
                <strong>{hasDisplayData ? diagnosis.recommendation || "Continue monitoring." : "Unavailable"}</strong>
              </div>
              <button
                className="primary-button wide"
                type="button"
                disabled={!hasDisplayData}
                onClick={() => setModal({
                  title: "Detailed AI Diagnosis",
                  body: (
                    <div className="diagnosis-modal">
                      <StatusBadge value={diagnosis.severity || "CRITICAL"} />
                      <h4>{diagnosis.fault || "NO_SPECIFIC_FAULT"}</h4>
                      <p>{diagnosis.recommendation}</p>
                      <div className="evidence-list">
                        {(Array.isArray(diagnosis.evidence) ? diagnosis.evidence : [String(diagnosis.evidence || "No evidence available.")]).map((item, index) => (
                          <div key={index}><CircleAlert size={16} /> {item}</div>
                        ))}
                      </div>
                    </div>
                  ),
                })}
              >
                View Detailed Diagnosis <ChevronRight size={17} />
              </button>
            </section>
          </div>

          <section className="panel parameters-panel" id="parameters">
            <SectionHeader
              icon={BarChart3}
              title={replayMode ? "Mission Telemetry (Replay)" : "Key Engine Parameters (Live)"}
              subtitle={replayMode ? "Frame-accurate telemetry from the selected mission" : "Real-time telemetry from the Digital Twin"}
              action="View Details"
              onAction={() => setModal({
                title: "Live Telemetry",
                body: (
                  <div className="telemetry-table">
                    {parameterCards.map(([label, value, unit, target, stateValue]) => (
                      <div key={label}><span>{label}</span><strong>{value} {unit}</strong><em>{stateValue}</em><small>Target {target} {unit}</small></div>
                    ))}
                  </div>
                ),
              })}
            />
            <div className="parameters-grid">
              {parameterCards.map(([label, value, unit, target, stateValue, Icon]) => (
                <ParameterCard
                  key={label}
                  label={label}
                  value={value}
                  unit={unit}
                  target={target}
                  state={stateValue}
                  icon={Icon}
                  onClick={() => openNotice(`${label}: ${value} ${unit}`)}
                />
              ))}
            </div>
          </section>

          <div className="analysis-grid">
            <section className="panel anomaly-panel">
              <SectionHeader icon={ShieldAlert} title="Anomaly Detection" subtitle="ML + physics fusion" />
              <div className="anomaly-layout">
                {hasDisplayData
                  ? <GaugeRing value={anomalyScore * 100} label="Anomaly Score" tone="red" />
                  : <p>Analysis unavailable</p>}
                <div className="metric-list">
                  <div><span>Anomaly Detected</span>{hasDisplayData ? <StatusBadge value={anomalyScore >= 0.5 ? "YES" : "NORMAL"} compact /> : <strong>—</strong>}</div>
                  <div><span>Confidence</span><strong>{hasDisplayData ? `${Math.round(n(diagnosis.confidence, 0) * 100)}%` : "—"}</strong></div>
                  <div><span>Primary Signal</span><strong>{hasDisplayData ? engine.diagnostic?.primary_signal || "PHYSICS_HEALTH" : "—"}</strong></div>
                </div>
              </div>
            </section>

            <section className="panel rul-panel">
              <SectionHeader icon={Clock3} title="Remaining Useful Life" subtitle="Degradation-based estimate" tone="green" />
              <div className="rul-value">
                <strong>{hasDisplayData ? rulHours.toFixed(0) : "—"}</strong>
                {hasDisplayData && <><span>h</span><StatusBadge value={engine.rul?.status || "STABLE"} compact /></>}
              </div>
              <div className="rul-bar"><span style={{ width: `${hasDisplayData ? clamp((rulHours / 5000) * 100, 2, 100) : 0}%` }} /></div>
              <div className="rul-mini-grid">
                <div><span>Degradation</span><strong>{hasDisplayData ? `${(degradation * 100).toFixed(1)}%` : "—"}</strong></div>
                <div><span>Trend</span><strong>{hasDisplayData ? engine.rul?.status === "DEGRADING" ? "RISING" : "STABLE" : "—"}</strong></div>
                <div><span>Confidence</span><strong>{hasDisplayData ? `${Math.round(n(engine.rul?.confidence, 0) * 100)}%` : "—"}</strong></div>
              </div>
            </section>

            <section className="panel trends-panel">
              <SectionHeader icon={BarChart3} title="Parameter Trends" subtitle={replayMode ? "Selected mission thermal behavior" : "Recent thermal behavior"} action={replayMode ? "REPLAY" : "LIVE"} />
              <TrendChart history={history} />
            </section>
          </div>

          <section className="panel states-panel">
            <div className="states-title-row">
              <SectionHeader icon={ShieldAlert} title="System States" subtitle="Current subsystem health" />
              <span className="live-indicator"><i /> {replayMode ? "REPLAY" : "LIVE"}</span>
            </div>
            <div className="states-grid">
              {[
                ["Thermal State", hasDisplayData ? state.thermal_state : "UNKNOWN"],
                ["Lubrication State", hasDisplayData ? state.lubrication_state : "UNKNOWN"],
                ["Combustion State", hasDisplayData ? state.combustion_state : "UNKNOWN"],
                ["Mechanical State", hasDisplayData ? state.mechanical_state : "UNKNOWN"],
                ["Electrical State", hasDisplayData ? state.electrical_state : "UNKNOWN"],
                ["Sensor Confidence", hasDisplayData ? state.sensor_confidence : "UNKNOWN"],
              ].map(([label, value]) => (
                <button key={label} type="button" className="state-card" onClick={() => openNotice(`${label}: ${value}`)}>
                  <span>{label}</span>
                  <StatusBadge value={value} compact />
                </button>
              ))}
            </div>
          </section>

          <div className="fault-grid">
            <section className="panel fault-panel">
              <div className="fault-heading">
                <div className="section-icon red"><CircleAlert size={21} /></div>
                <div>
                  <h2>Fault Detection</h2>
                  <p>AI + physics-based diagnosis</p>
                </div>
                <StatusBadge value={hasDisplayData ? diagnosis.severity || "UNKNOWN" : "UNKNOWN"} compact />
              </div>
              <h3>{hasDisplayData ? diagnosis.fault || "NO_SPECIFIC_FAULT" : "DIAGNOSIS UNAVAILABLE"}</h3>
              <div className="fault-detail-grid">
                <div><span>Confidence</span><strong>{hasDisplayData ? `${Math.round(n(diagnosis.confidence, 0) * 100)}%` : "—"}</strong></div>
                <div><span>Severity</span><strong className="red-text">{hasDisplayData ? diagnosis.severity || "UNKNOWN" : "—"}</strong></div>
                <div className="evidence-box">
                  <span>Evidence</span>
                  <strong>
                    {!hasDisplayData
                      ? "No telemetry available for diagnosis."
                      : Array.isArray(diagnosis.evidence)
                      ? diagnosis.evidence.slice(0, 3).join(", ")
                      : String(diagnosis.evidence || "Physics and ML evidence unavailable.")}
                  </strong>
                </div>
              </div>
              <div className="recommended-action">
                <CircleCheck size={18} />
                <div><span>Recommended Action</span><strong>{hasDisplayData ? diagnosis.recommendation : "Unavailable until telemetry is received."}</strong></div>
              </div>
            </section>

            <section className="maintenance-card">
              <div className="maintenance-icon"><ShieldAlert size={31} /></div>
              <h2>Proactive Maintenance for a Reliable Tomorrow</h2>
              <p>AI-powered insights help identify degradation early, optimize maintenance, and improve mission reliability.</p>
              <button
                className="primary-button"
                type="button"
                disabled={!hasDisplayData}
                onClick={() => setModal({
                  title: "AeroTwin Report",
                  body: (
                    <div className="report-modal">
                      <div><span>Engine</span><strong>{engine.engine_id}</strong></div>
                      <div><span>Health</span><strong>{health.toFixed(0)}%</strong></div>
                      <div><span>Fault</span><strong>{diagnosis.fault}</strong></div>
                      <div><span>RUL</span><strong>{rulHours.toFixed(0)} hours</strong></div>
                      <p>Report generation is connected to the dashboard action. Export integration can be attached to this workflow next.</p>
                    </div>
                  ),
                })}
              >
                <FileText size={17} /> Generate Report
              </button>
            </section>
          </div>
        </section>
      </main>

      {themeOpen && (
        <div className="theme-popover">
          <div className="theme-popover-header">
            <strong>Dashboard Background</strong>
            <button type="button" className="icon-button" onClick={() => setThemeOpen(false)}><X size={17} /></button>
          </div>
          <div className="theme-options">
            {THEMES.map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" className={theme === id ? "theme-option selected" : "theme-option"} onClick={() => setThemeAndClose(id)}>
                <span className={`theme-swatch ${id}`}><Icon size={17} /></span>
                <span>{label}</span>
                {theme === id && <CircleCheck size={17} />}
              </button>
            ))}
          </div>
        </div>
      )}

      {notice && <div className="toast"><CircleCheck size={17} /> {notice}</div>}

      {modal && (
        <Modal title={modal.title} onClose={() => setModal(null)}>
          {modal.body}
        </Modal>
      )}
    </div>
  );
}

export default App;
