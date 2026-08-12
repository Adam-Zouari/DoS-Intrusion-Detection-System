import { useCallback, useEffect, useRef, useState } from 'react';
import FlowTable from './components/FlowTable';
import ModelPanel from './components/ModelPanel';
import SummaryView from './components/SummaryView';
import {
  fetchHealth,
  fetchModelInformation,
  fetchSummary,
  subscribeToEvents,
} from './services/api';
import type { FlowRecord, Health, ModelInformation, Summary } from './types/api';
import './App.css';

type View = 'overview' | 'flows' | 'model';

const App = () => {
  const [view, setView] = useState<View>('overview');
  const [health, setHealth] = useState<Health | null>(null);
  const [model, setModel] = useState<ModelInformation | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [streamConnected, setStreamConnected] = useState(false);
  const [latestFlow, setLatestFlow] = useState<FlowRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const [nextHealth, nextModel] = await Promise.all([
        fetchHealth(),
        fetchModelInformation(),
      ]);
      setHealth(nextHealth);
      setModel(nextModel);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Backend unavailable');
    }
  }, []);

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await fetchSummary(windowMinutes));
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not load summary');
    }
  }, [windowMinutes]);

  const scheduleSummaryRefresh = useCallback(() => {
    if (refreshTimer.current !== null) return;
    refreshTimer.current = setTimeout(() => {
      refreshTimer.current = null;
      void loadSummary();
      void loadStatus();
    }, 250);
  }, [loadStatus, loadSummary]);

  useEffect(() => {
    void loadStatus();
    const interval = setInterval(() => void loadStatus(), 10_000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    const unsubscribe = subscribeToEvents((flow) => {
      setLatestFlow(flow);
      scheduleSummaryRefresh();
    }, setStreamConnected);
    return () => {
      unsubscribe();
      if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
    };
  }, [scheduleSummaryRefresh]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Completed-flow classification</p>
          <h1>Intrusion Detection System</h1>
          <p className="subtitle">Multiclass XGBoost inference on CICFlowMeter-compatible flows</p>
        </div>
        <div className="status-cluster">
          <span className={`status-dot ${health?.model_ready ? 'ready' : 'offline'}`} />
          <div>
            <strong>{health?.model_ready ? 'Model ready' : 'Model unavailable'}</strong>
            <small>{streamConnected ? 'Live updates connected' : 'Live updates reconnecting'}</small>
          </div>
        </div>
      </header>

      <nav className="navigation" aria-label="Dashboard sections">
        {(
          [
            ['overview', 'Overview'],
            ['flows', 'Flow explorer'],
            ['model', 'Model'],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            className={view === key ? 'active' : ''}
            onClick={() => setView(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {error && <div className="error-banner">{error}</div>}

      <main>
        {view === 'overview' && (
          <SummaryView
            summary={summary}
            windowMinutes={windowMinutes}
            onWindowChange={setWindowMinutes}
          />
        )}
        {view === 'flows' && (
          <FlowTable
            labels={model?.labels ?? []}
            liveFlow={latestFlow}
          />
        )}
        {view === 'model' && <ModelPanel health={health} model={model} />}
      </main>

      <footer>
        {health?.source ?? 'Flow source unavailable'} · Predictions describe completed flows and do not prove that a network is secure.
      </footer>
    </div>
  );
};

export default App;
