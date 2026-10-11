import type { Job } from "../types";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

export function ResultView({ job }: { job: Job }) {
  if (job.status === "failed") {
    return (
      <div className="banner error" role="alert">
        <p>{job.error_summary ?? "The job failed."}</p>
      </div>
    );
  }
  if (job.status === "cancelled") {
    return (
      <p className="banner warn" role="status">
        {job.error_summary ?? "This job was cancelled."}
      </p>
    );
  }
  if (job.status === "retrying" && job.error_summary) {
    return (
      <p className="banner warn" role="status">
        Last attempt: {job.error_summary}
      </p>
    );
  }
  if (!job.result) {
    return <p>The result will appear here when the job succeeds.</p>;
  }
  if (job.job_type === "sort") {
    const sorted = Array.isArray(job.result.sorted) ? job.result.sorted : [];
    return (
      <div>
        <p>
          Merge sort compared {String(job.result.comparisons)} times and returned {sorted.length} numbers.
        </p>
        <pre className="result-block">
          {sorted.join(", ")}
        </pre>
      </div>
    );
  }
  if (job.job_type === "shortest_path") {
    const path = Array.isArray(job.result.path) ? job.result.path.map(String) : [];
    const reachable = job.result.reachable === true;
    return (
      <div>
        {reachable ? (
          <p>
            Distance {String(job.result.distance)}. Path{" "}
            <span aria-label={path.join(" to ")}>{path.join(" → ")}</span>
          </p>
        ) : (
          <p>No path exists between the source and the target.</p>
        )}
      </div>
    );
  }
  if (job.job_type === "word_frequency") {
    const rows = Array.isArray(job.result.frequencies) ? job.result.frequencies : [];
    return (
      <div className="table-wrap">
        <p>
          {String(job.result.token_count)} tokens, {String(job.result.unique_count)} unique words.
        </p>
        <table>
          <caption>Word frequencies</caption>
          <thead>
            <tr>
              <th scope="col">Word</th>
              <th scope="col">Count</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const record = asRecord(row);
              const word = record ? String(record.word) : "";
              const count = record ? String(record.count) : "";
              return (
                <tr key={word}>
                  <td>{word}</td>
                  <td>{count}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <div>
      <p>
        F({String(job.result.n)}) has {String(job.result.digit_count)} digits.
      </p>
      <pre className="result-block fib-value">
        {String(job.result.value)}
      </pre>
    </div>
  );
}
