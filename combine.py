import pandas as pd
import os

# Specify the folder containing the CSV files
folder_path = 'C:/Users/ademz/Courses/AI&CyberSecurity/Data/TrafficLabelling'

# Get all CSV files in the folder
csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

# Read and combine all CSV files
combined_df = pd.concat([pd.read_csv(os.path.join(folder_path, file)) for file in csv_files], ignore_index=True)

# Optionally, save the combined dataframe to a new CSV file
combined_df.to_csv('C:/Users/ademz/Courses/AI&CyberSecurity/Data/TrafficLabelling/cicddos2019_dataset.csv', index=False)





print("Files combined and original files removed successfully!")