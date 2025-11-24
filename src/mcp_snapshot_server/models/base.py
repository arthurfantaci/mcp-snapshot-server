"""Base model configuration for all Pydantic models."""

from pydantic import BaseModel, ConfigDict


class SnapshotBaseModel(BaseModel):
    """Base model with common configuration for all models.

    Configuration:
    - frozen=False: Allow mutation after creation
    - extra="forbid": Reject unexpected fields (strict validation)
    - validate_assignment=True: Validate on attribute assignment
    - str_strip_whitespace=True: Strip whitespace from string fields
    """

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )
