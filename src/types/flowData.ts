export interface FlowData {
  id: string;
  timestamp: string;
  sourceIP: string;
  destinationIP: string;
  protocol: string;
  bytesTransferred: number;
  attackType?: string;
  severity?: 'low' | 'medium' | 'high';
  'Flow Bytes/s'?: number;
  'Flow Packets/s'?: number;
  'Label'?: string;
  'Protocol'?: number | string;
  'Timestamp'?: string;
  'Src IP'?: string;
  'Dst IP'?: string;
  'Total Length of Fwd Packet'?: number;
  'Total Fwd Packet'?: number;
  'Total Length of Bwd Packet'?: number;
  'Total Bwd packets'?: number;
  'SYN Flag Count'?: number;
  'ACK Flag Count'?: number;
  'FIN Flag Count'?: number;
  'RST Flag Count'?: number;
  'PSH Flag Count'?: number;
  'URG Flag Count'?: number;
  'CWR Flag Count'?: number;
  'ECE Flag Count'?: number;
  'Active Mean'?: number;
  'Idle Mean'?: number;
}

// Protocol distribution interface
export interface ProtocolDistribution {
  TCP: number;
  UDP: number;
  ICMP: number;
  OTHER: number;
}

// Host statistics interface
export interface HostStats {
  ip: string;
  connectionsInitiated: number;
  connectionsReceived: number;
  dataSent: number;
  dataReceived: number;
  packetsSent: number;
  packetsReceived: number;
  commonDestinations: { ip: string, count: number }[];
  flagCounts: {
    SYN: number;
    ACK: number;
    FIN: number;
    RST: number;
    PSH: number;
    URG: number;
    CWR: number;
    ECE: number;
  };
  activeMean: number;
  idleMean: number;
}

// Attack statistics interface
export interface AttackStats {
  attackType: string;
  count: number;
  relatedIPs: string[];
  severity: 'low' | 'medium' | 'high';
}
