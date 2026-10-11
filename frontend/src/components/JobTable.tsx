import { Link } from "react-router-dom";

import { formatTimestamp } from "../format";
import type { Job } from "../types";
import { JOB_LABELS } from "../types";
import { StatusBadge } from "./StatusBadge";

export function JobTable({
  jobs,
  loading,
  error,
}: {
  jobs: Job[] | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading && jobs === null) {
    return <p role="status">Loading jobs…</p>;
  }
  if (error && jobs === null) {
    return (
      <div className="banner error" role="alert">
        <p>{error}</p>
      </div>
    );
  }
  if (!jobs || jobs.length === 0) {
    return <p>No jobs yet. Submit a job to begin.</p>;
  }
  return (
    <div className="table-wrap">
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      <table>
        <caption>Recent jobs</caption>
        <thead>
          <tr>
            <th scope="col">Submitted</th>
            <th scope="col">Type</th>
            <th scope="col">Status</th>
            <th scope="col">Detail</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id}>
              <td>
                <time dateTime={job.created_at}>{formatTimestamp(job.created_at)}</time>
              </td>
              <td>{JOB_LABELS[job.job_type]}</td>
              <td>
                <StatusBadge status={job.status} />
              </td>
              <td>
                <Link to={`/jobs/${job.id}`}>View job</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
