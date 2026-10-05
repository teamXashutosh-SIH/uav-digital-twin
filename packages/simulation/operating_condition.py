from dataclasses import dataclass


@dataclass
class OperatingCondition:
    """
    Current engine operating condition.

    Development/demo representation of the conditions
    used by the mission simulator.
    """

    throttle_pct: float
    altitude_m: float
    ambient_temperature_c: float


@dataclass
class OperatingConditionStatus:
    """
    Describes whether the engine is in a steady operating
    condition or transitioning between operating points.
    """

    is_transition: bool

    transition_samples_remaining: int

    throttle_change_pct: float

    altitude_change_m: float

    temperature_change_c: float


class OperatingConditionTracker:
    """
    Detects transitions between engine operating points.

    The first operating point is also treated as an
    initialization transient because the simulated engine
    may require several samples to settle from its initial
    state.

    The tracker does NOT modify telemetry or health scores.

    It only provides operating-condition context to
    downstream analysis.
    """

    def __init__(
        self,
        transition_duration_samples: int = 5,
        initial_transient_samples: int = 5,
        throttle_threshold_pct: float = 5.0,
        altitude_threshold_m: float = 250.0,
        temperature_threshold_c: float = 5.0,
    ):

        self.transition_duration_samples = (
            transition_duration_samples
        )

        self.initial_transient_samples = (
            initial_transient_samples
        )

        self.throttle_threshold_pct = (
            throttle_threshold_pct
        )

        self.altitude_threshold_m = (
            altitude_threshold_m
        )

        self.temperature_threshold_c = (
            temperature_threshold_c
        )

        self.previous_condition = None

        self.transition_samples_remaining = 0

    def reset(self) -> None:
        """
        Reset the operating-condition history.
        """

        self.previous_condition = None

        self.transition_samples_remaining = (
            self.initial_transient_samples
        )

    def update(
        self,
        throttle_pct: float,
        altitude_m: float,
        ambient_temperature_c: float,
    ) -> OperatingConditionStatus:
        """
        Update the tracker with the current operating point.
        """

        current_condition = OperatingCondition(
            throttle_pct=throttle_pct,
            altitude_m=altitude_m,
            ambient_temperature_c=(
                ambient_temperature_c
            ),
        )

        # First sample establishes the baseline.
        #
        # It is nevertheless considered part of the
        # initial engine settling period.
        if self.previous_condition is None:

            self.previous_condition = (
                current_condition
            )

            remaining = (
                self.transition_samples_remaining
            )

            if remaining > 0:
                self.transition_samples_remaining -= 1

            return OperatingConditionStatus(
                is_transition=(
                    remaining > 0
                ),
                transition_samples_remaining=(
                    remaining
                ),
                throttle_change_pct=0.0,
                altitude_change_m=0.0,
                temperature_change_c=0.0,
            )

        throttle_change = (
            current_condition.throttle_pct
            - self.previous_condition.throttle_pct
        )

        altitude_change = (
            current_condition.altitude_m
            - self.previous_condition.altitude_m
        )

        temperature_change = (
            current_condition.ambient_temperature_c
            - self.previous_condition.ambient_temperature_c
        )

        operating_point_changed = (
            abs(throttle_change)
            >= self.throttle_threshold_pct
            or
            abs(altitude_change)
            >= self.altitude_threshold_m
            or
            abs(temperature_change)
            >= self.temperature_threshold_c
        )

        if operating_point_changed:

            self.transition_samples_remaining = (
                self.transition_duration_samples
            )

        elif (
            self.transition_samples_remaining > 0
        ):

            self.transition_samples_remaining -= 1

        is_transition = (
            self.transition_samples_remaining > 0
        )

        self.previous_condition = (
            current_condition
        )

        return OperatingConditionStatus(
            is_transition=is_transition,
            transition_samples_remaining=(
                self.transition_samples_remaining
            ),
            throttle_change_pct=float(
                throttle_change
            ),
            altitude_change_m=float(
                altitude_change
            ),
            temperature_change_c=float(
                temperature_change
            ),
        )