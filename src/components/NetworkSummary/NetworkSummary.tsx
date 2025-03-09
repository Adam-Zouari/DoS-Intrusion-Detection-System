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

  // Format attack distribution data for pie chart
  const attackData = useMemo(() => {
    return Object.entries(summary.attackCounts).map(([name, value]) => ({
      name,
      value
    }));
  }, [summary.attackCounts]);

  // Add more colors for different attack types
  const ATTACK_COLORS = ['#FF8042', '#FF4560', '#775DD0', '#FEB019', '#00E396', '#008FFB', '#A300F3', '#FD6585'];

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
                label={({ name, percent }) => 
                  percent > 0 ? 
                  `${name}: ${(percent * 100).toFixed(1)}%` : null
                }
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
          <h3>Attack Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={attackData}
                cx="50%"
                cy="50%"
                labelLine={true}
                outerRadius={100}
                dataKey="value"
                nameKey="name"
                label={({ name, percent }) => 
                  percent > 0.02 ? 
                  `${name}: ${(percent * 100).toFixed(1)}%` : null
                }
              >
                {attackData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.name === 'BENIGN' ? '#00C49F' : ATTACK_COLORS[index % ATTACK_COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip formatter={(value) => value.toLocaleString()} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default NetworkSummary;
