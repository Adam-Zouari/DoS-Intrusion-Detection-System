# DoS Intrusion Detection System

A comprehensive real-time network intrusion detection system that uses machine learning to identify Denial of Service (DoS) attacks in network traffic. The system combines AI-powered traffic analysis with an interactive web dashboard for monitoring and visualization.

## Table of Contents
- [System Architecture](#system-architecture)
- [AI Model Training](#ai-model-training)
- [Python Server (Real-time Analysis)](#python-server-real-time-analysis)
- [Dashboard Overview](#dashboard-overview)
- [Setup Instructions](#setup-instructions)
- [API Reference](#api-reference)

---

## System Architecture

The system consists of three main components:

1. **CICFlowMeter**: Captures network traffic and generates flow-based CSV files
2. **Python ML Server**: Monitors new traffic data and performs real-time DoS detection using trained models
3. **Node.js API + React Dashboard**: Serves analyzed data and provides visualization interface

```
Network Traffic → CICFlowMeter → Daily CSV Files → Python ML Server → Analyzed Data → Node.js API → React Dashboard
```

---

## AI Model Training

### Overview

The AI model is trained to classify network traffic as either **BENIGN** or **DoS** (Denial of Service) attacks. The training process involves data collection, preprocessing, feature engineering, model selection, and evaluation.

### Datasets Used

#### 1. CIC-IDS-2017 Dataset
- **Location**: `AI-Model/CIC-IDS-2017/`
- **Source**: Canadian Institute for Cybersecurity Intrusion Detection Dataset
- **Size**: ~1.58GB (2.8M+ network flows)
- **Attack Types**: DoS Hulk, DoS GoldenEye, DoS slowloris, DoS Slowhttptest, DDoS, PortScan, Brute Force, Web Attacks, Bot, Infiltration, Heartbleed
- **Notebook**: `DDoS_ML.ipynb`

#### 2. Custom Collected Data
- **Location**: `AI-Model/Collected-Data/`
- **Files**: ACK-flood.csv, SYN-flood.csv, DoS_BENIGN.csv
- **Purpose**: Real-world traffic data collected from controlled environments
- **Notebook**: `CyberAttacks_Classification.ipynb`

### Data Preprocessing Pipeline

#### 1. Data Cleaning (`Cleaning.py`)
```python
# Key preprocessing steps:
- Remove duplicate column (Fwd Header Length.1)
- Standardize 84 feature column names
- Map attack labels to categories (BENIGN, DoS, DDoS, PortScan, etc.)
- Handle missing values (NaN detection and removal)
- Handle infinite values in Flow Bytes/s and Flow Packets/s
- Filter out unknown attack types
```

#### 2. Data Combination (`combine2.py`)
- Merges multiple CSV files from different capture sessions
- Handles encoding issues (ISO-8859-1)
- Creates unified dataset for training

#### 3. Class Balancing
The dataset is balanced using undersampling to ensure equal representation:
```python
# Balance BENIGN and DoS samples
target_size = df['Label'].value_counts().min()
df_balanced = df.groupby('Label').apply(
    lambda x: x.sample(target_size, random_state=42)
).reset_index(drop=True)
```

**Result**: ~19,927 BENIGN samples + ~19,927 DoS samples = 39,854 total balanced samples

### Feature Engineering

#### Selected Features (10 Critical Features)
After extensive analysis, the following 10 features were selected for optimal performance:

1. **Flow Duration**: Total duration of the network flow
2. **Total Fwd Packet**: Number of forward packets
3. **Fwd Packet Length Mean**: Average size of forward packets
4. **Flow Bytes/s**: Rate of bytes transferred per second
5. **Flow Packets/s**: Rate of packets transferred per second
6. **Flow IAT Mean**: Mean inter-arrival time between packets
7. **FIN Flag Count**: Number of FIN flags (connection termination)
8. **SYN Flag Count**: Number of SYN flags (connection initiation)
9. **RST Flag Count**: Number of RST flags (connection reset)
10. **ACK Flag Count**: Number of ACK flags (acknowledgment)

These features capture:
- **Traffic volume patterns** (packet counts, bytes)
- **Timing characteristics** (duration, inter-arrival times)
- **Protocol behavior** (TCP flags)

### Data Augmentation

To improve model robustness, data augmentation is applied to DoS samples:

```python
def augment_dos_data(df, augmentation_factor=1,
                     noise_scale1=0.05,  # 5% noise for Flow Packets/s
                     noise_scale2=10):    # 10% noise for other features
    # Adds controlled random noise to DoS samples
    # Preserves integer constraints for flag counts
    # Creates synthetic variations while maintaining attack characteristics
```

**Benefits**:
- Prevents overfitting
- Improves generalization to unseen attack patterns
- Maintains realistic traffic characteristics

### Model Training & Evaluation

#### Models Tested

Eight different machine learning algorithms were evaluated:

| Model | Accuracy | Precision | Recall | F1-Score | Notes |
|-------|----------|-----------|--------|----------|-------|
| **Logistic Regression** | 99.48% | 99.49% | 99.48% | 99.48% | **Selected Model** |
| Decision Tree | 99.99% | 99.99% | 99.99% | 99.99% | Prone to overfitting |
| Random Forest | 99.97% | 99.97% | 99.97% | 99.97% | High complexity |
| SVM (RBF kernel) | 99.89% | 99.89% | 99.89% | 99.89% | Slow inference |
| KNN | 99.99% | 99.99% | 99.99% | 99.99% | Memory intensive |
| Gradient Boosting | 99.96% | 99.96% | 99.96% | 99.96% | Slow training |
| XGBoost | 99.99% | 99.99% | 99.99% | 99.99% | High complexity |
| Naive Bayes | 100.00% | 100.00% | 100.00% | 100.00% | Overfitting suspected |

#### Final Model Selection: Logistic Regression

**Why Logistic Regression?**
- **Regularization**: L2 penalty (C=0.01) prevents overfitting
- **Balanced Performance**: High accuracy without perfect scores (avoiding overfitting)
- **Fast Inference**: Real-time prediction capability
- **Interpretability**: Clear feature importance
- **Stability**: Consistent performance across different data splits

**Model Configuration**:
```python
LogisticRegression(
    C=0.01,              # Strong regularization
    penalty="l2",        # Ridge regularization
    solver="lbfgs",      # Optimization algorithm
    max_iter=1000        # Convergence iterations
)
```

#### Training Process

1. **Data Split**: 80% training, 20% testing (stratified)
2. **Standardization**: StandardScaler for feature normalization
3. **Training**: Fit on balanced, augmented dataset
4. **Validation**: Cross-validation on test set

#### Model Performance Metrics

**Classification Report**:
```
              precision    recall  f1-score   support
    BENIGN       0.9949    0.9948    0.9949      3954
    DoS          0.9949    0.9948    0.9949      3986

    accuracy                         0.9948      7940
```

**Confusion Matrix**:
```
[[3934   20]
 [  21 3965]]
```

- **True Positives (DoS detected)**: 3,965
- **True Negatives (BENIGN detected)**: 3,934
- **False Positives**: 20 (0.5%)
- **False Negatives**: 21 (0.5%)

### Model Persistence

The trained model is saved using joblib:
```python
joblib.dump(model, "Logistic_Regression_model.joblib")
```

**Model File**: Used by Python server for real-time predictions

---

## Python Server (Real-time Analysis)

### Overview

The Python server (`Python_Server/back.py`) is the core component that performs real-time network traffic analysis. It monitors incoming network flow data, applies the trained ML model, and outputs classified results.

### Architecture

```
Daily CSV Files → File Monitor (Watchdog) → Incremental Processing → ML Prediction → Analyzed Output
```

### Key Features

#### 1. **Real-time File Monitoring**
Uses `watchdog` library to detect file system events:
- **File Creation**: Automatically processes new daily CSV files
- **File Modification**: Incrementally processes new rows as they're added
- **Continuous Monitoring**: Runs 24/7 without manual intervention

```python
class FlowFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        # Triggered when CSV file is updated
        process_new_lines(event.src_path)

    def on_created(self, event):
        # Triggered when new daily file is created
        process_new_lines(event.src_path)
```

#### 2. **Incremental Processing**
Efficiently handles large files by processing only new data:

```python
# Track file sizes to identify new data
last_processed_sizes = {}

def process_new_lines(file_path):
    current_size = os.path.getsize(file_path)
    last_size = last_processed_sizes.get(filename, 0)

    if current_size <= last_size:
        return  # No new data

    # Read only new rows (skip already processed rows)
    skip_rows = existing_analyzed_rows
    df_new = pd.read_csv(file_path, skiprows=range(1, skip_rows+1))
```

**Benefits**:
- Low memory footprint
- Fast processing (only new data)
- No duplicate predictions

#### 3. **Data Preprocessing Pipeline**

Before prediction, each new batch undergoes:

**a. Error Handling**:
```python
# Skip malformed rows
df = pd.read_csv(file_path, on_bad_lines='skip')
```

**b. Missing Value Handling**:
```python
# Replace infinite values with NaN
df = df.replace([np.inf, -np.inf], np.nan)
# Drop rows with NaN
df = df.dropna()
```

**c. Protocol Filtering**:
```python
# Filter out Protocol 0 (invalid/unknown protocols)
df = df[df["Protocol"] != 0]
```

**d. Feature Selection**:
```python
columns_to_keep = [
    "Flow Duration", "Total Fwd Packet", "Fwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean",
    "FIN Flag Count", "SYN Flag Count", "RST Flag Count", "ACK Flag Count"
]
df_filtered = df[columns_to_keep]
```

**e. Feature Alignment**:
```python
# Ensure features match model's expected input
expected_columns = model.feature_names_in_
df_filtered = df_filtered[expected_columns]
```

#### 4. **ML Prediction**

```python
# Load trained model
model = joblib.load(model_path)

# Predict (convert to numpy to avoid warnings)
y_pred = model.predict(df_filtered.values)

# Map numeric predictions to labels
label_mapping = {0: "BENIGN", 1: "DoS"}
df["Label"] = [label_mapping.get(label, -1) for label in y_pred]
```

#### 5. **Output Management**

```python
# Append predictions to analyzed file
output_file = os.path.join(analyzed_dir, filename)
df_updated = pd.concat([df_existing, df_new], ignore_index=True)
df_updated.to_csv(output_file, index=False)
```

**Output Structure**:
- **Location**: `Analysed_Data/YYYY-MM-DD_Flow.csv`
- **Format**: Original features + "Label" column (BENIGN/DoS)

### Configuration

The server uses a JSON configuration file (`config.json`):

```json
{
  "daily_dir": "path/to/daily/csv/files",
  "analyzed_dir": "path/to/analyzed/output",
  "model_path": "path/to/trained/model.joblib"
}
```

### Logging

All operations are logged to `file_monitor.log`:
- File processing events
- Number of rows processed
- Errors and exceptions
- Filtered row counts

### Multi-threading

```python
# Main monitoring thread
observer = Observer()
observer.schedule(event_handler, daily_dir, recursive=False)
observer.start()

# Dedicated thread for today's file (1-second polling)
monitor_thread = threading.Thread(target=monitor_today_file, daemon=True)
monitor_thread.start()
```

**Why two monitoring mechanisms?**
- **Watchdog Observer**: Detects file system events (creation, modification)
- **Polling Thread**: Ensures today's file is checked every second (backup mechanism)

### Performance Characteristics

- **Latency**: < 2 seconds from data arrival to prediction
- **Throughput**: Processes thousands of flows per second
- **Memory**: Incremental processing keeps memory usage low
- **Reliability**: Automatic error recovery and logging

### Running the Python Server

```bash
cd Python_Server
python back.py
```

**Output**:
```
Monitoring started. Press Ctrl+C to stop.
```

The server will:
1. Load the trained ML model
2. Process any existing today's file
3. Start monitoring for new/modified files
4. Log all activities to `file_monitor.log`

---

## Dashboard Overview

The web dashboard provides real-time visualization of network traffic and detected attacks.

### Key Features

- **Network Summary**: Overall statistics (total flows, attack percentage, protocol distribution)
- **Machine Details**: Per-host analysis with suspicious IP tracking
- **Traffic Analysis**: Time-series visualization of traffic patterns
- **Anomaly Detection**: Real-time alerts for detected DoS attacks
- **Connection Logs**: Detailed flow-level information with pagination

### Technology Stack

- **Frontend**: React + TypeScript + Vite
- **Backend**: Node.js + Express
- **Real-time Updates**: Socket.IO (auto-refresh every 5 seconds)
- **Visualization**: Recharts (pie charts, bar charts, line graphs)

### Dashboard Components

1. **Network Summary View**: Protocol distribution, attack vs benign ratio
2. **Machine Details View**: IP-based statistics, suspicious host identification
3. **Traffic Analysis View**: Temporal patterns, packet/byte rates
4. **Anomaly Detection View**: Attack timeline, severity indicators
5. **Connection Logs View**: Searchable, filterable flow records

---

## Setup Instructions

### Prerequisites

- **Python 3.8+** (for ML server)
- **Node.js 16+** (for API server and dashboard)
- **CICFlowMeter** (for network traffic capture)

### 1. Install Python Dependencies

```bash
cd Python_Server
pip install pandas numpy scikit-learn joblib watchdog
```

### 2. Configure Python Server

Edit `config.json`:
```json
{
  "daily_dir": "C:/path/to/CICFlowMeter/target/data/daily",
  "analyzed_dir": "C:/path/to/CICFlowMeter/target/data/Analysed_Data",
  "model_path": "C:/path/to/trained/model.joblib"
}
```

### 3. Start Python Server

```bash
python back.py
```

### 4. Install Node.js Dependencies

```bash
cd server
npm install
```

### 5. Start API Server

```bash
npm start
```

The server will run on `http://localhost:5000`

### 6. Start Dashboard (Development)

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173`

---

## API Reference

### Endpoints

- **GET** `/api/network-summary` - Overall network statistics
- **GET** `/api/machine-details` - All host details
- **GET** `/api/machine-details/:ip` - Specific host details
- **GET** `/api/traffic-analysis` - Traffic patterns over time
- **GET** `/api/anomaly-detection` - Detected attacks and anomalies
- **GET** `/api/connection-logs` - Paginated connection records
- **GET** `/api/all-data` - Complete dashboard data

### WebSocket Events

- **Connection**: `socket.on('connect')`
- **Data Updates**: Automatic push every 5 seconds
- **Disconnection**: `socket.on('disconnect')`

---

## Project Structure

```
DoS-Intrusion-Detection-System/
├── AI-Model/
│   ├── CIC-IDS-2017/
│   │   ├── DDoS_ML.ipynb          # CIC-IDS-2017 training notebook
│   │   └── Cleaning.py            # Data preprocessing script
│   └── Collected-Data/
│       ├── CyberAttacks_Classification.ipynb  # Custom data training
│       ├── combine2.py            # Dataset merging script
│       ├── Ack-flood.csv          # ACK flood attack data
│       ├── Syn-flood.csv          # SYN flood attack data
│       └── DoS_BENIGN.csv         # Benign traffic data
├── Python_Server/
│   ├── back.py                    # Real-time ML analysis server
│   └── config.json                # Server configuration
├── server/
│   ├── server.js                  # Node.js API server
│   ├── routes/                    # API route handlers
│   └── services/                  # Data processing services
├── src/
│   ├── App.tsx                    # Main React application
│   ├── components/                # Dashboard UI components
│   └── services/                  # API client services
└── README.md
```

---

## License

This project is for educational and research purposes.

## Acknowledgments

- **CIC-IDS-2017 Dataset**: Canadian Institute for Cybersecurity
- **CICFlowMeter**: Network traffic flow generator
- **scikit-learn**: Machine learning library
