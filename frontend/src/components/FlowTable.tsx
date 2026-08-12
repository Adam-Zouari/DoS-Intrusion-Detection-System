import { useEffect, useMemo, useState } from 'react';
import { fetchFlows } from '../services/api';
import type { FlowPage, FlowRecord } from '../types/api';

type TrafficScope = 'all' | 'attacks' | 'benign';
type SortDirection = 'asc' | 'desc';

interface FilterState {
  trafficScope: TrafficScope;
  label: string;
  sourceIp: string;
  sourcePort: string;
  destinationIp: string;
  destinationPort: string;
  protocol: string;
  receivedFrom: string;
  receivedTo: string;
  minPackets: string;
  maxPackets: string;
  minBytes: string;
  maxBytes: string;
  minDurationMs: string;
  maxDurationMs: string;
  minLatencyMs: string;
  maxLatencyMs: string;
  sortBy: string;
  sortDirection: SortDirection;
  pageSize: number;
}

interface Props {
  labels: string[];
  liveFlow: FlowRecord | null;
}

const defaultFilters: FilterState = {
  trafficScope: 'all',
  label: '',
  sourceIp: '',
  sourcePort: '',
  destinationIp: '',
  destinationPort: '',
  protocol: '',
  receivedFrom: '',
  receivedTo: '',
  minPackets: '',
  maxPackets: '',
  minBytes: '',
  maxBytes: '',
  minDurationMs: '',
  maxDurationMs: '',
  minLatencyMs: '',
  maxLatencyMs: '',
  sortBy: 'received_at',
  sortDirection: 'desc',
  pageSize: 50,
};

const emptyPage: FlowPage = { items: [], total: 0, page: 1, page_size: 50 };

const contains = (value: string, query: string) =>
  value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());

const inNumericRange = (value: number, minimum: string, maximum: string) =>
  (!minimum || value >= Number(minimum)) && (!maximum || value <= Number(maximum));

const matchesFilters = (flow: FlowRecord, filters: FilterState) => {
  if (filters.trafficScope === 'attacks' && flow.prediction === 'BENIGN') return false;
  if (filters.trafficScope === 'benign' && flow.prediction !== 'BENIGN') return false;
  if (filters.label && flow.prediction !== filters.label) return false;
  if (filters.sourceIp && !contains(flow.source_ip, filters.sourceIp)) return false;
  if (filters.sourcePort && flow.source_port !== Number(filters.sourcePort)) return false;
  if (filters.destinationIp && !contains(flow.destination_ip, filters.destinationIp)) return false;
  if (filters.destinationPort && flow.destination_port !== Number(filters.destinationPort)) return false;
  if (filters.protocol && flow.protocol !== Number(filters.protocol)) return false;
  const received = new Date(flow.received_at).getTime();
  if (filters.receivedFrom && received < new Date(filters.receivedFrom).getTime()) return false;
  if (filters.receivedTo && received > new Date(filters.receivedTo).getTime()) return false;
  return (
    inNumericRange(flow.total_packets, filters.minPackets, filters.maxPackets)
    && inNumericRange(flow.total_bytes, filters.minBytes, filters.maxBytes)
    && inNumericRange(flow.duration_ms, filters.minDurationMs, filters.maxDurationMs)
    && inNumericRange(flow.inference_latency_ms, filters.minLatencyMs, filters.maxLatencyMs)
  );
};

const sortValue = (flow: FlowRecord, sortBy: string): string | number => {
  const values: Record<string, string | number> = {
    received_at: flow.received_at,
    prediction: flow.prediction,
    source_ip: flow.source_ip,
    source_port: flow.source_port,
    destination_ip: flow.destination_ip,
    destination_port: flow.destination_port,
    protocol: flow.protocol,
    packets: flow.total_packets,
    bytes: flow.total_bytes,
    duration: flow.duration_ms,
    latency: flow.inference_latency_ms,
  };
  return values[sortBy];
};

const sortFlows = (flows: FlowRecord[], filters: FilterState) => {
  const direction = filters.sortDirection === 'asc' ? 1 : -1;
  return [...flows].sort((left, right) => {
    const leftValue = sortValue(left, filters.sortBy);
    const rightValue = sortValue(right, filters.sortBy);
    const comparison = typeof leftValue === 'string'
      ? leftValue.localeCompare(String(rightValue))
      : leftValue - Number(rightValue);
    return comparison === 0 ? (left.id - right.id) * direction : comparison * direction;
  });
};

const FlowTable = ({ labels, liveFlow }: Props) => {
  const [data, setData] = useState<FlowPage>(emptyPage);
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<FilterState>(defaultFilters);
  const [applied, setApplied] = useState<FilterState>(defaultFilters);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchFlows({
      page,
      pageSize: applied.pageSize,
      trafficScope: applied.trafficScope,
      label: applied.label,
      sourceIp: applied.sourceIp,
      sourcePort: applied.sourcePort,
      destinationIp: applied.destinationIp,
      destinationPort: applied.destinationPort,
      protocol: applied.protocol,
      receivedFrom: applied.receivedFrom,
      receivedTo: applied.receivedTo,
      minPackets: applied.minPackets,
      maxPackets: applied.maxPackets,
      minBytes: applied.minBytes,
      maxBytes: applied.maxBytes,
      minDurationMs: applied.minDurationMs,
      maxDurationMs: applied.maxDurationMs,
      minLatencyMs: applied.minLatencyMs,
      maxLatencyMs: applied.maxLatencyMs,
      sortBy: applied.sortBy,
      sortDirection: applied.sortDirection,
    })
      .then((next) => {
        if (active) {
          setData(next);
          setError(null);
        }
      })
      .catch((requestError) => {
        if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load flows');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [applied, page]);

  useEffect(() => {
    if (!liveFlow || !matchesFilters(liveFlow, applied)) return;
    setData((current) => {
      if (current.items.some((flow) => flow.id === liveFlow.id)) return current;
      const items = page === 1
        ? sortFlows([liveFlow, ...current.items], applied).slice(0, applied.pageSize)
        : current.items;
      return { ...current, items, total: current.total + 1 };
    });
  }, [applied, liveFlow, page]);

  const activeFilterCount = useMemo(() => {
    const ignored = new Set(['trafficScope', 'sortBy', 'sortDirection', 'pageSize']);
    const values = Object.entries(applied).filter(([key, value]) => !ignored.has(key) && value !== '');
    return values.length + (applied.trafficScope === 'all' ? 0 : 1);
  }, [applied]);

  const update = (field: keyof FilterState, value: string | number) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const changeScope = (trafficScope: TrafficScope) => {
    setDraft((current) => ({
      ...current,
      trafficScope,
      label: trafficScope === 'benign' || (trafficScope === 'attacks' && current.label === 'BENIGN')
        ? ''
        : current.label,
    }));
  };

  const applyFilters = () => {
    setPage(1);
    setApplied({ ...draft });
  };

  const resetFilters = () => {
    setDraft(defaultFilters);
    setPage(1);
    setApplied(defaultFilters);
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <section className="panel flow-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Live rows with server-side querying</p>
          <h2>Completed flow explorer</h2>
          <span className="filter-summary">{activeFilterCount} active filters · new matching flows appear without reloading</span>
        </div>
        <strong>{data.total.toLocaleString()} matching records</strong>
      </div>

      <form className="filter-panel" onSubmit={(event) => { event.preventDefault(); applyFilters(); }}>
        <div className="filter-section scope-filter">
          <span>Traffic</span>
          <div className="segmented-control">
            {(['all', 'attacks', 'benign'] as const).map((scope) => (
              <button
                type="button"
                key={scope}
                className={draft.trafficScope === scope ? 'active' : ''}
                onClick={() => changeScope(scope)}
              >
                {scope === 'all' ? 'All flows' : scope === 'attacks' ? 'All attacks' : 'Benign only'}
              </button>
            ))}
          </div>
        </div>

        <div className="filters identity-filters">
          <label>Prediction
            <select value={draft.label} disabled={draft.trafficScope === 'benign'} onChange={(event) => update('label', event.target.value)}>
              <option value="">Any label</option>
              {labels.filter((label) => draft.trafficScope !== 'attacks' || label !== 'BENIGN').map((label) => (
                <option value={label} key={label}>{label}</option>
              ))}
            </select>
          </label>
          <label>Protocol
            <select value={draft.protocol} onChange={(event) => update('protocol', event.target.value)}>
              <option value="">Any protocol</option>
              <option value="0">HOPOPT (0)</option>
              <option value="1">ICMP (1)</option>
              <option value="6">TCP (6)</option>
              <option value="17">UDP (17)</option>
            </select>
          </label>
        </div>

        <div className="filters endpoint-filters">
          <label>Source IP contains<input value={draft.sourceIp} onChange={(event) => update('sourceIp', event.target.value)} /></label>
          <label>Source port<input type="number" min="0" max="65535" value={draft.sourcePort} onChange={(event) => update('sourcePort', event.target.value)} /></label>
          <label>Destination IP contains<input value={draft.destinationIp} onChange={(event) => update('destinationIp', event.target.value)} /></label>
          <label>Destination port<input type="number" min="0" max="65535" value={draft.destinationPort} onChange={(event) => update('destinationPort', event.target.value)} /></label>
        </div>

        <div className="filters time-filters">
          <label>Received from<input type="datetime-local" value={draft.receivedFrom} onChange={(event) => update('receivedFrom', event.target.value)} /></label>
          <label>Received to<input type="datetime-local" value={draft.receivedTo} onChange={(event) => update('receivedTo', event.target.value)} /></label>
        </div>

        <div className="range-grid">
          <fieldset><legend>Packets</legend><input aria-label="Minimum packets" type="number" min="0" placeholder="Min" value={draft.minPackets} onChange={(event) => update('minPackets', event.target.value)} /><input aria-label="Maximum packets" type="number" min="0" placeholder="Max" value={draft.maxPackets} onChange={(event) => update('maxPackets', event.target.value)} /></fieldset>
          <fieldset><legend>Bytes</legend><input aria-label="Minimum bytes" type="number" min="0" placeholder="Min" value={draft.minBytes} onChange={(event) => update('minBytes', event.target.value)} /><input aria-label="Maximum bytes" type="number" min="0" placeholder="Max" value={draft.maxBytes} onChange={(event) => update('maxBytes', event.target.value)} /></fieldset>
          <fieldset><legend>Duration (ms)</legend><input aria-label="Minimum duration" type="number" min="0" step="any" placeholder="Min" value={draft.minDurationMs} onChange={(event) => update('minDurationMs', event.target.value)} /><input aria-label="Maximum duration" type="number" min="0" step="any" placeholder="Max" value={draft.maxDurationMs} onChange={(event) => update('maxDurationMs', event.target.value)} /></fieldset>
          <fieldset><legend>Inference (ms)</legend><input aria-label="Minimum latency" type="number" min="0" step="any" placeholder="Min" value={draft.minLatencyMs} onChange={(event) => update('minLatencyMs', event.target.value)} /><input aria-label="Maximum latency" type="number" min="0" step="any" placeholder="Max" value={draft.maxLatencyMs} onChange={(event) => update('maxLatencyMs', event.target.value)} /></fieldset>
        </div>

        <div className="filter-actions">
          <label>Sort by
            <select value={draft.sortBy} onChange={(event) => update('sortBy', event.target.value)}>
              <option value="received_at">Received time</option><option value="prediction">Prediction</option>
              <option value="source_ip">Source IP</option><option value="source_port">Source port</option>
              <option value="destination_ip">Destination IP</option><option value="destination_port">Destination port</option>
              <option value="protocol">Protocol</option><option value="packets">Packets</option>
              <option value="bytes">Bytes</option><option value="duration">Duration</option><option value="latency">Inference latency</option>
            </select>
          </label>
          <label>Direction
            <select value={draft.sortDirection} onChange={(event) => update('sortDirection', event.target.value)}>
              <option value="desc">Descending</option><option value="asc">Ascending</option>
            </select>
          </label>
          <label>Rows per page
            <select value={draft.pageSize} onChange={(event) => update('pageSize', Number(event.target.value))}>
              <option value={25}>25</option><option value={50}>50</option><option value={100}>100</option><option value={200}>200</option>
            </select>
          </label>
          <button className="secondary-button" type="button" onClick={resetFilters}>Reset</button>
          <button className="primary-button" type="submit">Apply filters</button>
        </div>
      </form>

      {error && <div className="inline-error">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Received</th><th>Flow timestamp</th><th>Prediction</th><th>Source</th><th>Destination</th><th>Protocol</th><th>Packets</th><th>Bytes</th><th>Duration</th><th>Inference</th></tr></thead>
          <tbody>
            {!loading && data.items.map((flow) => (
              <tr key={flow.id} className={flow.prediction === 'BENIGN' ? '' : 'attack-row'}>
                <td>{new Date(flow.received_at).toLocaleString()}</td><td>{flow.flow_timestamp}</td>
                <td><span className={`prediction ${flow.prediction === 'BENIGN' ? 'benign' : 'attack'}`}>{flow.prediction}</span></td>
                <td>{flow.source_ip}:{flow.source_port}</td><td>{flow.destination_ip}:{flow.destination_port}</td><td>{flow.protocol_name}</td>
                <td>{Math.round(flow.total_packets).toLocaleString()}</td><td>{Math.round(flow.total_bytes).toLocaleString()}</td>
                <td>{flow.duration_ms.toLocaleString(undefined, { maximumFractionDigits: 3 })} ms</td><td>{flow.inference_latency_ms.toFixed(2)} ms</td>
              </tr>
            ))}
            {loading && <tr><td colSpan={10} className="empty-state">Loading flows…</td></tr>}
            {!loading && !data.items.length && <tr><td colSpan={10} className="empty-state">No completed flows match the applied filters.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</button>
      </div>
    </section>
  );
};

export default FlowTable;
