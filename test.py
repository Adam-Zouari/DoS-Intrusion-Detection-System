import pandas as pd

df = pd.read_csv("C:/Users/ademz/Courses/AI&CyberSecurity/Data/TrafficLabelling/cicddos2019")
print(df.head())
print(df[" Label"].value_counts())