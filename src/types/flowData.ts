export interface FlowData {
  'Flow ID': string;
  'Src IP': string;
  'Src Port': number;
  'Dst IP': string;
  'Dst Port': number;
  'Protocol': number | string;
  'Timestamp': string;
  'Flow Duration': number;
  'Total Fwd Packet': number;
  'Total Bwd packets': number;
  'Total Length of Fwd Packet': number;
  'Total Length of Bwd Packet': number;
  'Fwd Packet Length Max': number;
  'Fwd Packet Length Min': number;
  'Fwd Packet Length Mean': number;
  'Fwd Packet Length Std': number;
  'Bwd Packet Length Max': number;
  'Bwd Packet Length Min': number;
  'Bwd Packet Length Mean': number;
  'Bwd Packet Length Std': number;
  'Flow Bytes/s': number;
  'Flow Packets/s': number;
  'Flow IAT Mean': number;
  'Flow IAT Std': number;
  'Flow IAT Max': number;
  'Flow IAT Min': number;
  'Fwd IAT Total': number;
  'Fwd IAT Mean': number;
  'Fwd IAT Std': number;
  'Fwd IAT Max': number;
  'Fwd IAT Min': number;
  'Bwd IAT Total': number;
  'Bwd IAT Mean': number;
  'Bwd IAT Std': number;
  'Bwd IAT Max': number;
  'Bwd IAT Min': number;
  'Fwd PSH Flags': number;
  'Bwd PSH Flags': number;
  'Fwd URG Flags': number;
  'Bwd URG Flags': number;
  'Fwd Header Length': number;
  'Bwd Header Length': number;
  'Fwd Packets/s': number;
  'Bwd Packets/s': number;
  'Packet Length Min': number;
  'Packet Length Max': number;
  'Packet Length Mean': number;
  'Packet Length Std': number;
  'Packet Length Variance': number;
  'FIN Flag Count': number;
  'SYN Flag Count': number;
  'RST Flag Count': number;
  'PSH Flag Count': number;
  'ACK Flag Count': number;
  'URG Flag Count': number;
  'CWR Flag Count': number;
  'ECE Flag Count': number;
  'Down/Up Ratio': number;
  'Average Packet Size': number;
  'Fwd Segment Size Avg': number;
  'Bwd Segment Size Avg': number;
  'Fwd Bytes/Bulk Avg': number;
  'Fwd Packet/Bulk Avg': number;
  'Fwd Bulk Rate Avg': number;
  'Bwd Bytes/Bulk Avg': number;
  'Bwd Packet/Bulk Avg': number;
  'Bwd Bulk Rate Avg': number;
  'Subflow Fwd Packets': number;
  'Subflow Fwd Bytes': number;
  'Subflow Bwd Packets': number;
  'Subflow Bwd Bytes': number;
  'FWD Init Win Bytes': number;
  'Bwd Init Win Bytes': number;
  'Fwd Act Data Pkts': number;
  'Fwd Seg Size Min': number;
  'Active Mean': number;
  'Active Std': number;
  'Active Max': number;
  'Active Min': number;
  'Idle Mean': number;
  'Idle Std': number;
  'Idle Max': number;
  'Idle Min': number;
  'Label': string;
}

export type AttackType = 'BENIGN' | 'DDOS' | 'DOS' | 'PORT SCAN';

export interface ProtocolDistribution {
  TCP: number;
  UDP: number;
  ICMP: number;
  OTHER: number;
}

export interface HostStats {
  ip: string;
  connectionsInitiated: number;
  connectionsReceived: number;
  dataSent: number;
  dataReceived: number;
  packetsSent: number;
  packetsReceived: number;
  commonDestinations: {ip: string, count: number}[];
  flagCounts: {[flag: string]: number};
  activeMean: number;
  idleMean: number;
}

export interface AttackStats {
  attackType: AttackType;
  count: number;
  relatedIPs: string[];
  severity: 'low' | 'medium' | 'high';
}
