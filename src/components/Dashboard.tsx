import React, { useState, useEffect } from 'react';
import { fetchFlowData } from '../services/dataService';
import { FlowData } from '../types/flowData';
import { format } from 'date-fns';

const Dashboard: React.FC = () => {
  const [flowData, setFlowData] = useState<FlowData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(format(new Date(), 'yyyy-MM-dd'));

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchFlowData(selectedDate);
        setFlowData(data);
      } catch (err) {
        setError('Failed to load data. Please ensure the backend server is running.');
        console.error('Error loading data:', err);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [selectedDate]);

  return (
    <div className="dashboard-container">
      <h1>Network Flow Analysis Dashboard</h1>
      
      <div className="date-selector">
        <label htmlFor="date-input">Select Date: </label>
        <input 
          id="date-input"
          type="date" 
          value={selectedDate} 
          onChange={(e) => setSelectedDate(e.target.value)}
        />
      </div>
      
      {loading && <div className="loading-indicator">Loading data...</div>}
      
      {error && (
        <div className="error-message">
          <p>{error}</p>
          <p>Make sure the backend server is running at: http://localhost:3001</p>
        </div>
      )}
      
      {!loading && !error && flowData.length === 0 && (
        <div className="no-data-message">No data available for the selected date.</div>
      )}
      
      {!loading && !error && flowData.length > 0 && (
        <div className="data-display">
          <h2>Network Flows</h2>
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Source IP</th>
                <th>Destination IP</th>
                <th>Protocol</th>
                <th>Bytes</th>
                <th>Attack Type</th>
                <th>Severity</th>
              </tr>
            </thead>
            <tbody>
              {flowData.map(flow => (
                <tr key={flow['Flow ID']} className={flow.attackType ? `severity-${flow.severity}` : ''}>
                  <td>{new Date(flow.timestamp).toLocaleTimeString()}</td>
                  <td>{flow.sourceIP}</td>
                  <td>{flow.destinationIP}</td>
                  <td>{flow.protocol}</td>
                  <td>{flow.bytesTransferred}</td>
                  <td>{flow.attackType || 'N/A'}</td>
                  <td>{flow.severity || 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
