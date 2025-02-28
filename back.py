import os
import pandas as pd
import joblib

# Define directories
daily_dir = r"C:\Users\ademz\Courses\AI and CyberSecurity\CICFlowMeter\target\data\daily"
analyzed_dir = r"C:\Users\ademz\Courses\AI and CyberSecurity\CICFlowMeter\target\data\Analysed_Data"
model_path = r"C:\Users\ademz\Courses\AI and CyberSecurity\ML\SVM_model.joblib"

# Load the trained SVM model
model = joblib.load(model_path)

# Ensure the analyzed_data directory exists
os.makedirs(analyzed_dir, exist_ok=True)

# Columns to be removed from the feature set
columns_to_remove = ["Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp", "Label"]

# Encoding Mapping
label_mapping = {0: "BENIGN", 1: "DDoS", 2: "DoS", 3: "PortScan"}

# Process each CSV file in the daily directory
for filename in os.listdir(daily_dir):
    if filename.endswith(".csv"):
        file_path = os.path.join(daily_dir, filename)
        
        # Load the CSV file into a DataFrame
        df = pd.read_csv(file_path)

        # Remove the specified columns if they exist in the DataFrame
        df_filtered = df.drop(columns=[col for col in columns_to_remove if col in df.columns], errors="ignore")

        # Ensure the remaining columns are used as features
        X = df_filtered.values

        # Predict labels using the trained model
        y_pred = model.predict(X)

        # Convert predicted labels to their encoded form
        y_encoded = [label_mapping.get(label, -1) for label in y_pred]  # -1 for unknown labels

        # Add predictions to the DataFrame
        df["Label"] = y_encoded

        # Save the updated DataFrame to the analyzed_data directory
        output_file_path = os.path.join(analyzed_dir, filename)
        df.to_csv(output_file_path, index=False)

        # Remove the analyzed file after processing
        os.remove(file_path)

        print(f"Processed, saved, and deleted: {file_path}")

print("✅ All files have been analyzed, saved, and removed successfully!")

