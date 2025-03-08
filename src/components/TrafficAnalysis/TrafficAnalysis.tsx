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
  
  // Top active connections by packets transferred
  const topActiveConnections = useMemo(() => {
    return [...data]
      .sort((a, b) => {
        const packetsA = (a['Flow Packets/s'] || 0);
        const packetsB = (b['Flow Packets/s'] || 0);
        return packetsB - packetsA;
      })
      .slice(0, 10)
      .map(flow => ({
        id: flow['Flow ID'],
        source: `${flow['Src IP']}:${flow['Src Port']}`,
        destination: `${flow['Dst IP']}:${flow['Dst Port']}`,
        protocol: typeof flow['Protocol'] === 'number' 
          ? {0: 'HOPOPT', 1: 'ICMP', 6: 'TCP', 17: 'UDP'}[flow['Protocol']] || 'OTHER' 
          : flow['Protocol'],
        bytesPerSec: flow['Flow Bytes/s'] || 0,
        packetsPerSec: flow['Flow Packets/s'] || 0,
        duration: flow['Flow Duration'] || 0,
        timestamp: flow['Timestamp'] || new Date().toISOString()
      }));
  }, [data, liveUpdateCounter]); // Re-compute when liveUpdateCounter changes
  
  // Traffic trend data
  const trafficTrendData = useMemo(() => {
    const timestamps = [...new Set(data.map(flow => flow['Timestamp']))].sort();
    
    return timestamps.map(timestamp => {
      const flowsAtTimestamp = data.filter(flow => flow['Timestamp'] === timestamp);
      
      const totalBytes = flowsAtTimestamp.reduce((sum, flow) => sum + (flow['Flow Bytes/s'] || 0), 0);
      const totalPackets = flowsAtTimestamp.reduce((sum, flow) => sum + (flow['Flow Packets/s'] || 0), 0);
      
      // Find the flow ID with the highest bytes/s at this timestamp
      const topFlow = flowsAtTimestamp.length > 0 
        ? flowsAtTimestamp.reduce((prev, current) => 
            (prev['Flow Bytes/s'] || 0) > (current['Flow Bytes/s'] || 0) ? prev : current)
        : null;
      
      const topFlowId = topFlow ? topFlow['Flow ID'] : 'N/A';
      
      return {
        timestamp,
        bytes: totalBytes,
        packets: totalPackets,
        topFlowId,
      };
    });
  }, [data]);
  
  // Detect traffic spikes
  const trafficSpikes = useMemo(() => {
    if (trafficTrendData.length < 2) return [];
    
    // Calculate mean packets per second
    const meanPackets = trafficTrendData.reduce((sum, point) => sum + point.packets, 0) / trafficTrendData.length;
    
    // Standard deviation
    const stdDevPackets = Math.sqrt(
      trafficTrendData.reduce((sum, point) => sum + Math.pow(point.packets - meanPackets, 2), 0) / trafficTrendData.length
    );
    
    // Find points that are more than 2 standard deviations above mean
    return trafficTrendData
      .filter(point => point.packets > meanPackets + 2 * stdDevPackets)
      .map(point => ({
        timestamp: point.timestamp || new Date().toISOString(),
        packets: point.packets,
        percentAboveMean: Math.round(((point.packets - meanPackets) / meanPackets) * 100)
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
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const flowId = payload[0]?.payload?.topFlowId || 'N/A';
                  return (
                    <div className="custom-tooltip" style={{ 
                      backgroundColor: 'white', 
                      padding: '10px', 
                      border: '1px solid #ccc',
                      borderRadius: '4px'
                    }}>
                      <p className="tooltip-time" style={{ margin: '5px 0' }}>{formatTimestamp(label)}</p>
                      <p className="tooltip-flow" style={{ margin: '5px 0' }}>Flow ID: {flowId}</p>
                      {payload.map((entry, index) => (
                        <p key={index} style={{ color: entry.color, margin: '5px 0' }}>
                          {entry.name === 'bytes' ? 'Bytes/s' : 'Packets/s'}: {Number(entry.value).toLocaleString()}
                        </p>
                      ))}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend />
            <Area type="monotone" dataKey="bytes" name="bytes" stroke="#8884d8" fill="#8884d8" fillOpacity={0.3} />
            <Area type="monotone" dataKey="packets" name="packets" stroke="#82ca9d" fill="#82ca9d" fillOpacity={0.3} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      
      <div className="traffic-panels">
        <div className="traffic-panel">
          <h3>Top Active Flows</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Destination</th>
                  <th>Protocol</th>
                  <th>Packets/s</th>
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
                    <td>{Math.round(conn.packetsPerSec).toLocaleString()}</td>
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
                    <th>Packets/s</th>
                    <th>% Above Avg</th>
                  </tr>
                </thead>
                <tbody>
                  {trafficSpikes.map((spike, index) => (
                    <tr key={index} className="spike-row">
                      <td>{formatTimestamp(spike.timestamp)}</td>
                      <td>{Math.round(spike.packets).toLocaleString()}</td>
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
                bytes: flow['Flow Bytes/s'],
                packets: flow['Flow Packets/s'],
                flowId: flow['Flow ID'] // Add Flow ID to the data points
              }))}
            margin={{ top: 5, right: 40, left: 40, bottom: 5 }} // Increased left and right margins
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="index" label={{ value: 'Flow Index', position: 'insideBottomRight', offset: -10 }} />
            <YAxis 
              yAxisId="left" 
              label={{ 
                value: 'Duration (ms)', 
                angle: -90, 
                position: 'insideLeft',
                style: { textAnchor: 'middle' },
                dx: -35  // Use dx instead of offset for horizontal positioning
              }} 
            />
            <YAxis 
              yAxisId="right" 
              orientation="right" 
              label={{ 
                value: 'Bytes/s', 
                angle: 90, 
                position: 'insideRight',
                style: { textAnchor: 'middle' },
                dx: 35  // Use dx instead of offset for horizontal positioning
              }} 
            />
            <Tooltip 
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const flowId = payload[0]?.payload?.flowId || 'N/A';
                  return (
                    <div className="custom-tooltip" style={{ 
                      backgroundColor: 'white', 
                      padding: '10px', 
                      border: '1px solid #ccc',
                      borderRadius: '4px'
                    }}>
                      <p className="tooltip-flow" style={{ margin: '5px 0' }}>Flow ID: {flowId}</p>
                      {payload.map((entry, index) => (
                        <p key={index} style={{ color: entry.color, margin: '5px 0' }}>
                          {entry.name}: {Number(entry.value).toLocaleString()}
                        </p>
                      ))}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="duration" name="Duration (ms)" stroke="#8884d8" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="bytes" name="Bytes/s" stroke="#82ca9d" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="packets" name="Packets/s" stroke="#ff8042" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrafficAnalysis;
