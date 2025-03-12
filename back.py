import os
import pandas as pd
import joblib
import time
import datetime
import logging
import json
import threading
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import numpy as np

# Load configuration from JSON
with open("C:/Users/ademz/Courses/AI and CyberSecurity/Back/config.json", "r") as f:
    config = json.load(f)

daily_dir = config["daily_dir"]
analyzed_dir = config["analyzed_dir"]
model_path = config["model_path"]

# Load the trained SVM model
model = joblib.load(model_path)

# Ensure the analyzed directory exists
os.makedirs(analyzed_dir, exist_ok=True)

# Logging setup
logging.basicConfig(filename="file_monitor.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Columns to be removed
columns_to_remove = ["Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp", "Label"]

# Encoding Mapping
label_mapping = {0: "BENIGN", 1: "DDoS", 2: "DoS", 3: "PortScan"}

# Track processed file sizes (by file name)
last_processed_sizes = {}

def get_today_filename():
    """Generate the current day's filename."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return f"{today}_Flow.csv"


def process_new_lines(file_path):
    """Process only new lines from the file and update the analyzed version."""
    filename = os.path.basename(file_path)  # Get the file name
    output_file_path = os.path.join(analyzed_dir, filename)

    try:
        # Get current file size
        current_size = os.path.getsize(file_path)
        last_size = last_processed_sizes.get(filename, 0)  # Use file name as the key

        # If no new data, return
        if current_size <= last_size:
            return

        skip_rows = 0
        df_analyzed = None
        
        if os.path.exists(output_file_path):
            try:
                # Add error handling for reading the analyzed file
                df_analyzed = pd.read_csv(output_file_path, error_bad_lines=False, warn_bad_lines=True)
                skip_rows = df_analyzed.shape[0]
            except Exception as e:
                logging.error(f"Error reading analyzed file {output_file_path}: {e}")
                # If we can't read the existing file, we'll treat it as non-existent
                df_analyzed = None

        # Read only new rows with error handling
        try:
            # Use error_bad_lines=False to skip problematic rows
            df_to_process = pd.read_csv(file_path, 
                                      skiprows=range(1, skip_rows+1), 
                                      error_bad_lines=False,  
                                      warn_bad_lines=True,
                                      on_bad_lines='skip')
        except TypeError:
            # For newer pandas versions where error_bad_lines is deprecated
            df_to_process = pd.read_csv(file_path, 
                                      skiprows=range(1, skip_rows+1), 
                                      on_bad_lines='skip')

        # Handle missing values in the dataset (NaN)
        df_to_process = df_to_process.replace([np.inf, -np.inf], np.nan)
        df_to_process = df_to_process.dropna()

        if df_to_process.empty:
            return
            
        # Filter out rows where Protocol is 0
        initial_row_count = df_to_process.shape[0]
        if "Protocol" in df_to_process.columns:
            df_to_process = df_to_process[df_to_process["Protocol"] != 0]
            filtered_row_count = initial_row_count - df_to_process.shape[0]
            if filtered_row_count > 0:
                logging.info(f"Filtered out {filtered_row_count} rows with Protocol 0 from {filename}")
            
            if df_to_process.empty:
                logging.info(f"All rows were filtered out from {filename}")
                return

        # Remove unnecessary columns
        df_filtered = df_to_process.drop(columns=[col for col in columns_to_remove if col in df_to_process.columns], errors="ignore")

        # Make sure we have all the expected columns for the model
        expected_columns = model.feature_names_in_ if hasattr(model, 'feature_names_in_') else None
        if expected_columns is not None:
            missing_columns = set(expected_columns) - set(df_filtered.columns)
            if missing_columns:
                logging.warning(f"Missing columns for model: {missing_columns}")
                # Add missing columns with default values
                for col in missing_columns:
                    df_filtered[col] = 0

            # Ensure columns are in the right order
            df_filtered = df_filtered[expected_columns]

        # Predict labels
        X = df_filtered.values
        y_pred = model.predict(X)
        df_to_process["Label"] = [label_mapping.get(label, -1) for label in y_pred]

        # Append processed data
        df_updated = pd.concat([df_analyzed, df_to_process], ignore_index=True) if df_analyzed is not None else df_to_process
        df_updated.to_csv(output_file_path, index=False)

        logging.info(f"Processed {df_to_process.shape[0]} new rows from {filename}")

        # Update last processed size with the file name (not path)
        last_processed_sizes[filename] = current_size

    except Exception as e:
        logging.error(f"Error processing {filename}: {e}")
        traceback.print_exc()

class FlowFileHandler(FileSystemEventHandler):
    """Handles new and modified CSV files in real-time."""
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.csv'):
            process_new_lines(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.csv'):
            filename = os.path.basename(event.src_path)  # Get the file name
            last_processed_sizes[filename] = 0  # Use file name as the key
            process_new_lines(event.src_path)

def monitor_today_file():
    """Continuously monitor today's file in a separate thread."""
    while not stop_event.is_set():
        time.sleep(1)
        today_file = get_today_filename()
        today_path = os.path.join(daily_dir, today_file)
        if os.path.exists(today_path):
            process_new_lines(today_path)

stop_event = threading.Event()

def main():
    # Process only today's file
    today_file = get_today_filename()
    today_path = os.path.join(daily_dir, today_file)
    if os.path.exists(today_path):
        last_processed_sizes[today_file] = 0  # Use file name as the key
        process_new_lines(today_path)

    # Start watchdog observer
    event_handler = FlowFileHandler()
    observer = Observer()
    observer.schedule(event_handler, daily_dir, recursive=False)
    observer.start()

    # Start monitoring today’s file in a separate thread
    monitor_thread = threading.Thread(target=monitor_today_file, daemon=True)
    monitor_thread.start()

    print("Monitoring started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping monitoring...")
        stop_event.set()
        observer.stop()
        monitor_thread.join()
    observer.join()

if __name__ == "__main__":
    main()
