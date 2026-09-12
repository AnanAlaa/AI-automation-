from backend.data_loader import load_csv


file_path = "data/enterprise_sales_revenue_data.csv"

df = load_csv(file_path)

print("CSV loaded successfully!")
print("Rows:", len(df))
print("Columns:", list(df.columns))
print(df.head())