import pandas as pd
import sys

sheet_url = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"

if '/d/' in sheet_url:
    sheet_id = sheet_url.split('/d/')[1].split('/')[0]

url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid=0"

df = pd.read_csv(url, header=None)

for idx in range(len(df)):
    row = df.iloc[idx]
    a = str(row[0]) if not pd.isna(row[0]) else "ריק"
    b = str(row[1]) if not pd.isna(row[1]) else "ריק"
    print(f"שורה {idx}: A='{a}' | B='{b}'")
