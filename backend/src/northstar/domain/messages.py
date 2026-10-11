"""User-facing error text with a hard length cap."""


def safe_summary(message: str, limit: int = 400) -> str:
    cleaned = " ".join(message.split())
    if not cleaned:
        return "The job failed."
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
