const path = require('path');

module.exports = {
  // Path to the data directory
  DATA_DIRECTORY: process.env.DATA_DIRECTORY || path.resolve(__dirname, '..', 'runtime-data', 'analyzed'),
  
  // Known attack types from the dataset
  ATTACK_TYPES: ['DDOS', 'DOS', 'PORT SCAN', 'BRUTE FORCE'],
  
  // Server port
  PORT: process.env.PORT || 5000,
  
  // Client URL for CORS
  CLIENT_URL: process.env.CLIENT_URL || 'http://localhost:5173'
};
