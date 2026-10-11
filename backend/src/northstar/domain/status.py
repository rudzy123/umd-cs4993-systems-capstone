"""Shared job type names and status names."""


class JobType:
    SORT = "sort"
    SHORTEST_PATH = "shortest_path"
    WORD_FREQUENCY = "word_frequency"
    FIBONACCI = "fibonacci"
    ALL = frozenset({SORT, SHORTEST_PATH, WORD_FREQUENCY, FIBONACCI})


class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TERMINAL = frozenset({SUCCEEDED, FAILED, CANCELLED})
    CLAIMABLE = frozenset({QUEUED, RETRYING})


class AttemptStatus:
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
