import type { JobStatus } from "../types";
import { STATUS_LABELS } from "../types";

export function StatusBadge({ status }: { status: JobStatus }) {
  const label = STATUS_LABELS[status] ?? status;
  return (
    <span className={`status status-${status}`}>
      <span className="status-mark" aria-hidden="true" />
      {label}
    </span>
  );
}
