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
  
  // Removed the topActiveHosts useMemo as it's no longer needed
  
  const flagData = useMemo(() => {
    if (!selectedHostData) return [];
    
    return Object.entries(selectedHostData.flagCounts).map(([flag, count]) => ({
      flag,
      count
    }));
  }, [selectedHostData]);

  return (
    <div className="machine-details full-width">
      <h2>Machine (Host) Details</h2>
      
      <div className="hosts-container full-width">
        <div className="hosts-table full-width">
          <h3>All Hosts</h3>
          <div className="table-container limited-height">
            <table className="full-width-table">
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
                  <th onClick={() => toggleSort('packetsSent')}>
                    Packets Sent {sortBy === 'packetsSent' && (sortDirection === 'asc' ? '▲' : '▼')}
                  </th>
                  <th onClick={() => toggleSort('packetsReceived')}>
                    Packets Received {sortBy === 'packetsReceived' && (sortDirection === 'asc' ? '▲' : '▼')}
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
                  <React.Fragment key={host.ip}>
                    <tr 
                      className={selectedHost === host.ip ? 'selected-row' : ''}
                      onClick={() => setSelectedHost(selectedHost === host.ip ? null : host.ip)}
                    >
                      <td>{host.ip}</td>
                      <td>{host.connectionsInitiated.toLocaleString()}</td>
                      <td>{host.connectionsReceived.toLocaleString()}</td>
                      <td>{host.packetsSent.toLocaleString()}</td>
                      <td>{host.packetsReceived.toLocaleString()}</td>
                      <td>{Math.round(host.dataSent).toLocaleString()} bytes</td>
                      <td>{Math.round(host.dataReceived).toLocaleString()} bytes</td>
                      <td>
                        <button 
                          className="view-details-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedHost(selectedHost === host.ip ? null : host.ip);
                          }}
                        >
                          {selectedHost === host.ip ? 'Hide Details' : 'View Details'}
                        </button>
                      </td>
                    </tr>
                    {selectedHost === host.ip && (
                      <tr className="host-details-row">
                        <td colSpan={8}>
                          <div className="expanded-details">
                            <div className="detail-cards">
                              <div className="detail-card">
                                <h4>Connection Stats</h4>
                                <ul>
                                  <li><strong>Total Outbound:</strong> {host.connectionsInitiated.toLocaleString()}</li>
                                  <li><strong>Total Inbound:</strong> {host.connectionsReceived.toLocaleString()}</li>
                                  <li><strong>Data Sent:</strong> {Math.round(host.dataSent).toLocaleString()} bytes</li>
                                  <li><strong>Data Received:</strong> {Math.round(host.dataReceived).toLocaleString()} bytes</li>
                                </ul>
                              </div>
                              
                              <div className="detail-card">
                                <h4>Packet Stats</h4>
                                <ul>
                                  <li><strong>Packets Sent:</strong> {host.packetsSent.toLocaleString()}</li>
                                  <li><strong>Packets Received:</strong> {host.packetsReceived.toLocaleString()}</li>
                                  <li><strong>Active Mean:</strong> {host.activeMean.toLocaleString()} ms</li>
                                  <li><strong>Idle Mean:</strong> {host.idleMean.toLocaleString()} ms</li>
                                </ul>
                              </div>
                            </div>
                            
                            <div className="common-destinations">
                              <h4>Top Destinations</h4>
                              <ul>
                                {host.commonDestinations.map((dest, index) => (
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
                                <BarChart 
                                  data={Object.entries(host.flagCounts).map(([flag, count]) => ({ flag, count }))} 
                                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                >
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
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      {/* Removed the active-hosts-visualization section */}
    </div>
  );
};

export default MachineDetails;
