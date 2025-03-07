import React, { useMemo, useState, useEffect } from 'react';
import { FlowData } from '../../types/flowData';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts';
import './TrafficAnalysis.css';

interface TrafficAnalysisProps {
  data: FlowData[];
}

// Format timestamps consistently across the component
const formatTimestamp = (timestamp: string) => {
  try {
    return new Date(timestamp).toLocaleTimeString();
  } catch (e) {
    return timestamp;
  }
};

const TrafficAnalysis: React.FC<TrafficAnalysisProps> = ({ data }) => {
  const [liveUpdateCounter, setLiveUpdateCounter] = useState(0);
  
  // Simulate live updates
  useEffect(() => {
    const timer = setInterval(() => {
      setLiveUpdateCounter(prev => prev + 1);
    }, 5000); // Update every 5 seconds
    
    return () => clearInterval(timer);
  }, []);
  
  // Top active connections by bytes transferred
  const topActiveConnections = useMemo(() => {
    return [...data]
      .sort((a, b) => {
        const bytesA = (a['Flow Bytes/s'] || 0);
        const bytesB = (b['Flow Bytes/s'] || 0);
        return bytesB - bytesA;
      })
      .slice(0, 10)
      .map(flow => ({
        id: flow['Flow ID'],
        source: `${flow['Src IP']}:${flow['Src Port']}`,
        destination: `${flow['Dst IP']}:${flow['Dst Port']}`,
        protocol: typeof flow['Protocol'] === 'number' 
          ? {1: 'ICMP', 6: 'TCP', 17: 'UDP'}[flow['Protocol']] || 'OTHER' 
          : flow['Protocol'],
        bytesPerSec: flow['Flow Bytes/s'],
        packetsPerSec: flow['Flow Packets/s'],
        duration: flow['Flow Duration'],
        timestamp: flow['Timestamp']
      }));
  }, [data, liveUpdateCounter]); // Re-compute when liveUpdateCounter changes
  
  // Traffic trend data
  const trafficTrendData = useMemo(() => {
    const timestamps = [...new Set(data.map(flow => flow['Timestamp']))].sort();
    
    return timestamps.map(timestamp => {
      const flowsAtTimestamp = data.filter(flow => flow['Timestamp'] === timestamp);
      
      const totalBytes = flowsAtTimestamp.reduce((sum, flow) => sum + (flow['Flow Bytes/s'] || 0), 0);
      const totalPackets = flowsAtTimestamp.reduce((sum, flow) => sum + (flow['Flow Packets/s'] || 0), 0);
      
      return {
        timestamp,
        bytes: totalBytes,
        packets: totalPackets,
      };
    });
  }, [data]);
  
  // Detect traffic spikes
  const trafficSpikes = useMemo(() => {
    if (trafficTrendData.length < 2) return [];
    
    // Calculate mean bytes per second
    const meanBytes = trafficTrendData.reduce((sum, point) => sum + point.bytes, 0) / trafficTrendData.length;
    
    // Standard deviation
    const stdDevBytes = Math.sqrt(
      trafficTrendData.reduce((sum, point) => sum + Math.pow(point.bytes - meanBytes, 2), 0) / trafficTrendData.length
    );
    
    // Find points that are more than 2 standard deviations above mean
    return trafficTrendData
      .filter(point => point.bytes > meanBytes + 2 * stdDevBytes)
      .map(point => ({
        timestamp: point.timestamp,
        bytes: point.bytes,
        percentAboveMean: Math.round(((point.bytes - meanBytes) / meanBytes) * 100)
      }));
  }, [trafficTrendData]);
  
  return (
    <div className="traffic-analysis">
      <h2>Real-Time Traffic Analysis</h2>
      <p className="update-status">Auto-updating every 5 seconds. Last update: {new Date().toLocaleTimeString()}</p>
      
      <div className="traffic-overview">
        <h3>Traffic Trend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={trafficTrendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="timestamp" 
              tickFormatter={formatTimestamp} 
              tick={{ fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis />
            <Tooltip 
              labelFormatter={formatTimestamp}
              formatter={(value) => [`${Number(value).toLocaleString()}`, undefined]}
            />
            <Legend />
            <Area type="monotone" dataKey="bytes" name="Bytes/s" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
            <Area type="monotone" dataKey="packets" name="Packets/s" stroke="#82ca9d" fill="#82ca9d" fillOpacity={0.3} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      
      <div className="traffic-panels">
        <div className="traffic-panel">
          <h3>Top Active Connections</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Protocol</th>
                  <th>Bytes/s</th>
                  <th>Duration</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {topActiveConnections.map((conn, index) => (
                  <tr key={index}>
                    <td>{conn.source}</td>
                    <td>{conn.destination}</td>
                    <td>{conn.protocol}</td>
                    <td>{Math.round(conn.bytesPerSec).toLocaleString()}</td>
                    <td>{Math.round(conn.duration).toLocaleString()} ms</td>
                    <td>{formatTimestamp(conn.timestamp)}</td>
                  </tr>
                ))}
                {topActiveConnections.length === 0 && (
                  <tr>
                    <td colSpan={6} className="no-data">No active connections available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        
        <div className="traffic-panel">
          <h3>Traffic Spikes {trafficSpikes.length > 0 ? `(${trafficSpikes.length} Detected)` : ''}</h3>
          {trafficSpikes.length > 0 ? (
            <div className="spikes-list">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Bytes/s</th>
                    <th>% Above Avg</th>
                  </tr>
                </thead>
                <tbody>
                  {trafficSpikes.map((spike, index) => (
                    <tr key={index} className="spike-row">
                      <td>{formatTimestamp(spike.timestamp)}</td>
                      <td>{Math.round(spike.bytes).toLocaleString()}</td>
                      <td>+{spike.percentAboveMean}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="no-spikes">
              <p>No unusual traffic spikes detected</p>
            </div>
          )}
        </div>
      </div>
      
      <div className="flow-duration-analysis">
        <h3>Flow Duration Distribution</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart
            data={[...data]
              .sort((a, b) => a['Flow Duration'] - b['Flow Duration'])
              .slice(0, 100) // Take a sample for better visualization
              .map((flow, index) => ({
                index,
                duration: flow['Flow Duration'],
                bytes: flow['Flow Bytes/s']
              }))}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="index" label={{ value: 'Flow Index', position: 'insideBottomRight', offset: -10 }} />
            <YAxis yAxisId="left" label={{ value: 'Duration (ms)', angle: -90, position: 'insideLeft' }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: 'Bytes/s', angle: 90, position: 'insideRight' }} />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="duration" name="Duration (ms)" stroke="#8884d8" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="bytes" name="Bytes/s" stroke="#82ca9d" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrafficAnalysis;
