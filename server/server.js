const express = require('express');
const http = require('http');
const cors = require('cors');
const socketIo = require('socket.io');
const apiRoutes = require('./routes/apiRoutes');
const dataService = require('./services/dataService');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

// Middleware
app.use(cors());
app.use(express.json());

// API routes
app.use('/api', apiRoutes);

// Socket.io for real-time updates
io.on('connection', (socket) => {
  console.log('Client connected');
  
  // Send initial data
  dataService.getInitialData().then(data => {
    socket.emit('initialData', data);
  });
  
  // Set up interval for real-time updates
  const updateInterval = setInterval(() => {
    dataService.getLatestData().then(update => {
      socket.emit('dataUpdate', update);
    });
  }, 10000); // Update every 10 seconds
  
  socket.on('disconnect', () => {
    console.log('Client disconnected');
    clearInterval(updateInterval);
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).send('Something broke!');
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
  
  // Initialize data service
  dataService.initializeDataService();
});
