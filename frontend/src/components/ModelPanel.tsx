import type { Health, ModelInformation } from '../types/api';

interface Props {
  health: Health | null;
  model: ModelInformation | null;
}

const ModelPanel = ({ health, model }: Props) => (
  <div className="model-layout">
    <section className="panel model-card">
      <p className="eyebrow">Deployed pipeline</p>
      <h2>{model?.family ?? 'Model unavailable'}</h2>
      <dl>
        <div><dt>Status</dt><dd>{model?.ready ? 'Ready' : 'Unavailable'}</dd></div>
        <div><dt>Task</dt><dd>{model?.task ?? '—'}</dd></div>
        <div><dt>Source features</dt><dd>{model?.source_feature_count ?? '—'}</dd></div>
        <div><dt>Transformed features</dt><dd>{model?.transformed_feature_count ?? '—'}</dd></div>
        <div><dt>Boosting iterations</dt><dd>{model?.boosting_iterations ?? '—'}</dd></div>
        <div><dt>Inference device</dt><dd>{model?.inference_device.toUpperCase() ?? '—'}</dd></div>
        <div><dt>Flow source</dt><dd>{health?.source ?? '—'}</dd></div>
        <div><dt>Stored flows</dt><dd>{health?.stored_flows.toLocaleString() ?? '—'}</dd></div>
      </dl>
      {model?.error && <div className="inline-error">{model.error}</div>}
    </section>

    <section className="panel label-card">
      <p className="eyebrow">Fixed output contract</p>
      <h2>Supported labels</h2>
      <div className="label-grid">
        {model?.labels.map((label, index) => (
          <span key={label}><b>{index}</b>{label}</span>
        ))}
      </div>
      <p className="model-note">
        The service classifies completed bidirectional flows. A BENIGN prediction is a model result,
        not proof that the network or endpoint is secure.
      </p>
    </section>
  </div>
);

export default ModelPanel;
