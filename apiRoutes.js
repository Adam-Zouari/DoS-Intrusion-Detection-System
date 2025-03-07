import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import csvParser from 'csv-parser';

const router = express.Router();

// Get __dirname equivalent in ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// API endpoint to get flow data
router.get('/flowData/:date', (req, res) => {
  const { date } = req.params;
  const filePath = path.join(
    'C:/Users/ademz/Courses/AI and CyberSecurity/CICFlowMeter/target/data/Analysed_Data', 
    `${date}_Flow.csv`
  );
  
  console.log(`Attempting to read file: ${filePath}`);
  
  // Check if file exists before trying to read it
  if (!fs.existsSync(filePath)) {
    console.log(`File not found: ${filePath}`);
    return res.status(404).json({ error: `File not found: ${date}_Flow.csv` });
  }
  
  const results = [];
  
  fs.createReadStream(filePath)
    .on('error', (error) => {
      console.error('Error reading CSV file:', error);
      res.status(500).json({ error: 'File cannot be read' });
    })
    .pipe(csvParser())
    .on('data', (data) => results.push(data))
    .on('end', () => {
      console.log(`Successfully read ${results.length} records`);
      res.json(results);
    });
});

// Add more API endpoints as needed

export default router;
