import type { JobType } from "./types";

export interface SubmissionFields {
  jobType: JobType;
  numbers: string;
  nodes: string;
  edges: string;
  source: string;
  target: string;
  directed: boolean;
  text: string;
  topN: string;
  fibonacciN: string;
}

export type Submission =
  | { ok: true; jobType: JobType; input: Record<string, unknown> }
  | { ok: false; error: string };

const NODE = /^[A-Za-z0-9_-]{1,64}$/;

export function parseNumbers(raw: string): number[] | string {
  const parts = raw.split(/[\s,]+/).filter((part) => part.length > 0);
  if (parts.length > 10000) {
    return "Enter at most 10,000 numbers.";
  }
  const numbers: number[] = [];
  for (const part of parts) {
    if (!/^-?(?:\d+\.?\d*|\.\d+)$/.test(part)) {
      return `"${part}" is not a finite number.`;
    }
    const value = Number(part);
    if (!Number.isFinite(value)) {
      return `"${part}" is not a finite number.`;
    }
    numbers.push(value);
  }
  return numbers;
}

export function parseNodes(raw: string): string[] | string {
  const nodes = raw.split(/[\s,]+/).filter((part) => part.length > 0);
  if (nodes.length === 0) {
    return "Enter at least one node.";
  }
  if (nodes.length > 300) {
    return "Enter at most 300 nodes.";
  }
  const seen = new Set<string>();
  for (const node of nodes) {
    if (!NODE.test(node)) {
      return `Node "${node}" uses unsupported characters.`;
    }
    if (seen.has(node)) {
      return `Node "${node}" is duplicated.`;
    }
    seen.add(node);
  }
  return nodes;
}

export function parseEdges(
  raw: string,
): { source: string; target: string; weight: number }[] | string {
  const edges: { source: string; target: string; weight: number }[] = [];
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    const parts = trimmed.split(/\s+/);
    if (parts.length !== 3) {
      return `Edge "${trimmed}" must be SOURCE TARGET WEIGHT.`;
    }
    const [source, target, weightText] = parts;
    if (!NODE.test(source) || !NODE.test(target)) {
      return `Edge "${trimmed}" has an invalid node id.`;
    }
    if (!/^(?:\d+\.?\d*|\.\d+)$/.test(weightText)) {
      return `Weight "${weightText}" must be zero or positive.`;
    }
    const weight = Number(weightText);
    if (!Number.isFinite(weight) || weight < 0) {
      return `Weight "${weightText}" must be zero or positive.`;
    }
    edges.push({ source, target, weight });
  }
  if (edges.length > 2000) {
    return "Enter at most 2,000 edges.";
  }
  return edges;
}

export function buildSubmission(fields: SubmissionFields): Submission {
  if (fields.jobType === "sort") {
    const numbers = parseNumbers(fields.numbers);
    if (typeof numbers === "string") {
      return { ok: false, error: numbers };
    }
    return { ok: true, jobType: "sort", input: { numbers } };
  }
  if (fields.jobType === "shortest_path") {
    const nodes = parseNodes(fields.nodes);
    if (typeof nodes === "string") {
      return { ok: false, error: nodes };
    }
    const edges = parseEdges(fields.edges);
    if (typeof edges === "string") {
      return { ok: false, error: edges };
    }
    if (!NODE.test(fields.source.trim()) || !NODE.test(fields.target.trim())) {
      return { ok: false, error: "Source and target must be node ids." };
    }
    return {
      ok: true,
      jobType: "shortest_path",
      input: {
        nodes,
        edges,
        source: fields.source.trim(),
        target: fields.target.trim(),
        directed: fields.directed,
      },
    };
  }
  if (fields.jobType === "word_frequency") {
    if (fields.text.length > 100000) {
      return { ok: false, error: "Text must be 100,000 characters or fewer." };
    }
    if (!/^\d+$/.test(fields.topN.trim())) {
      return { ok: false, error: "Top words must be a whole number from 1 through 100." };
    }
    const topN = Number(fields.topN.trim());
    if (topN < 1 || topN > 100) {
      return { ok: false, error: "Top words must be a whole number from 1 through 100." };
    }
    return { ok: true, jobType: "word_frequency", input: { text: fields.text, top_n: topN } };
  }
  if (!/^\d+$/.test(fields.fibonacciN.trim())) {
    return { ok: false, error: "Enter a whole number from 0 through 10000." };
  }
  const n = Number(fields.fibonacciN.trim());
  if (n > 10000) {
    return { ok: false, error: "Enter a whole number from 0 through 10000." };
  }
  return { ok: true, jobType: "fibonacci", input: { n } };
}

export const GUIDANCE: Record<JobType, string> = {
  sort: "Enter finite numbers separated by commas or whitespace. At most 10,000 numbers. Merge sort returns them in nondecreasing order.",
  shortest_path:
    "List node ids, then one edge per line as SOURCE TARGET WEIGHT. Weights must be zero or positive. At most 300 nodes and 2,000 edges. Dijkstra finds a deterministic shortest path.",
  word_frequency:
    "Paste text up to 100,000 characters. Words are letter and number tokens. Results rank by count, then by word.",
  fibonacci:
    "Enter n from 0 through 10,000. The worker uses bottom-up dynamic programming and returns the value as a decimal string.",
};
