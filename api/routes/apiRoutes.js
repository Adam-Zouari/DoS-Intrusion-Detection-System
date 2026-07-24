const express = require('express');
const router = express.Router();
const dataService = require('../services/dataService');

// Get network summary
router.get('/network-summary', async (req, res) => {
  try {
    const data = await dataService.getLatestData();
    res.json(data.networkSummary);
  } catch (error) {
    console.error('Error getting network summary:', error);
    res.status(500).json({ error: 'Failed to fetch network summary' });
  }
});

// Get machine details
router.get('/machine-details', async (req, res) => {
  try {
    const data = await dataService.getLatestData();
    res.json(data.machineDetails);
  } catch (error) {
    console.error('Error getting machine details:', error);
    res.status(500).json({ error: 'Failed to fetch machine details' });
  }
});

// Get machine details for a specific IP
router.get('/machine-details/:ip', async (req, res) => {
  try {
    const { ip } = req.params;
    const data = await dataService.getLatestData();
    const machine = data.machineDetails.find(m => m.ip === ip);
    
    if (!machine) {
      return res.status(404).json({ error: 'Machine not found' });
    }
    
    res.json(machine);
  } catch (error) {
    console.error('Error getting machine details:', error);
    res.status(500).json({ error: 'Failed to fetch machine details' });
  }
});

// Get real-time traffic analysis
router.get('/traffic-analysis', async (req, res) => {
  try {
    const data = await dataService.getLatestData();
    res.json(data.trafficAnalysis);
  } catch (error) {
    console.error('Error getting traffic analysis:', error);
    res.status(500).json({ error: 'Failed to fetch traffic analysis' });
  }
});

// Get anomaly detection data
router.get('/anomaly-detection', async (req, res) => {
  try {
    const data = await dataService.getLatestData();
    res.json(data.anomalyDetection);
  } catch (error) {
    console.error('Error getting anomaly detection data:', error);
    res.status(500).json({ error: 'Failed to fetch anomaly detection data' });
  }
});

// Get connection logs with pagination
router.get('/connection-logs', async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 100;
    const filter = req.query.filter || '';
    
    const data = await dataService.getLatestData();
    let logs = data.connectionLogs;
    
    // Apply filtering if requested
    if (filter) {
      logs = logs.filter(log => {
        return log['Src IP'].includes(filter) || 
               log['Dst IP'].includes(filter) ||
               log['Protocol'].includes(filter) ||
               log['Label'].includes(filter);
      });
    }
    
    const startIdx = (page - 1) * limit;
    const paginatedLogs = logs.slice(startIdx, startIdx + limit);
    
    res.json({
      total: logs.length,
      page,
      limit,
      logs: paginatedLogs
    });
  } catch (error) {
    console.error('Error getting connection logs:', error);
    res.status(500).json({ error: 'Failed to fetch connection logs' });
  }
});

// Get all data in one request
router.get('/all-data', async (req, res) => {
  try {
    const data = await dataService.getLatestData();
    res.json(data);
  } catch (error) {
    console.error('Error getting all data:', error);
    res.status(500).json({ error: 'Failed to fetch data' });
  }
});

// Get flow data for a specific date
router.get('/flow-data', async (req, res) => {
  try {
    const date = req.query.date || new Date().toISOString().split('T')[0];
    const result = await dataService.getFlowData(date);
    
    // Include timestamp in response header
    if (result.timestamp) {
      res.setHeader('Last-Modified', result.timestamp.toUTCString());
    }
    
    res.json(result.data || []);
  } catch (error) {
    console.error('Error fetching flow data:', error);
    res.status(500).json({ error: 'Failed to fetch flow data' });
  }
});

module.exports = router;
