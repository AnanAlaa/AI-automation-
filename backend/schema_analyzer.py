def analyze_schema(df):
    schema = {
        "rows": len(df),
        "columns": []
    }

    for column in df.columns:
        schema["columns"].append({
            "name": column,
            "dtype": str(df[column].dtype),
            "sample_values": df[column].dropna().head(5).tolist()
        })

    return schema