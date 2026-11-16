export type TelemetrySummary = {
  samples: number;
  max_utilization_pct: number;
  average_utilization_pct: number;
};

export type Experiment = {
  id: number;
  controller: string;
  topology: string;
  failure_link: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown>;
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string }>("/api/health"),
  telemetry: () => get<{ summary: TelemetrySummary }>("/api/telemetry?limit=100"),
  experiments: () => get<Experiment[]>("/api/experiments"),
  topologies: () => get<Record<string, { nodes: string[]; links: unknown[] }>>("/api/topologies"),
};

