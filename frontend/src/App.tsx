import { useEffect, useState } from "react";
import { api, Experiment, TelemetrySummary } from "./api";

type DashboardState = {
  health: string;
  telemetry: TelemetrySummary;
  experiments: Experiment[];
  topologyCount: number;
  error: string | null;
};

const initialState: DashboardState = {
  health: "loading",
  telemetry: { samples: 0, max_utilization_pct: 0, average_utilization_pct: 0 },
  experiments: [],
  topologyCount: 0,
  error: null,
};

export default function App() {
  const [state, setState] = useState(initialState);

  useEffect(() => {
    Promise.all([api.health(), api.telemetry(), api.experiments(), api.topologies()])
      .then(([health, telemetry, experiments, topologies]) => {
        setState({
          health: health.status,
          telemetry: telemetry.summary,
          experiments,
          topologyCount: Object.keys(topologies).length,
          error: null,
        });
      })
      .catch((error: Error) => setState((current) => ({ ...current, error: error.message })));
  }, []);

  return (
    <main className="shell">
      <header className="header">
        <div>
          <p className="eyebrow">NETWORK OPERATIONS</p>
          <h1>Self-Healing SDN</h1>
          <p className="muted">Observe, evaluate, and plan recovery experiments.</p>
        </div>
        <span className={`status ${state.health === "ok" ? "healthy" : ""}`}>
          API {state.health}
        </span>
      </header>

      {state.error && <div className="error">{state.error}</div>}

      <section className="cards">
        <article className="card"><span>Telemetry samples</span><strong>{state.telemetry.samples}</strong></article>
        <article className="card"><span>Average utilization</span><strong>{state.telemetry.average_utilization_pct}%</strong></article>
        <article className="card"><span>Peak utilization</span><strong>{state.telemetry.max_utilization_pct}%</strong></article>
        <article className="card"><span>Topology catalog</span><strong>{state.topologyCount}</strong></article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>Experiment history</h2>
          <span className="muted">{state.experiments.length} recorded</span>
        </div>
        {state.experiments.length === 0 ? (
          <p className="muted">No experiments have been planned yet.</p>
        ) : (
          <div className="table">
            {state.experiments.map((experiment) => (
              <div className="row" key={experiment.id}>
                <span>#{experiment.id}</span>
                <span>{experiment.controller}</span>
                <span>{experiment.topology}</span>
                <span>{experiment.failure_link ?? "No failure injected"}</span>
                <span className="tag">{experiment.status}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

