import React, { useMemo, useState } from 'react';
import { FlowData, AttackStats, AttackType } from '../../types/flowData';
import { processAnomalies } from '../../services/dataService';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import './AnomalyDetection.css';

interface AnomalyDetectionProps {
  data: FlowData[];
}

const COLORS = {
  low: '#4caf50',
  medium: '#ff9800',
  high: '#f44336'
};

const ATTACK_COLORS = {
  'BENIGN': '#4caf50',
  'DOS': '#ff9800'
};

const ATTACK_DESCRIPTIONS = {
  'BENIGN': 'Normal network traffic with no malicious intent detected.',
  'DOS': 'Denial of Service attack attempting to make a service unavailable by flooding it with traffic.'
};

const AnomalyDetection: React.FC<AnomalyDetectionProps> = ({ data }) => {
  const attacks = useMemo(() => processAnomalies(data), [data]);
  const [selectedAttack, setSelectedAttack] = useState<AttackType | null>(null);
  
  const attacksWithoutBenign = useMemo(() => {
    return attacks.filter(attack => attack.attackType !== 'BENIGN');
  }, [attacks]);
  
  const benignStats = useMemo(() => {
    return attacks.find(attack => attack.attackType === 'BENIGN');
  }, [attacks]);
  
  const selectedAttackDetails = useMemo(() => {
    return attacks.find(attack => attack.attackType === selectedAttack);
  }, [attacks, selectedAttack]);
  
  // Get suspicious flag patterns (high SYN counts without corresponding ACK can indicate scanning)
  const suspiciousPatterns = useMemo(() => {
    const patterns: {
      ip: string;
      pattern: string;
      synCount?: number;
      ackCount?: number;
      ratio?: string;
      severity: 'low' | 'medium' | 'high';
      rstCount?: number;
      packetsPerSec?: string;
    }[] = [];
    
    // Group flows by source IP
    const hostFlows = new Map<string, FlowData[]>();
    
    data.forEach(flow => {
      const srcIP = flow['Src IP'];
      if (srcIP) { // Check if srcIP is defined
        if (!hostFlows.has(srcIP)) {
          hostFlows.set(srcIP, []);
        }
        hostFlows.get(srcIP)!.push(flow);
      }
    });
    
    // Check for suspicious patterns
    hostFlows.forEach((flows, ip) => {
      // SYN scan pattern: many SYNs, few ACKs
      const totalSYN = flows.reduce((sum, flow) => sum + (flow['SYN Flag Count'] || 0), 0);
      const totalACK = flows.reduce((sum, flow) => sum + (flow['ACK Flag Count'] || 0), 0);
      
      if (totalSYN > 20 && totalSYN > totalACK * 3) {
        patterns.push({
          ip,
          pattern: 'SYN Scan',
          synCount: totalSYN,
          ackCount: totalACK,
          ratio: totalACK > 0 ? (totalSYN / totalACK).toFixed(2) : 'N/A',
          severity: 'high'
        });
      }
      
      // RST flood pattern: many RSTs
      const totalRST = flows.reduce((sum, flow) => sum + (flow['RST Flag Count'] || 0), 0);
      if (totalRST > 30) {
        patterns.push({
          ip,
          pattern: 'RST Flood',
          rstCount: totalRST,
          severity: totalRST > 100 ? 'high' : 'medium'
        });
      }
      
      // High flow rate pattern
      const flowRate = flows.reduce((sum, flow) => sum + (flow['Flow Packets/s'] || 0), 0);
      if (flowRate > 1000) {
        patterns.push({
          ip,
          pattern: 'High Flow Rate',
          packetsPerSec: flowRate.toFixed(2),
          severity: flowRate > 10000 ? 'high' : 'medium'
        });
      }
    });
    
    return patterns;
  }, [data]);
  
  // For pie chart visualization
  const attackDistribution = useMemo(() => {
    return attacks.map(attack => ({
      name: attack.attackType,
      value: attack.count,
      color: ATTACK_COLORS[attack.attackType as keyof typeof ATTACK_COLORS] || '#999'
    }));
  }, [attacks]);
  
  return (
    <div className="anomaly-detection">
      <h2>Anomaly Detection & Alerts</h2>
      
      <div className="anomaly-overview">
        <div className="anomaly-cards">
          <div className={`anomaly-card ${attacksWithoutBenign.length > 0 ? 'alert' : 'safe'}`}>
            <h3>Attack Status</h3>
            <p className="anomaly-value">
              {attacksWithoutBenign.length > 0 
                ? `${attacksWithoutBenign.reduce((sum, a) => sum + a.count, 0)} Attacks Detected` 
                : 'No Attacks Detected'}
            </p>
            <p className="anomaly-label">
              {attacksWithoutBenign.length > 0 
                ? `${attacksWithoutBenign.length} different attack types` 
                : 'Network appears secure'}
            </p>
          </div>
          
          <div className={`anomaly-card ${suspiciousPatterns.length > 0 ? 'alert' : 'safe'}`}>
            <h3>Suspicious Patterns</h3>
            <p className="anomaly-value">{suspiciousPatterns.length}</p>
            <p className="anomaly-label">
              {suspiciousPatterns.length > 0 
                ? 'Suspicious traffic patterns detected' 
                : 'No suspicious patterns'}
            </p>
          </div>
          
          <div className="anomaly-card">
            <h3>Benign Traffic</h3>
            <p className="anomaly-value">{benignStats?.count.toLocaleString() || 0}</p>
            <p className="anomaly-label">Normal Flows</p>
          </div>
          
          <div className="anomaly-card">
            <h3>Affected IPs</h3>
            <p className="anomaly-value">
              {new Set(attacks.flatMap(a => a.relatedIPs)).size}
            </p>
            <p className="anomaly-label">Unique IP addresses</p>
          </div>
        </div>
        
        <div className="chart-container">
          <h3>Attack Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart 
              data={attackDistribution}
              margin={{ top: 20, right: 30, left: 60, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="name" 
                label={{ 
                  value: 'Attack Type', 
                  position: 'bottom', 
                  offset: 10,
                  textAnchor: 'middle'
                }} 
              />
              <YAxis 
                label={{ 
                  value: 'Number of Flows', 
                  angle: -90, 
                  position: 'center',
                  textAnchor: 'middle',
                  dx: -50
                }} 
              />
              <Tooltip formatter={(value) => [`${value} connections`, undefined]} />
              {/* Removing Legend component entirely */}
              <Bar 
                dataKey="value" 
                onClick={(data) => setSelectedAttack(data.name as AttackType)}
              >
                {attackDistribution.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={entry.color} 
                    style={{ cursor: 'pointer' }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {selectedAttackDetails && (
        <div className="attack-details">
          <h3>
            {selectedAttackDetails.attackType} Details
            <span className={`severity-badge ${selectedAttackDetails.severity}`}>
              {selectedAttackDetails.severity.toUpperCase()}
            </span>
          </h3>
          
          <p className="attack-description">
            {ATTACK_DESCRIPTIONS[selectedAttackDetails.attackType as keyof typeof ATTACK_DESCRIPTIONS] || 'Description not available'}
          </p>
          
          <div className="attack-stats">
            <div className="attack-stat-item">
              <span className="stat-label">Total Connections</span>
              <span className="stat-value">{selectedAttackDetails.count.toLocaleString()}</span>
            </div>
            
            <div className="attack-stat-item">
              <span className="stat-label">Related IPs</span>
              <span className="stat-value">{selectedAttackDetails.relatedIPs.length.toLocaleString()}</span>
            </div>
          </div>
          
          {selectedAttackDetails.relatedIPs.length > 0 && (
            <div className="related-ips">
              <h4>Related IP Addresses</h4>
              <div className="ip-tags">
                {selectedAttackDetails.relatedIPs.slice(0, 50).map((ip, index) => (
                  <span key={index} className="ip-tag">{ip}</span>
                ))}
                {selectedAttackDetails.relatedIPs.length > 50 && (
                  <span className="ip-tag more">
                    +{selectedAttackDetails.relatedIPs.length - 50} more
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      <div className="suspicious-patterns">
        <h3>Suspicious Traffic Patterns</h3>
        {suspiciousPatterns.length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Source IP</th>
                  <th>Suspicious Pattern</th>
                  <th>Details</th>
                  <th>Severity</th>
                </tr>
              </thead>
              <tbody>
                {suspiciousPatterns.map((pattern, index) => (
                  <tr key={index}>
                    <td>{pattern.ip}</td>
                    <td>{pattern.pattern}</td>
                    <td>
                      {pattern.pattern === 'SYN Scan' && (
                        <span>SYN: {pattern.synCount}, ACK: {pattern.ackCount}, Ratio: {pattern.ratio}</span>
                      )}
                      {pattern.pattern === 'RST Flood' && (
                        <span>RST Count: {pattern.rstCount}</span>
                      )}
                      {pattern.pattern === 'High Flow Rate' && (
                        <span>{pattern.packetsPerSec} packets/sec</span>
                      )}
                    </td>
                    <td>
                      <span className={`severity-badge ${pattern.severity}`}>
                        {pattern.severity.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="no-patterns">
            <p>No suspicious traffic patterns detected in the current dataset.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnomalyDetection;
