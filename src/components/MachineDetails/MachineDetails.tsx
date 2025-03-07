import React, { useState, useMemo } from 'react';
import { FlowData, HostStats } from '../../types/flowData';
import { processHostDetails } from '../../services/dataService';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './MachineDetails.css';

interface MachineDetailsProps {
  data: FlowData[];
}

const MachineDetails: React.FC<MachineDetailsProps> = ({ data }) => {
  const hosts = useMemo(() => processHostDetails(data), [data]);
  const [selectedHost, setSelectedHost] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<keyof HostStats>('connectionsInitiated');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const toggleSort = (field: keyof HostStats) => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDirection('desc');
    }
  };

  const sortedHosts = useMemo(() => {
    return [...hosts].sort((a, b) => {
      if (sortDirection === 'asc') {
        return a[sortBy] > b[sortBy] ? 1 : -1;
      } else {
        return a[sortBy] < b[sortBy] ? 1 : -1;
      }
    });
  }, [hosts, sortBy, sortDirection]);

  const selectedHostData = useMemo(() => {
    return hosts.find(host => host.ip === selectedHost) || null;
  }, [hosts, selectedHost]);
  
  // For visualization
  const topActiveHosts = useMemo(() => {
    return [...hosts]
      .sort((a, b) => (b.connectionsInitiated + b.connectionsReceived) - 
                      (a.connectionsInitiated + a.connectionsReceived))
      .slice(0, 10)
      .map(host => ({
        ip: host.ip,
        active: host.activeMean,
        idle: host.idleMean,
        totalConnections: host.connectionsInitiated + host.connectionsReceived
      }));
  }, [hosts]);

  const flagData = useMemo(() => {
    if (!selectedHostData) return [];
    
    return Object.entries(selectedHostData.flagCounts).map(([flag, count]) => ({
      flag,
      count
    }));
  }, [selectedHostData]);

  return (
    <div className="machine-details">
      <h2>Machine (Host) Details</h2>
      
      <div className="hosts-container">
        <div className="hosts-table">
          <h3>All Hosts</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th onClick={() => toggleSort('ip')}>
                    IP Address {sortBy === 'ip' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => toggleSort('connectionsInitiated')}>
                    Outbound {sortBy === 'connectionsInitiated' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => toggleSort('connectionsReceived')}>
                    Inbound {sortBy === 'connectionsReceived' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => toggleSort('dataSent')}>
                    Data Sent {sortBy === 'dataSent' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => toggleSort('dataReceived')}>
                    Data Received {sortBy === 'dataReceived' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedHosts.map(host => (
                  <tr 
                    key={host.ip} 
                    className={selectedHost === host.ip ? 'selected-row' : ''}
                    onClick={() => setSelectedHost(host.ip)}
                  >
                    <td>{host.ip}</td>
                    <td>{host.connectionsInitiated.toLocaleString()}</td>
                    <td>{host.connectionsReceived.toLocaleString()}</td>
                    <td>{Math.round(host.dataSent).toLocaleString()} bytes</td>
                    <td>{Math.round(host.dataReceived).toLocaleString()} bytes</td>
                    <td>
                      <button 
                        className="view-details-btn"
                        onClick={() => setSelectedHost(host.ip)}
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        
        {selectedHostData && (
          <div className="host-details">
            <h3>Details for {selectedHostData.ip}</h3>
            
            <div className="detail-cards">
              <div className="detail-card">
                <h4>Connection Stats</h4>
                <ul>
                  <li><strong>Total Outbound:</strong> {selectedHostData.connectionsInitiated.toLocaleString()}</li>
                  <li><strong>Total Inbound:</strong> {selectedHostData.connectionsReceived.toLocaleString()}</li>
                  <li><strong>Data Sent:</strong> {Math.round(selectedHostData.dataSent).toLocaleString()} bytes</li>
                  <li><strong>Data Received:</strong> {Math.round(selectedHostData.dataReceived).toLocaleString()} bytes</li>
                </ul>
              </div>
              
              <div className="detail-card">
                <h4>Packet Stats</h4>
                <ul>
                  <li><strong>Packets Sent:</strong> {selectedHostData.packetsSent.toLocaleString()}</li>
                  <li><strong>Packets Received:</strong> {selectedHostData.packetsReceived.toLocaleString()}</li>
                  <li><strong>Active Mean:</strong> {selectedHostData.activeMean.toLocaleString()} ms</li>
                  <li><strong>Idle Mean:</strong> {selectedHostData.idleMean.toLocaleString()} ms</li>
                </ul>
              </div>
            </div>
            
            <div className="common-destinations">
              <h4>Top Destinations</h4>
              <ul>
                {selectedHostData.commonDestinations.map((dest, index) => (
                  <li key={index}>
                    <span className="destination-ip">{dest.ip}</span>
                    <span className="destination-count">{dest.count} connections</span>
                  </li>
                ))}
              </ul>
            </div>
            
            <div className="flag-chart">
              <h4>TCP Flag Distribution</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={flagData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="flag" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" name="Count" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
      
      <div className="active-hosts-visualization">
        <h3>Host Activity Comparison</h3>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart
            data={topActiveHosts}
            layout="vertical"
            margin={{ top: 20, right: 30, left: 60, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" />
            <YAxis dataKey="ip" type="category" />
            <Tooltip />
            <Legend />
            <Bar dataKey="active" name="Active Time (ms)" fill="#82ca9d" />
            <Bar dataKey="idle" name="Idle Time (ms)" fill="#8884d8" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default MachineDetails;
