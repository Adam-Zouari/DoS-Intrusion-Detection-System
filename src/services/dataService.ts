import { FlowData, ProtocolDistribution, HostStats, AttackStats } from '../types/flowData';
import Papa from 'papaparse';

// Re-export the types so they can be imported from this module
export type { FlowData, ProtocolDistribution, HostStats, AttackStats };

// Use the server API endpoint instead of direct file access
const API_BASE_URL = 'http://localhost:5000/api';

// Get current date in yyyy-mm-dd format
const getCurrentDateString = (): string => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

// Map protocol numbers to names
const protocolMap: { [key: number]: string } = {
  1: 'ICMP',
  6: 'TCP', 
  17: 'UDP'
};

export const fetchFlowData = async (date?: string): Promise<FlowData[]> => {
  try {
    const dateToFetch = date || getCurrentDateString();
    const url = `${API_BASE_URL}/flow-data?date=${dateToFetch}`;
    
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`);
    }
    
    const data = await response.json();
    return data as FlowData[];
  } catch (error) {
    console.error('Error fetching flow data:', error);
    return [];
  }
};

export const processNetworkSummary = (data: FlowData[]) => {
  const totalConnections = data.length;
  let totalBytes = 0;
  let totalPackets = 0;
  let attackCounts = {
    BENIGN: 0,
    DDOS: 0,
    DOS: 0,
    'PORT SCAN': 0
  };
  
  const protocolDistribution: ProtocolDistribution = {
    TCP: 0,
    UDP: 0,
    ICMP: 0,
    OTHER: 0
  };
  
  // Time series data for visualizations
  const timeSeriesData: {timestamp: string, bytes: number, packets: number}[] = [];
  
  data.forEach(flow => {
    // Process bytes and packets
    totalBytes += flow['Flow Bytes/s'] || 0;
    totalPackets += flow['Flow Packets/s'] || 0;
    
    // Count attacks
    if (flow['Label']) {
      const label = flow['Label'] as string;
      if (label in attackCounts) {
        attackCounts[label as keyof typeof attackCounts]++;
      }
    }
    
    // Process protocol distribution
    const protocol = typeof flow['Protocol'] === 'number' 
      ? protocolMap[flow['Protocol']] || 'OTHER' 
      : String(flow['Protocol']).toUpperCase();
    
    if (protocol === 'TCP') protocolDistribution.TCP++;
    else if (protocol === 'UDP') protocolDistribution.UDP++;
    else if (protocol === 'ICMP') protocolDistribution.ICMP++;
    else protocolDistribution.OTHER++;
    
    // Add time series data point
    if (flow['Timestamp']) {
      timeSeriesData.push({
        timestamp: flow['Timestamp'],
        bytes: flow['Flow Bytes/s'] || 0,
        packets: flow['Flow Packets/s'] || 0
      });
    }
  });
  
  return {
    totalConnections,
    totalBytes,
    totalPackets,
    attackCounts,
    protocolDistribution,
    timeSeriesData
  };
};

export const processHostDetails = (data: FlowData[]): HostStats[] => {
  const hostMap = new Map<string, HostStats>();

  data.forEach(flow => {
    const srcIP = flow['Src IP'];
    const dstIP = flow['Dst IP'];
    
    if (srcIP) {
      // Process source host
      if (!hostMap.has(srcIP)) {
        hostMap.set(srcIP, createEmptyHostStats(srcIP));
      }
      
      const srcHost = hostMap.get(srcIP)!;
      srcHost.connectionsInitiated++;
      srcHost.dataSent += flow['Total Length of Fwd Packet'] || 0;
      srcHost.packetsSent += flow['Total Fwd Packet'] || 0;
      
      // Track common destinations
      if (dstIP) {
        const dstIndex = srcHost.commonDestinations.findIndex(d => d.ip === dstIP);
        if (dstIndex >= 0) {
          srcHost.commonDestinations[dstIndex].count++;
        } else {
          srcHost.commonDestinations.push({ ip: dstIP, count: 1 });
        }
      }
      
      // Process flags
      processFlags(srcHost, flow);
      
      // Process active/idle times
      srcHost.activeMean = (srcHost.activeMean + (flow['Active Mean'] || 0)) / 2;
      srcHost.idleMean = (srcHost.idleMean + (flow['Idle Mean'] || 0)) / 2;
    }
    
    if (dstIP) {
      // Process destination host
      if (!hostMap.has(dstIP)) {
        hostMap.set(dstIP, createEmptyHostStats(dstIP));
      }
      
      const dstHost = hostMap.get(dstIP)!;
      dstHost.connectionsReceived++;
      dstHost.dataReceived += flow['Total Length of Bwd Packet'] || 0;
      dstHost.packetsReceived += flow['Total Bwd packets'] || 0;
    }
  });
  
  // Sort common destinations and convert Map to Array
  return Array.from(hostMap.values()).map(host => {
    host.commonDestinations.sort((a, b) => b.count - a.count);
    host.commonDestinations = host.commonDestinations.slice(0, 5); // Top 5
    return host;
  });
};

const createEmptyHostStats = (ip: string): HostStats => ({
  ip,
  connectionsInitiated: 0,
  connectionsReceived: 0,
  dataSent: 0,
  dataReceived: 0,
  packetsSent: 0,
  packetsReceived: 0,
  commonDestinations: [],
  flagCounts: {
    SYN: 0,
    ACK: 0,
    FIN: 0,
    RST: 0,
    PSH: 0,
    URG: 0,
    CWR: 0,
    ECE: 0
  },
  activeMean: 0,
  idleMean: 0
});

const processFlags = (host: HostStats, flow: FlowData) => {
  host.flagCounts.SYN += flow['SYN Flag Count'] || 0;
  host.flagCounts.ACK += flow['ACK Flag Count'] || 0;
  host.flagCounts.FIN += flow['FIN Flag Count'] || 0;
  host.flagCounts.RST += flow['RST Flag Count'] || 0;
  host.flagCounts.PSH += flow['PSH Flag Count'] || 0;
  host.flagCounts.URG += flow['URG Flag Count'] || 0;
  host.flagCounts.CWR += flow['CWR Flag Count'] || 0;
  host.flagCounts.ECE += flow['ECE Flag Count'] || 0;
};

export const processAnomalies = (data: FlowData[]): AttackStats[] => {
  const attackMap = new Map<string, AttackStats>();
  
  // Initialize with all attack types
  ['BENIGN', 'DDOS', 'DOS', 'PORT SCAN'].forEach(type => {
    attackMap.set(type, {
      attackType: type as any,
      count: 0,
      relatedIPs: [],
      severity: type === 'BENIGN' ? 'low' : 'high'
    });
  });
  
  data.forEach(flow => {
    const label = flow['Label'] || 'BENIGN';
    const srcIP = flow['Src IP'];
    const dstIP = flow['Dst IP'];
    
    if (attackMap.has(label)) {
      const stats = attackMap.get(label)!;
      stats.count++;
      
      // Add unique IPs
      if (srcIP && !stats.relatedIPs.includes(srcIP)) {
        stats.relatedIPs.push(srcIP);
      }
      if (dstIP && !stats.relatedIPs.includes(dstIP)) {
        stats.relatedIPs.push(dstIP);
      }
      
      // Determine severity based on volume
      if (label !== 'BENIGN') {
        if (stats.count > 100) stats.severity = 'high';
        else if (stats.count > 10) stats.severity = 'medium';
        else stats.severity = 'low';
      }
    }
  });
  
  return Array.from(attackMap.values());
};
