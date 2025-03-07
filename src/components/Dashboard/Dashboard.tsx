import React, { useState, useEffect } from 'react';
import { fetchFlowData, processNetworkSummary, processHostDetails, processAnomalies } from '../../services/dataService';
import { FlowData } from '../../types/flowData';
import NetworkSummary from '../NetworkSummary/NetworkSummary';
import MachineDetails from '../MachineDetails/MachineDetails';
import TrafficAnalysis from '../TrafficAnalysis/TrafficAnalysis';
import AnomalyDetection from '../AnomalyDetection/AnomalyDetection';
import ConnectionLogs from '../ConnectionLogs/ConnectionLogs';
import './Dashboard.css';

const Dashboard: React.FC = () => {
  const [flowData, setFlowData] = useState<FlowData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('summary');
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  
  // Fetch data on component mount and periodically
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const data = await fetchFlowData();
        setFlowData(data);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        setError('Failed to fetch flow data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
    
    // Refresh data every 60 seconds
    const interval = setInterval(loadData, 60000);
    
    return () => clearInterval(interval);
  }, []);
  
  const renderActiveTab = () => {
    if (loading) {
      return <div className="loading">Loading data...</div>;
    }
    
    if (error) {
      return <div className="error">{error}</div>;
    }
    
    switch (activeTab) {
      case 'summary':
        return <NetworkSummary data={flowData} />;
      case 'machines':
        return <MachineDetails data={flowData} />;
      case 'traffic':
        return <TrafficAnalysis data={flowData} />;
      case 'anomalies':
        return <AnomalyDetection data={flowData} />;
      case 'logs':
        return <ConnectionLogs data={flowData} />;
      default:
        return <NetworkSummary data={flowData} />;
    }
  };
  
  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Network Traffic Analysis Dashboard</h1>
        <div className="last-updated">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </div>
      </header>
      
      <nav className="dashboard-nav">
        <ul>
          <li className={activeTab === 'summary' ? 'active' : ''}>
            <button onClick={() => setActiveTab('summary')}>Network Summary</button>
          </li>
          <li className={activeTab === 'machines' ? 'active' : ''}>
            <button onClick={() => setActiveTab('machines')}>Machine Details</button>
          </li>
          <li className={activeTab === 'traffic' ? 'active' : ''}>
            <button onClick={() => setActiveTab('traffic')}>Traffic Analysis</button>
          </li>
          <li className={activeTab === 'anomalies' ? 'active' : ''}>
            <button onClick={() => setActiveTab('anomalies')}>Anomaly Detection</button>
          </li>
          <li className={activeTab === 'logs' ? 'active' : ''}>
            <button onClick={() => setActiveTab('logs')}>Connection Logs</button>
          </li>
        </ul>
      </nav>
      
      <main className="dashboard-content">
        {renderActiveTab()}
      </main>
      
      <footer className="dashboard-footer">
        <p>CyberAttacks Dashboard - Flow Data Analysis</p>
      </footer>
    </div>
  );
};

export default Dashboard;
