const express = require('express');
const http = require('http');
const cors = require('cors');
const apiRoutes = require('./routes/apiRoutes');
const dataService = require('./services/dataService');

const app = express();
const server = http.createServer(app);

// Middleware
app.use(cors());
app.use(express.json());

// API routes
app.use('/api', apiRoutes);

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  
  // Initial data service initialization
  dataService.initializeDataService();
  
  // Set up interval to initialize data service every 5 seconds
  const dataServiceInterval = setInterval(() => {
    console.log('Refreshing data service...');
    dataService.initializeDataService();
  }, 5000);
  
  // Handle server shutdown (optional)
  process.on('SIGTERM', () => {
    clearInterval(dataServiceInterval);
    // Other cleanup as needed
  });
});
