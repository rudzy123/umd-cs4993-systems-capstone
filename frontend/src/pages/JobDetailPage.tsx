import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { cancelJob, errorText, getJob } from "../api";
import { ResultView } from "../components/ResultView";
import { StatusBadge } from "../components/StatusBadge";
import { formatTimestamp } from "../format";
import type { Job } from "../types";
import { JOB_LABELS, isTerminal } from "../types";

export function JobDetailPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingCancel, setPendingCancel] = useState(false);

  useEffect(() => {
    let stop = false;
    let timer = 0;

    async function load() {
      try {
        const next = await getJob(jobId);
        if (stop) {
          return;
        }
        setJob(next);
        setError(null);
        if (isTerminal(next.status)) {
          window.clearInterval(timer);
        }
      } catch (caught) {
        if (!stop) {
          setError(errorText(caught));
        }
      } finally {
        if (!stop) {
          setLoading(false);
        }
      }
    }

    void load();
    timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [jobId]);

  useEffect(() => {
    document.title = job ? `${JOB_LABELS[job.job_type]} job` : "Job detail";
  }, [job]);

  async function onCancel() {
    if (!job) {
      return;
    }
    setPendingCancel(true);
    setError(null);
    try {
      setJob(await cancelJob(job.id));
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setPendingCancel(false);
    }
  }

  return (
    <>
      <p>
        <Link to="/">Back to jobs</Link>
      </p>
      <h1>Job detail</h1>
      {loading && !job && <p role="status">Loading job…</p>}
      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {job && (
        <article className="panel">
          <p aria-live="polite">
            Status <StatusBadge status={job.status} />
          </p>
          <dl className="facts">
            <div>
              <dt>Type</dt>
              <dd>{JOB_LABELS[job.job_type]}</dd>
            </div>
            <div>
              <dt>Submitted</dt>
              <dd>
                <time dateTime={job.created_at}>{formatTimestamp(job.created_at)}</time>
              </dd>
            </div>
            <div>
              <dt>Retries</dt>
              <dd>
                {job.retry_count} of {job.max_retries}
              </dd>
            </div>
          </dl>
          {(job.status === "queued" || job.status === "retrying") && (
            <button type="button" onClick={() => void onCancel()} disabled={pendingCancel}>
              {pendingCancel ? "Cancelling…" : "Cancel queued job"}
            </button>
          )}
          <h2>Result</h2>
          <ResultView job={job} />
          <h2>Attempts</h2>
          {job.attempts.length === 0 ? (
            <p>No worker has claimed this job yet.</p>
          ) : (
            <ol className="attempts">
              {job.attempts.map((attempt) => (
                <li key={attempt.attempt_number}>
                  Attempt {attempt.attempt_number}: {attempt.status}
                  {attempt.error_summary ? ` — ${attempt.error_summary}` : ""}
                </li>
              ))}
            </ol>
          )}
        </article>
      )}
    </>
  );
}
