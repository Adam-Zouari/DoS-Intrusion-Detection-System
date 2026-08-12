import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Summary } from '../types/api';

interface Props {
  summary: Summary | null;
  windowMinutes: number;
  onWindowChange: (minutes: number) => void;
}

const number = new Intl.NumberFormat();

const formatBytes = (value: number) => {
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)} GB`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)} MB`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)} kB`;
  return `${Math.round(value)} B`;
};

const SummaryView = ({ summary, windowMinutes, onWindowChange }: Props) => {
  if (!summary) return <section className="panel loading-panel">Loading summary…</section>;

  const timeline = summary.timeline.map((point) => ({
    ...point,
    time: new Date(point.bucket).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }));
  const attacks = summary.labels.filter((item) => item.label !== 'BENIGN');

  return (
    <div className="view-stack">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Backend-calculated statistics</p>
          <h2>Flow overview</h2>
        </div>
        <label className="window-picker">
          Window
          <select value={windowMinutes} onChange={(event) => onWindowChange(Number(event.target.value))}>
            <option value={15}>Last 15 minutes</option>
            <option value={60}>Last hour</option>
            <option value={360}>Last 6 hours</option>
            <option value={1440}>Last 24 hours</option>
            <option value={10080}>Last 7 days</option>
          </select>
        </label>
      </div>

      <section className="metric-grid">
        <article className="metric-card">
          <span>Completed flows</span>
          <strong>{number.format(summary.flow_count)}</strong>
        </article>
        <article className="metric-card danger-accent">
          <span>Detected attack flows</span>
          <strong>{number.format(summary.attack_count)}</strong>
          <small>{summary.attack_percentage.toFixed(2)}% of this window</small>
        </article>
        <article className="metric-card">
          <span>Transferred data</span>
          <strong>{formatBytes(summary.total_bytes)}</strong>
          <small>{number.format(Math.round(summary.total_packets))} packets</small>
        </article>
        <article className="metric-card">
          <span>Average inference</span>
          <strong>{summary.average_inference_latency_ms.toFixed(2)} ms</strong>
          <small>complete model pipeline</small>
        </article>
      </section>

      <section className="chart-grid">
        <article className="panel chart-panel wide">
          <div className="panel-title">
            <h3>Completed flows over time</h3>
            <span>Counts per received minute</span>
          </div>
          {timeline.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#24334c" />
                <XAxis dataKey="time" stroke="#91a1b7" />
                <YAxis stroke="#91a1b7" allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#111b2e', border: '1px solid #30415e' }} />
                <Legend />
                <Line type="monotone" dataKey="flows" stroke="#52c7ea" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="attacks" stroke="#ff6b78" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <div className="empty-state">No completed flows in this window.</div>}
        </article>

        <article className="panel chart-panel">
          <div className="panel-title">
            <h3>Attack-family distribution</h3>
            <span>Model predictions, excluding BENIGN</span>
          </div>
          {attacks.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={attacks} layout="vertical" margin={{ left: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#24334c" />
                <XAxis type="number" stroke="#91a1b7" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={120} stroke="#91a1b7" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#111b2e', border: '1px solid #30415e' }} />
                <Bar dataKey="count" fill="#ff6b78" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <div className="empty-state">No attack flows detected in this window.</div>}
        </article>

        <article className="panel protocol-panel">
          <div className="panel-title">
            <h3>Protocols</h3>
            <span>Completed-flow count</span>
          </div>
          <div className="protocol-list">
            {summary.protocols.map((protocol) => (
              <div key={protocol.protocol}>
                <span>{protocol.name}</span>
                <strong>{number.format(protocol.count)}</strong>
              </div>
            ))}
            {!summary.protocols.length && <div className="empty-state">No protocol data.</div>}
          </div>
        </article>
      </section>
    </div>
  );
};

export default SummaryView;
