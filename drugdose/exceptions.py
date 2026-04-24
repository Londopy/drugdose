"""Custom exceptions for the drugdose library."""


class DrugDoseError(Exception):
    """Base exception for all drugdose errors."""


class DrugNotFoundError(DrugDoseError):
    """Raised when a requested drug is not in the database."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Drug not found: '{name}'. Use `drugdose list` to see available drugs.")


class InvalidRouteError(DrugDoseError):
    """Raised when the requested route is not available for a drug."""

    def __init__(self, drug: str, route: str, available: list[str]):
        self.drug = drug
        self.route = route
        self.available = available
        super().__init__(
            f"Route '{route}' not available for {drug}. "
            f"Available routes: {', '.join(available)}"
        )


class InvalidPatientError(DrugDoseError):
    """Raised when patient parameters are invalid."""


class ContraindicatedError(DrugDoseError):
    """Raised when a drug is absolutely contraindicated for the given patient."""

    def __init__(self, drug: str, reasons: list[str]):
        self.drug = drug
        self.reasons = reasons
        super().__init__(
            f"{drug} is CONTRAINDICATED: {'; '.join(reasons)}"
        )


class WeightError(DrugDoseError):
    """Raised when weight is missing or out of a physiologic range."""


class ConcentrationError(DrugDoseError):
    """Raised when no concentration is provided and none is in the database."""
