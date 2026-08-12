import type { FlowPage, FlowRecord, Health, ModelInformation, Summary } from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Preserve the HTTP status when the response is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const fetchHealth = () => fetchJson<Health>('/health');

export const fetchModelInformation = () => fetchJson<ModelInformation>('/model');

export const fetchSummary = (windowMinutes: number) =>
  fetchJson<Summary>(`/summary?window_minutes=${windowMinutes}`);

export interface FlowFilters {
  page: number;
  pageSize: number;
  trafficScope: 'all' | 'attacks' | 'benign';
  label?: string;
  sourceIp?: string;
  sourcePort?: string;
  destinationIp?: string;
  destinationPort?: string;
  protocol?: string;
  receivedFrom?: string;
  receivedTo?: string;
  minPackets?: string;
  maxPackets?: string;
  minBytes?: string;
  maxBytes?: string;
  minDurationMs?: string;
  maxDurationMs?: string;
  minLatencyMs?: string;
  maxLatencyMs?: string;
  sortBy: string;
  sortDirection: 'asc' | 'desc';
}

const setIfPresent = (parameters: URLSearchParams, name: string, value?: string) => {
  if (value) parameters.set(name, value);
};

export const fetchFlows = (filters: FlowFilters) => {
  const parameters = new URLSearchParams({
    page: String(filters.page),
    page_size: String(filters.pageSize),
    traffic_scope: filters.trafficScope,
    sort_by: filters.sortBy,
    sort_direction: filters.sortDirection,
  });
  setIfPresent(parameters, 'label', filters.label);
  setIfPresent(parameters, 'source_ip', filters.sourceIp);
  setIfPresent(parameters, 'source_port', filters.sourcePort);
  setIfPresent(parameters, 'destination_ip', filters.destinationIp);
  setIfPresent(parameters, 'destination_port', filters.destinationPort);
  setIfPresent(parameters, 'protocol', filters.protocol);
  if (filters.receivedFrom) parameters.set('received_from', new Date(filters.receivedFrom).toISOString());
  if (filters.receivedTo) parameters.set('received_to', new Date(filters.receivedTo).toISOString());
  setIfPresent(parameters, 'min_packets', filters.minPackets);
  setIfPresent(parameters, 'max_packets', filters.maxPackets);
  setIfPresent(parameters, 'min_bytes', filters.minBytes);
  setIfPresent(parameters, 'max_bytes', filters.maxBytes);
  setIfPresent(parameters, 'min_duration_ms', filters.minDurationMs);
  setIfPresent(parameters, 'max_duration_ms', filters.maxDurationMs);
  setIfPresent(parameters, 'min_latency_ms', filters.minLatencyMs);
  setIfPresent(parameters, 'max_latency_ms', filters.maxLatencyMs);
  return fetchJson<FlowPage>(`/flows?${parameters.toString()}`);
};

export const subscribeToEvents = (
  onFlow: (flow: FlowRecord) => void,
  onConnectionChange: (connected: boolean) => void,
) => {
  const source = new EventSource(`${API_BASE_URL}/events`);
  source.onopen = () => onConnectionChange(true);
  source.onmessage = (event) => onFlow(JSON.parse(event.data) as FlowRecord);
  source.onerror = () => onConnectionChange(false);
  return () => {
    source.close();
    onConnectionChange(false);
  };
};
