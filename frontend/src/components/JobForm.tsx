import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { createJob, errorText } from "../api";
import { GUIDANCE, buildSubmission } from "../forms";
import type { Job, JobType } from "../types";
import { JOB_LABELS } from "../types";

const JOB_TYPES: JobType[] = ["sort", "shortest_path", "word_frequency", "fibonacci"];

export function JobForm({ onCreated }: { onCreated: (job: Job) => void }) {
  const [jobType, setJobType] = useState<JobType>("sort");
  const [numbers, setNumbers] = useState("3, 1, 2");
  const [nodes, setNodes] = useState("A, B, C");
  const [edges, setEdges] = useState("A B 1\nB C 2\nA C 10");
  const [source, setSource] = useState("A");
  const [target, setTarget] = useState("C");
  const [directed, setDirected] = useState(true);
  const [text, setText] = useState("The cat sat on the mat.");
  const [topN, setTopN] = useState("10");
  const [fibonacciN, setFibonacciN] = useState("20");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submission = buildSubmission({
      jobType,
      numbers,
      nodes,
      edges,
      source,
      target,
      directed,
      text,
      topN,
      fibonacciN,
    });
    if (!submission.ok) {
      setCreatedId(null);
      setError(submission.error);
      return;
    }
    setPending(true);
    setError(null);
    try {
      const job = await createJob(submission.jobType, submission.input);
      setCreatedId(job.id);
      onCreated(job);
    } catch (caught) {
      setCreatedId(null);
      setError(errorText(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="panel form" onSubmit={onSubmit} noValidate>
      <div className="field">
        <label htmlFor="job-type">Job type</label>
        <select
          id="job-type"
          value={jobType}
          aria-describedby="job-guidance"
          onChange={(event) => {
            setJobType(event.target.value as JobType);
            setError(null);
            setCreatedId(null);
          }}
        >
          {JOB_TYPES.map((type) => (
            <option key={type} value={type}>
              {JOB_LABELS[type]}
            </option>
          ))}
        </select>
        <p id="job-guidance">{GUIDANCE[jobType]}</p>
      </div>

      {jobType === "sort" && (
        <div className="field">
          <label htmlFor="numbers">Numbers</label>
          <textarea
            id="numbers"
            value={numbers}
            onChange={(event) => setNumbers(event.target.value)}
            rows={4}
            spellCheck={false}
          />
        </div>
      )}

      {jobType === "shortest_path" && (
        <>
          <div className="field">
            <label htmlFor="nodes">Nodes</label>
            <input id="nodes" value={nodes} onChange={(event) => setNodes(event.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="edges">Edges</label>
            <textarea
              id="edges"
              value={edges}
              onChange={(event) => setEdges(event.target.value)}
              rows={5}
              spellCheck={false}
            />
          </div>
          <div className="split">
            <div className="field">
              <label htmlFor="source">Source</label>
              <input id="source" value={source} onChange={(event) => setSource(event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="target">Target</label>
              <input id="target" value={target} onChange={(event) => setTarget(event.target.value)} />
            </div>
          </div>
          <div className="check">
            <input
              id="directed"
              type="checkbox"
              checked={directed}
              onChange={(event) => setDirected(event.target.checked)}
            />
            <label htmlFor="directed">Directed graph</label>
          </div>
        </>
      )}

      {jobType === "word_frequency" && (
        <>
          <div className="field">
            <label htmlFor="text">Text</label>
            <textarea id="text" value={text} onChange={(event) => setText(event.target.value)} rows={6} />
          </div>
          <div className="field">
            <label htmlFor="top-n">Top words</label>
            <input
              id="top-n"
              inputMode="numeric"
              value={topN}
              onChange={(event) => setTopN(event.target.value)}
            />
          </div>
        </>
      )}

      {jobType === "fibonacci" && (
        <div className="field">
          <label htmlFor="fibonacci-n">Fibonacci n</label>
          <input
            id="fibonacci-n"
            inputMode="numeric"
            value={fibonacciN}
            onChange={(event) => setFibonacciN(event.target.value)}
          />
        </div>
      )}

      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {createdId && (
        <p className="banner success" role="status">
          Job submitted. <Link to={`/jobs/${createdId}`}>View this job</Link>
        </p>
      )}
      <button type="submit" disabled={pending}>
        {pending ? "Submitting…" : "Submit job"}
      </button>
    </form>
  );
}
