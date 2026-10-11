"""Strict payloads for the four supported job types."""

import re
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic.functional_validators import AfterValidator, BeforeValidator

from northstar.domain.errors import InputValidationError
from northstar.domain.numbers import canonicalize
from northstar.domain.status import JobType

MAX_SORT_ITEMS = 10_000
MAX_NODES = 300
MAX_EDGES = 2_000
MAX_TEXT_CHARS = 100_000
MAX_FIBONACCI_N = 10_000
NODE_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
_NODE_RE = re.compile(NODE_PATTERN)


def _reject_non_numeric(value: object) -> object:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("must be a finite number")
    return value


def _finite_number(value: float) -> float:
    numeric = float(value)
    if numeric != numeric or numeric in (float("inf"), float("-inf")) or abs(numeric) > 10**15:
        raise ValueError("must be a finite number within the allowed magnitude")
    return numeric


FiniteNumber = Annotated[
    float, BeforeValidator(_reject_non_numeric), AfterValidator(_finite_number)
]


class SortInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numbers: list[FiniteNumber] = Field(max_length=MAX_SORT_ITEMS)


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(pattern=NODE_PATTERN)
    target: str = Field(pattern=NODE_PATTERN)
    weight: FiniteNumber = Field(ge=0, le=1_000_000_000)


class ShortestPathInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[str] = Field(min_length=1, max_length=MAX_NODES)
    edges: list[Edge] = Field(max_length=MAX_EDGES)
    source: str = Field(pattern=NODE_PATTERN)
    target: str = Field(pattern=NODE_PATTERN)
    directed: bool = True

    @field_validator("nodes")
    @classmethod
    def node_ids(cls, values: list[str]) -> list[str]:
        for value in values:
            if _NODE_RE.fullmatch(value) is None:
                raise ValueError("node ids must use letters, numbers, underscore, or hyphen")
        if len(set(values)) != len(values):
            raise ValueError("nodes must be unique")
        return values

    @model_validator(mode="after")
    def endpoints_exist(self) -> Self:
        node_set = set(self.nodes)
        if self.source not in node_set:
            raise ValueError("source must be included in nodes")
        if self.target not in node_set:
            raise ValueError("target must be included in nodes")
        for edge in self.edges:
            if edge.source not in node_set or edge.target not in node_set:
                raise ValueError("every edge endpoint must be included in nodes")
        return self


class WordFrequencyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=MAX_TEXT_CHARS)
    top_n: int = Field(default=20, ge=1, le=100)


class FibonacciInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int = Field(ge=0, le=MAX_FIBONACCI_N)


JobInput = SortInput | ShortestPathInput | WordFrequencyInput | FibonacciInput

_MODELS: dict[str, type[BaseModel]] = {
    JobType.SORT: SortInput,
    JobType.SHORTEST_PATH: ShortestPathInput,
    JobType.WORD_FREQUENCY: WordFrequencyInput,
    JobType.FIBONACCI: FibonacciInput,
}


def _details_from_validation(exc: ValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        loc = ["input", *[str(part) for part in location]]
        message = str(error.get("msg", "Invalid value"))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        details.append({"loc": loc, "message": message})
    return details


def parse_job_input(job_type: str, payload: Any) -> JobInput:
    model_cls = _MODELS.get(job_type)
    if model_cls is None:
        raise InputValidationError([{"loc": ["job_type"], "message": "Unsupported job type."}])
    if not isinstance(payload, dict):
        raise InputValidationError([{"loc": ["input"], "message": "Input must be an object."}])
    try:
        parsed = model_cls.model_validate(payload)
    except ValidationError as exc:
        raise InputValidationError(_details_from_validation(exc)) from exc
    except ValueError as exc:
        raise InputValidationError([{"loc": ["input"], "message": str(exc)}]) from exc
    if isinstance(parsed, SortInput | ShortestPathInput | WordFrequencyInput | FibonacciInput):
        return parsed
    raise InputValidationError([{"loc": ["job_type"], "message": "Unsupported job type."}])


def canonical_payload(model: BaseModel) -> dict[str, Any]:
    dumped = canonicalize(model.model_dump(mode="json"))
    if not isinstance(dumped, dict):
        raise InputValidationError([{"loc": ["input"], "message": "Input must be an object."}])
    return dumped
