import { exec } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const serverPath = path.join(__dirname, '..', 'server.js');

console.log('Starting server...');
const server = exec(`node ${serverPath}`);

server.stdout.on('data', (data) => {
  console.log(data);
});

server.stderr.on('data', (data) => {
  console.error(`Error: ${data}`);
});
