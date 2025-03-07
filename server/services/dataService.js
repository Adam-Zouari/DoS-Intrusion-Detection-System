const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');
const moment = require('moment');
const config = require('../config');

let cachedData = null;
let lastReadTime = null;
let isReading = false;

const initializeDataService = async () => {
  try {
    await loadCurrentDayData();
    console.log('Data service initialized');
  } catch (error) {
    console.error('Error initializing data service:', error);
  }
};

const getCurrentDayFilePath = () => {
  const today = moment().format('YYYY-MM-DD');
  const fileName = `${today}_Flow.csv`;
  return path.join(config.DATA_DIRECTORY, fileName);
};

const loadCurrentDayData = async () => {
  if (isReading) return;
  isReading = true;
  
  try {
    const filePath = getCurrentDayFilePath();
    
    // Check if file exists
    if (!fs.existsSync(filePath)) {
      console.error(`File does not exist: ${filePath}`);
      isReading = false;
      return;
    }
    
    const results = [];
    
    await new Promise((resolve, reject) => {
      fs.createReadStream(filePath)
        .pipe(csv())
        .on('data', (data) => results.push(data))
        .on('end', () => {
          cachedData = results;
          lastReadTime = new Date();
          console.log(`Read ${results.length} records from ${filePath}`);
          resolve();
        })
        .on('error', (error) => {
          reject(error);
        });
    });
  } catch (error) {
    console.error('Error reading CSV file:', error);
  } finally {
    isReading = false;
  }
};

// Get data for initial load
const getInitialData = async () => {
  if (!cachedData) {
    await loadCurrentDayData();
  }
  return processData(cachedData);
};

// Check if we need to reload data
const getLatestData = async () => {
  const now = new Date();
  // Reload if data is more than 30 seconds old
  if (!lastReadTime || (now - lastReadTime > 300)) {
    await loadCurrentDayData();
  }
  return processData(cachedData);
};

// Process raw data for the dashboard
const processData = (data) => {
  if (!data || data.length === 0) {
    return {
      networkSummary: createEmptyNetworkSummary(),
      machineDetails: [],
      trafficAnalysis: createEmptyTrafficAnalysis(),
      anomalyDetection: createEmptyAnomalyDetection(),
      connectionLogs: []
    };
  }

  const networkSummary = processNetworkSummary(data);
  const machineDetails = processMachineDetails(data);
  const trafficAnalysis = processTrafficAnalysis(data);
  const anomalyDetection = processAnomalyDetection(data);
  
  // Get the most recent 1000 connections for logs
  const connectionLogs = data
    .sort((a, b) => new Date(b.Timestamp) - new Date(a.Timestamp))
    .slice(0, 1000);

  return {
    networkSummary,
    machineDetails,
    trafficAnalysis,
    anomalyDetection,
    connectionLogs
  };
};

const processNetworkSummary = (data) => {
  const activeConnections = new Set();
  let totalBytes = 0;
  let totalPackets = 0;
  let attacks = 0;
  const protocols = {};

  data.forEach(row => {
    const connectionKey = `${row['Src IP']}:${row['Src Port']}-${row['Dst IP']}:${row['Dst Port']}`;
    activeConnections.add(connectionKey);
    
    totalBytes += parseFloat(row['Flow Bytes/s'] || 0);
    totalPackets += parseFloat(row['Flow Packets/s'] || 0);
    
    if (row['Label'] !== 'BENIGN') {
      attacks++;
    }
    
    const protocol = row['Protocol'];
    protocols[protocol] = (protocols[protocol] || 0) + 1;
  });

  return {
    totalConnections: activeConnections.size,
    totalBytes,
    totalPackets,
    attackCount: attacks,
    protocols
  };
};

const processMachineDetails = (data) => {
  const machines = {};
  
  data.forEach(row => {
    const srcIp = row['Src IP'];
    const dstIp = row['Dst IP'];
    
    // Process source machine
    if (!machines[srcIp]) {
      machines[srcIp] = createMachineEntry(srcIp);
    }
    
    machines[srcIp].sentBytes += parseFloat(row['Total Length of Fwd Packet'] || 0);
    machines[srcIp].sentPackets += parseFloat(row['Total Fwd Packet'] || 0);
    machines[srcIp].outboundConnections++;
    
    // Process destination machine
    if (!machines[dstIp]) {
      machines[dstIp] = createMachineEntry(dstIp);
    }
    
    machines[dstIp].receivedBytes += parseFloat(row['Total Length of Bwd Packet'] || 0);
    machines[dstIp].receivedPackets += parseFloat(row['Total Bwd packets'] || 0);
    machines[dstIp].inboundConnections++;
    
    // Count flag occurrences
    countFlags(machines[srcIp], row, true);
    countFlags(machines[dstIp], row, false);
  });
  
  return Object.values(machines);
};

const createMachineEntry = (ip) => {
  return {
    ip,
    sentBytes: 0,
    receivedBytes: 0,
    sentPackets: 0,
    receivedPackets: 0,
    outboundConnections: 0,
    inboundConnections: 0,
    activeMean: 0,
    idleMean: 0,
    flags: {
      syn: 0,
      fin: 0,
      rst: 0,
      psh: 0,
      ack: 0,
      urg: 0
    }
  };
};

const countFlags = (machine, row, isSrc) => {
  machine.flags.syn += parseInt(row['SYN Flag Count'] || 0);
  machine.flags.fin += parseInt(row['FIN Flag Count'] || 0);
  machine.flags.rst += parseInt(row['RST Flag Count'] || 0);
  machine.flags.psh += parseInt(row['PSH Flag Count'] || 0);
  machine.flags.ack += parseInt(row['ACK Flag Count'] || 0);
  machine.flags.urg += parseInt(row['URG Flag Count'] || 0);
  
  machine.activeMean = parseFloat(row['Active Mean'] || 0);
  machine.idleMean = parseFloat(row['Idle Mean'] || 0);
};

const processTrafficAnalysis = (data) => {
  // Sort data by timestamp to get most recent entries
  const sortedData = [...data].sort((a, b) => new Date(b.Timestamp) - new Date(a.Timestamp));
  const recentConnections = sortedData.slice(0, 100);
  
  const topConnections = [...data]
    .sort((a, b) => {
      const bytesA = parseFloat(a['Flow Bytes/s'] || 0);
      const bytesB = parseFloat(b['Flow Bytes/s'] || 0);
      return bytesB - bytesA;
    })
    .slice(0, 10);
  
  return {
    recentConnections,
    topConnections,
    currentPacketRate: calculateCurrentPacketRate(recentConnections),
    currentByteRate: calculateCurrentByteRate(recentConnections)
  };
};

const calculateCurrentPacketRate = (connections) => {
  if (connections.length === 0) return 0;
  return connections.reduce((sum, conn) => sum + parseFloat(conn['Flow Packets/s'] || 0), 0) / connections.length;
};

const calculateCurrentByteRate = (connections) => {
  if (connections.length === 0) return 0;
  return connections.reduce((sum, conn) => sum + parseFloat(conn['Flow Bytes/s'] || 0), 0) / connections.length;
};

const processAnomalyDetection = (data) => {
  const attacks = data.filter(row => row['Label'] !== 'BENIGN');
  
  const attacksByType = {};
  config.ATTACK_TYPES.forEach(type => {
    attacksByType[type] = data.filter(row => row['Label'] === type).length;
  });
  
  const suspiciousIPs = new Map();
  attacks.forEach(attack => {
    const srcIp = attack['Src IP'];
    if (!suspiciousIPs.has(srcIp)) {
      suspiciousIPs.set(srcIp, 0);
    }
    suspiciousIPs.set(srcIp, suspiciousIPs.get(srcIp) + 1);
  });
  
  // Find potential scanning/DDoS based on SYN/RST flags
  const potentialScans = data.filter(row => {
    return parseInt(row['SYN Flag Count'] || 0) > 5 || 
           parseInt(row['RST Flag Count'] || 0) > 5;
  });
  
  return {
    attacks: attacks.slice(0, 100),
    attacksByType,
    suspiciousIPs: [...suspiciousIPs].map(([ip, count]) => ({ ip, count })),
    potentialScans: potentialScans.slice(0, 50)
  };
};

const createEmptyNetworkSummary = () => {
  return {
    totalConnections: 0,
    totalBytes: 0,
    totalPackets: 0,
    attackCount: 0,
    protocols: {}
  };
};

const createEmptyTrafficAnalysis = () => {
  return {
    recentConnections: [],
    topConnections: [],
    currentPacketRate: 0,
    currentByteRate: 0
  };
};

const createEmptyAnomalyDetection = () => {
  return {
    attacks: [],
    attacksByType: {},
    suspiciousIPs: [],
    potentialScans: []
  };
};

const getFlowData = async (date) => {
  // Check if we have cached this data
  if (cachedData[date]) {
    return cachedData[date];
  }
  
  return new Promise((resolve, reject) => {
    const filePath = path.join(config.DATA_DIRECTORY, `${date}_Flow.csv`);
    const results = [];
    
    // Check if file exists
    if (!fs.existsSync(filePath)) {
      console.log(`File not found: ${filePath}`);
      resolve([]);
      return;
    }
    
    fs.createReadStream(filePath)
      .pipe(csv())
      .on('data', (data) => results.push(data))
      .on('end', () => {
        // Process data to ensure numeric values
        const processedData = results.map(item => {
          const processed = {};
          for (const key in item) {
            const value = item[key];
            processed[key] = !isNaN(value) && value !== '' ? Number(value) : value;
          }
          return processed;
        });
        
        // Cache the results
        cachedData[date] = processedData;
        resolve(processedData);
      })
      .on('error', (error) => {
        console.error(`Error reading CSV: ${error.message}`);
        reject(error);
      });
  });
};

module.exports = {
  initializeDataService,
  getInitialData,
  getLatestData,
  getFlowData
};
