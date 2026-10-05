from threading import Lock

from services.simulator.engine_simulator import EngineSimulator


class SimulatorController:
    """
    Controls the shared AeroTwin engine simulator state.

    Development implementation for the AeroTwin demonstrator.
    """

    def __init__(self):
        self.simulator = EngineSimulator()
        self.lock = Lock()

    def inject_fault(
        self,
        fault: str,
        severity: float = 1.0,
    ) -> dict:

        with self.lock:
            self.simulator.inject_fault(
                fault=fault,
                severity=severity,
            )

            return {
                "status": "FAULT_INJECTED",
                "fault": fault,
                "severity": self.simulator.fault_severity,
            }

    def clear_fault(self) -> dict:

        with self.lock:
            self.simulator.clear_fault()

            return {
                "status": "FAULT_CLEARED",
            }

    def step(self):
        with self.lock:
            return self.simulator.step()


simulator_controller = SimulatorController()