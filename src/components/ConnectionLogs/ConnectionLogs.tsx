import React, { useState, useMemo, useCallback } from 'react';
import { FlowData } from '../../types/flowData';
import './ConnectionLogs.css';

interface ConnectionLogsProps {
  data: FlowData[];
}

const ConnectionLogs: React.FC<ConnectionLogsProps> = ({ data }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [sortField, setSortField] = useState<keyof FlowData>('Timestamp');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [filterValue, setFilterValue] = useState('');
  const [filterField, setFilterField] = useState<keyof FlowData>('Label');

  const toggleSort = (field: keyof FlowData) => {
    if (field === sortField) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Get protocol name from number
  const getProtocolName = useCallback((protocol: number | string): string => {
    if (typeof protocol === 'number') {
      switch (protocol) {
        case 1: return 'ICMP';
        case 6: return 'TCP';
        case 17: return 'UDP';
        default: return `Protocol ${protocol}`;
      }
    }
    return String(protocol);
  }, []);

  const formatTimestamp = useCallback((timestamp: string): string => {
    try {
      // Parse DD/MM/YYYY HH:MM:SS AM/PM format
      const parts = timestamp.split(' ');
      if (parts.length >= 3) {
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
          const day = parseInt(dateParts[0]);
          const month = parseInt(dateParts[1]) - 1; // Month is 0-indexed in JS Date
          const year = parseInt(dateParts[2]);
          
          // Parse time parts
          const timeParts = parts[1].split(':');
          let hours = parseInt(timeParts[0]);
          const minutes = parseInt(timeParts[1]);
          const seconds = parseInt(timeParts[2]);
          
          // Handle AM/PM
          if (parts[2].toUpperCase() === 'PM' && hours < 12) {
            hours += 12;
          } else if (parts[2].toUpperCase() === 'AM' && hours === 12) {
            hours = 0;
          }
          
          const date = new Date(year, month, day, hours, minutes, seconds);
          return date.toLocaleString();
        }
      }
      // Fallback to default parsing if format doesn't match expected pattern
      return new Date(timestamp).toLocaleString();
    } catch (e) {
      return timestamp;
    }
  }, []);

  // Filter and sort data
  const filteredData = useMemo(() => {
    if (!filterValue) return data;
    
    return data.filter(flow => {
      if (filterField === 'Protocol') {
        // For Protocol field, convert number to name before comparing
        const protocolValue = flow[filterField];
        if (protocolValue === undefined) return false;
        const protocolName = getProtocolName(protocolValue);
        return protocolName.toLowerCase().includes(filterValue.toLowerCase());
      }
      
      const fieldValue = flow[filterField];
      if (fieldValue === undefined) return false;
      
      return String(fieldValue).toLowerCase().includes(filterValue.toLowerCase());
    });
  }, [data, filterField, filterValue, getProtocolName]);

  const sortedData = useMemo(() => {
    return [...filteredData].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      // Handle different types of values
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortDirection === 'asc' ? aValue - bValue : bValue - aValue;
      } 
      
      const aStr = String(aValue || '').toLowerCase();
      const bStr = String(bValue || '').toLowerCase();
      
      return sortDirection === 'asc' 
        ? aStr.localeCompare(bStr)
        : bStr.localeCompare(aStr);
    });
  }, [filteredData, sortField, sortDirection]);

  // Paginate data
  const paginatedData = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return sortedData.slice(startIndex, startIndex + rowsPerPage);
  }, [sortedData, currentPage, rowsPerPage]);

  const totalPages = useMemo(() => 
    Math.ceil(filteredData.length / rowsPerPage), 
  [filteredData.length, rowsPerPage]);

  // Common filter fields
  const filterFields: Array<keyof FlowData> = [
    'Label', 'Src IP', 'Dst IP', 'Protocol'
  ];

  const handleFilterChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFilterValue(e.target.value);
    setCurrentPage(1); // Reset to first page on filter change
  }, []);

  const handleFieldChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setFilterField(e.target.value as keyof FlowData);
    setCurrentPage(1); // Reset to first page on field change
  }, []);

  return (
    <div className="connection-logs">
      <h2>Detailed Connection Logs</h2>

      <div className="filter-controls">
        <div className="search-container">
          <select value={filterField} onChange={handleFieldChange}>
            {filterFields.map(field => (
              <option key={field as string} value={field as string}>{field}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder={`Search by ${filterField}...`}
            value={filterValue}
            onChange={handleFilterChange}
          />
        </div>
        <div className="pagination-info">
          Showing {paginatedData.length} of {filteredData.length} connections
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th onClick={() => toggleSort('Src IP')}>
                Source {sortField === 'Src IP' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Dst IP')}>
                Destination {sortField === 'Dst IP' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Protocol')}>
                Protocol {sortField === 'Protocol' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Flow Duration')}>
                Duration {sortField === 'Flow Duration' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Flow Bytes/s')}>
                Bytes/s {sortField === 'Flow Bytes/s' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Flow Packets/s' as keyof FlowData)}>
                Packets/s {sortField === 'Flow Packets/s' as keyof FlowData && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Timestamp')}>
                Time {sortField === 'Timestamp' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
              <th onClick={() => toggleSort('Label')}>
                Classification {sortField === 'Label' && (sortDirection === 'asc' ? '▲' : '▼')}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.length > 0 ? (
              paginatedData.map((flow, index) => (
                <tr key={index} className={flow['Label'] !== 'BENIGN' ? 'attack-row' : ''}>
                  <td>{flow['Src IP']}:{flow['Src Port']}</td>
                  <td>{flow['Dst IP']}:{flow['Dst Port']}</td>
                  <td>{getProtocolName(flow['Protocol'])}</td>
                  <td>{flow['Flow Duration'].toLocaleString()} ms</td>
                  <td>{Math.round(flow['Flow Bytes/s'] || 0).toLocaleString()}</td>
                  <td>{Math.round(flow['Flow Packets/s'] || 0).toLocaleString()}</td>
                  <td>{formatTimestamp(flow['Timestamp'])}</td>
                  <td>
                    <span className={`label-badge ${flow['Label']}`}>
                      {flow['Label']}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="no-data">No matching connections found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="pagination-controls">
        <div className="rows-per-page">
          <label>
            Rows per page:
            <select 
              value={rowsPerPage} 
              onChange={(e) => {
                setRowsPerPage(Number(e.target.value));
                setCurrentPage(1);
              }}
            >
              <option value={10}>10</option>
              <option value={15}>15</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
            </select>
          </label>
        </div>
        
        <div className="page-navigation">
          <button 
            onClick={() => setCurrentPage(1)} 
            disabled={currentPage === 1}
          >
            &laquo;
          </button>
          <button 
            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))} 
            disabled={currentPage === 1}
          >
            &lsaquo;
          </button>
          
          <span className="page-info">
            Page {currentPage} of {totalPages || 1}
          </span>
          
          <button 
            onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))} 
            disabled={currentPage === totalPages || totalPages === 0}
          >
            &rsaquo;
          </button>
          <button 
            onClick={() => setCurrentPage(totalPages)} 
            disabled={currentPage === totalPages || totalPages === 0}
          >
            &raquo;
          </button>
        </div>
      </div>

      <div className="connection-details-section">
        <h3>Connection Fields Guide</h3>
        <div className="fields-guide">
          <div className="guide-item">
            <h4>Basic Information</h4>
            <ul>
              <li><strong>Source/Destination:</strong> IP addresses and ports involved</li>
              <li><strong>Protocol:</strong> TCP, UDP, ICMP, or other network protocol</li>
              <li><strong>Time:</strong> When the flow was recorded</li>
            </ul>
          </div>
          
          <div className="guide-item">
            <h4>Performance Metrics</h4>
            <ul>
              <li><strong>Flow Duration:</strong> Length of the connection in milliseconds</li>
              <li><strong>Bytes/s:</strong> Data transfer rate</li>
              <li><strong>Packets/s:</strong> Number of packets per second</li>
            </ul>
          </div>
          
          <div className="guide-item">
            <h4>Classification</h4>
            <ul>
              <li><strong>BENIGN:</strong> Normal network traffic</li>
              <li><strong>DDOS:</strong> Distributed Denial of Service attack</li>
              <li><strong>DOS:</strong> Denial of Service attack</li>
              <li><strong>PORT SCAN:</strong> Port scanning activity</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConnectionLogs;
