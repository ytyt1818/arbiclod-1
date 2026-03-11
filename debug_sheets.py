import pandas as pd
import requests

sheet_id = "1O_a9_tEuubCuBqsX_dOqsKJlYhJEDGBbUZUF1Q9xoQU"
gid = "1278180562"

url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"

print(f"קורא מ: {url}")

# בדוק גישה
resp = requests.get(url)
print(f"סטטוס: {resp.status_code}")

if resp.status_code == 200:
    import io
    import pandas as pd
    df = pd.read_csv(io.StringIO(resp.text), header=None)
    print(f"נטען! שורות: {len(df)}")
    print("="*50)
    for idx in range(len(df)):
        row = df.iloc[idx]
        a = str(row[0]) if not pd.isna(row[0]) else "ריק"
        b = str(row[1]) if not pd.isna(row[1]) else "ריק"
        print(f"שורה {idx}: A='{a}' | B='{b}'")
else:
    print(f"❌ שגיאה: {resp.status_code}")
    print("הגיליון לא נגיש - וודא שהוא ציבורי!")
    print(f"תשובה: {resp.text[:200]}")
