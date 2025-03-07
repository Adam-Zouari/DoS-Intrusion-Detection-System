const express = require('express');
const fs = require('fs');
const path = require('path');
const cors = require('cors');
const csv = require('csv-parser');

const app = express();
const PORT = 3001;

// Enable CORS for all routes
app.use(cors());

// Serve static files from the public directory if you have one
app.use(express.static(path.join(__dirname, 'public')));

// API endpoint to get flow data
app.get('/api/flow-data/:date', (req, res) => {
  const { date } = req.params;
  const filePath = path.join(
    'C:/Users/ademz/Courses/AI and CyberSecurity/CyberAttacks-Dashboard/data', 
    `${date}_Flow.csv`
  );
  
  const results = [];
  
  // Check if file exists before trying to read it
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: `File not found: ${date}_Flow.csv` });
  }
  
  fs.createReadStream(filePath)
    .on('error', (error) => {
      console.error('Error reading CSV file:', error);
      res.status(500).json({ error: 'File cannot be read' });
    })
    .pipe(csv())
    .on('data', (data) => results.push(data))
    .on('end', () => {
      res.json(results);
    });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
