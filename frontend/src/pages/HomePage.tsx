import { useEffect, useState } from "react";

import { errorText, listJobs } from "../api";
import { JobForm } from "../components/JobForm";
import { JobTable } from "../components/JobTable";
import type { Job } from "../types";

export function HomePage() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;

    async function load() {
      try {
        const body = await listJobs();
        if (!stop) {
          setJobs(body.jobs);
          setError(null);
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
    const timer = window.setInterval(() => {
      void load();
    }, 3000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <>
      <h1>Submit a job</h1>
      <p className="lede">
        The API validates the request, PostgreSQL stores it, and a separate worker claims and runs it.
      </p>
      <div className="layout">
        <JobForm
          onCreated={(job) => {
            setJobs((current) => [job, ...(current ?? []).filter((item) => item.id !== job.id)]);
          }}
        />
        <section className="panel" aria-labelledby="recent-heading">
          <h2 id="recent-heading">Recent jobs</h2>
          <p className="hint">This list refreshes automatically.</p>
          <JobTable jobs={jobs} loading={loading} error={error} />
        </section>
      </div>
    </>
  );
}
