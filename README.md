# CyberAttacks Dashboard

A comprehensive dashboard for visualizing and analyzing network traffic and potential cyber attacks.

## Features

- Overall Network Summary
- Machine (Host) Details
- Real-Time Traffic Analysis
- Anomaly Detection & Alerts
- Detailed Connection Logs

## Setup Instructions

### Server Setup

1. Navigate to the server directory:
   ```
   cd server
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the server:
   ```
   npm start
   ```

The server will run on port 5000 by default.

### Data Source

The application reads network flow data from CSV files stored at:
`CICFlowMeter\target\data\Analysed_Data`

Each day's data is stored in a file named with the format: `YYYY-MM-DD_Flow.csv`

## API Endpoints

- GET `/api/network-summary` - Get overall network statistics
- GET `/api/machine-details` - Get details for all machines
- GET `/api/machine-details/:ip` - Get details for a specific machine
- GET `/api/traffic-analysis` - Get real-time traffic analysis
- GET `/api/anomaly-detection` - Get anomaly detection data
- GET `/api/connection-logs` - Get connection logs with pagination
- GET `/api/all-data` - Get all dashboard data

## Real-time Updates

Real-time updates are provided through Socket.IO. Connect to the server's socket to receive automatic updates.
