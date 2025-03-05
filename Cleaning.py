import pandas as pd
import numpy as np

# Load your CSV file
df = pd.read_csv("C:/Users/ademz/Courses/AI&CyberSecurity/Data/TrafficLabelling/Combined2019")
print(df[" Label"].isna().sum())
# Drop the column
df = df.drop(columns=[" Fwd Header Length.1"])

print(len(df.columns))

df.columns = [
    "Flow ID", "Src IP", "Src Port", "Dst IP", "Dst Port", "Protocol", "Timestamp",
    "Flow Duration", "Total Fwd Packet", "Total Bwd packets", "Total Length of Fwd Packet",
    "Total Length of Bwd Packet", "Fwd Packet Length Max", "Fwd Packet Length Min",
    "Fwd Packet Length Mean", "Fwd Packet Length Std", "Bwd Packet Length Max",
    "Bwd Packet Length Min", "Bwd Packet Length Mean", "Bwd Packet Length Std",
    "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max",
    "Flow IAT Min", "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Max",
    "Fwd IAT Min", "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std", "Bwd IAT Max",
    "Bwd IAT Min", "Fwd PSH Flags", "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags",
    "Fwd Header Length", "Bwd Header Length", "Fwd Packets/s", "Bwd Packets/s",
    "Packet Length Min", "Packet Length Max", "Packet Length Mean", "Packet Length Std",
    "Packet Length Variance", "FIN Flag Count", "SYN Flag Count", "RST Flag Count",
    "PSH Flag Count", "ACK Flag Count", "URG Flag Count", "CWR Flag Count", "ECE Flag Count",
    "Down/Up Ratio", "Average Packet Size", "Fwd Segment Size Avg", "Bwd Segment Size Avg",
    "Fwd Bytes/Bulk Avg", "Fwd Packet/Bulk Avg", "Fwd Bulk Rate Avg", "Bwd Bytes/Bulk Avg",
    "Bwd Packet/Bulk Avg", "Bwd Bulk Rate Avg", "Subflow Fwd Packets", "Subflow Fwd Bytes",
    "Subflow Bwd Packets", "Subflow Bwd Bytes", "FWD Init Win Bytes", "Bwd Init Win Bytes",
    "Fwd Act Data Pkts", "Fwd Seg Size Min", "Active Mean", "Active Std", "Active Max",
    "Active Min", "Idle Mean", "Idle Std", "Idle Max", "Idle Min", "Label"
]



# Define a mapping of specific attack labels to categories
attack_categories = {
    'BENIGN': 'BENIGN',
    'DoS Hulk': 'DoS',
    'DoS GoldenEye': 'DoS',
    'DoS slowloris': 'DoS',
    'DoS Slowhttptest': 'DoS',
    'DDoS': 'DDoS',
    'PortScan': 'PortScan',
    'FTP-Patator': 'Brute Force',
    'SSH-Patator': 'Brute Force',
    'Web Attack \x96 Brute Force': 'Web Attack',
    'Web Attack \x96 XSS': 'Web Attack',
    'Web Attack \x96 Sql Injection': 'Web Attack',
    'Bot': 'Bot',
    'Infiltration': 'Infiltration',
    'Heartbleed': 'Vulnerability Exploit',
}

# Function to map detailed attack label to a category
def map_to_category(label):
    return attack_categories.get(label, 'Unknown')  # Default to 'Unknown' if not found

# Apply the mapping function to the 'Label' column
df['ClassLabel'] = df['Label'].apply(map_to_category)

# Drop rows with 'Unknown' class labels
df = df[df['ClassLabel'] != 'Unknown']


print(df["ClassLabel"].value_counts())


for column in df.columns:
    print(f"NaN values in {column}: {df[column].isna().sum()}")


# Identify columns with inf values

numeric_df = df.select_dtypes(include=[np.number])

inf_columns = numeric_df.columns[np.isinf(numeric_df).any()].tolist()

# Print result
print("Columns containing infinity values:", inf_columns)


# Check for inf values in the specific columns
inf_counts = df[['Flow Bytes/s', 'Flow Packets/s']].applymap(np.isinf).sum()

# Display the number of infinite values per column
print("Number of infinite values in 'Flow Bytes/s' and 'Flow Packets/s':\n", inf_counts)

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna()

# Select the two problematic columns
columns_to_check = ['Flow Bytes/s', 'Flow Packets/s']

# Describe the two problematic columns
description = df[columns_to_check].describe()

# Display the description
print("Description for 'Flow Bytes/s' and 'Flow Packets/s':\n", description)






# Save the modified DataFrame to a new CSV file
df.to_csv('clean_cicddos.csv', index=False)

print("Class labels have been added successfully!")






