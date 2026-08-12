export interface Health {
  status: 'ready' | 'degraded';
  model_ready: boolean;
  database_ready: boolean;
  stored_flows: number;
  source: string;
  model_error: string | null;
}

export interface ModelInformation {
  ready: boolean;
  error: string | null;
  family: string;
  task: string;
  source_feature_count: number;
  source_features: string[];
  transformed_feature_count: number;
  boosting_iterations: number;
  labels: string[];
  inference_device: string;
  source: string;
}

export interface LabelCount {
  label: string;
  count: number;
}

export interface ProtocolCount {
  protocol: number;
  name: string;
  count: number;
}

export interface TimelinePoint {
  bucket: string;
  flows: number;
  attacks: number;
  bytes: number;
  packets: number;
}

export interface Summary {
  window_minutes: number;
  flow_count: number;
  attack_count: number;
  attack_percentage: number;
  total_bytes: number;
  total_packets: number;
  average_inference_latency_ms: number;
  last_flow_at: string | null;
  labels: LabelCount[];
  protocols: ProtocolCount[];
  timeline: TimelinePoint[];
}

export interface FlowRecord {
  id: number;
  flow_id: string;
  source_ip: string;
  source_port: number;
  destination_ip: string;
  destination_port: number;
  protocol: number;
  protocol_name: string;
  flow_timestamp: string;
  received_at: string;
  predicted_at: string;
  prediction: string;
  inference_latency_ms: number;
  duration_us: number;
  duration_ms: number;
  total_packets: number;
  total_bytes: number;
}

export interface FlowPage {
  items: FlowRecord[];
  total: number;
  page: number;
  page_size: number;
}
