import React, { useMemo } from 'react';
import { FlowData } from '../../types/flowData';
import { processNetworkSummary } from '../../services/dataService';
import { PieChart, Pie, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import './NetworkSummary.css';

interface NetworkSummaryProps {
  data: FlowData[];
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

const NetworkSummary: React.FC<NetworkSummaryProps> = ({ data }) => {
  const summary = useMemo(() => processNetworkSummary(data), [data]);
  
  const protocolData = useMemo(() => {
    return Object.entries(summary.protocolDistribution).map(([name, value]) => ({
      name,
      value
    }));
  }, [summary.protocolDistribution]);

  // Format time series data for chart
  const timeData = useMemo(() => {
    return summary.timeSeriesData
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .slice(-100); // Show last 100 data points to avoid overcrowding
  }, [summary.timeSeriesData]);

  const attackCount = useMemo(() => {
    return Object.entries(summary.attackCounts)
      .filter(([type]) => type !== 'BENIGN')
      .reduce((total, [_, count]) => total + count, 0);
  }, [summary.attackCounts]);

  return (
    <div className="network-summary">
      <h2>Overall Network Summary</h2>
      
      <div className="stat-cards">
        <div className="stat-card">
          <h3>Active Connections</h3>
          <p className="stat-value">{summary.totalConnections.toLocaleString()}</p>
        </div>
        
        <div className="stat-card">
          <h3>Total Bytes Transferred</h3>
          <p className="stat-value">{Math.round(summary.totalBytes).toLocaleString()} bytes</p>
        </div>
        
        <div className="stat-card">
          <h3>Total Packets</h3>
          <p className="stat-value">{Math.round(summary.totalPackets).toLocaleString()}</p>
        </div>
        
        <div className="stat-card">
          <h3>Detected Attacks</h3>
          <p className="stat-value">{attackCount.toLocaleString()}</p>
        </div>
      </div>
      
      <div className="chart-container">
        <div className="chart-wrapper">
          <h3>Protocol Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={protocolData}
                cx="50%"
                cy="50%"
                labelLine={true}
                outerRadius={100}
                dataKey="value"
                nameKey="name"
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
              >
                {protocolData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => value.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-wrapper">
          <h3>Traffic Over Time</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart
              data={timeData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="timestamp" 
                tick={false}
                label={{ value: 'Time', position: 'insideBottomRight', offset: -10 }} 
              />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <Tooltip labelFormatter={(label) => new Date(label).toLocaleTimeString()} />
              <Legend />
              <Line 
                yAxisId="left"
                type="monotone" 
                dataKey="bytes" 
                name="Bytes/s"
                stroke="#8884d8" 
                activeDot={{ r: 8 }} 
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="packets" 
                name="Packets/s"
                stroke="#82ca9d" 
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      <div className="attack-summary">
        <h3>Attack Distribution</h3>
        <table className="attack-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Count</th>
              <th>Percentage</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(summary.attackCounts).map(([type, count]) => (
              <tr 
                key={type} 
                className={type !== 'BENIGN' ? 'attack-row' : ''}
              >
                <td>{type}</td>
                <td>{count.toLocaleString()}</td>
                <td>
                  {summary.totalConnections > 0 
                    ? `${((count / summary.totalConnections) * 100).toFixed(2)}%` 
                    : '0%'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default NetworkSummary;
