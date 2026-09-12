import pandas as pd


def _get_revenue(df, revenue_definition):
    definition_type = revenue_definition["type"]

    if definition_type == "column":
        column = revenue_definition["column"]

        return pd.to_numeric(
            df[column],
            errors="coerce"
        )

    elif definition_type == "multiply":
        quantity_column = revenue_definition["quantity_column"]
        price_column = revenue_definition["price_column"]

        quantity = pd.to_numeric(
            df[quantity_column],
            errors="coerce"
        )

        price = pd.to_numeric(
            df[price_column],
            errors="coerce"
        )

        return quantity * price

    elif definition_type == "multiply_discount":
        quantity = pd.to_numeric(
            df[revenue_definition["quantity_column"]],
            errors="coerce"
        )

        price = pd.to_numeric(
            df[revenue_definition["price_column"]],
            errors="coerce"
        )

        discount = pd.to_numeric(
            df[revenue_definition["discount_column"]],
            errors="coerce"
        )

        if discount.max() > 1:
            discount = discount / 100

        return quantity * price * (1 - discount)

    else:
        raise ValueError(
            f"Unsupported revenue definition: {definition_type}"
        )


def get_total_revenue(df, revenue_definition):
    revenue = _get_revenue(
        df,
        revenue_definition
    )

    return float(
        revenue.sum(skipna=True)
    )


def get_monthly_sales(
    df,
    date_column,
    revenue_definition
):
    data = df.copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce"
    )

    data["_revenue"] = _get_revenue(
        data,
        revenue_definition
    )

    data = data.dropna(
        subset=[date_column]
    )

    result = (
        data
        .groupby(
            data[date_column].dt.to_period("M")
        )["_revenue"]
        .sum()
        .reset_index()
    )

    result[date_column] = (
        result[date_column]
        .astype(str)
    )

    result = result.rename(
        columns={
            "_revenue": "revenue"
        }
    )

    monthly_sales = result.to_dict(
        orient="records"
    )

    # Python/Pandas determines both rankings.
    strongest_row = result.loc[
        result["revenue"].idxmax()
    ]

    weakest_row = result.loc[
        result["revenue"].idxmin()
    ]

    strongest_month = {
        "month": strongest_row[date_column],
        "revenue": float(
            strongest_row["revenue"]
        )
    }

    weakest_month = {
        "month": weakest_row[date_column],
        "revenue": float(
            weakest_row["revenue"]
        )
    }

    return {
        "monthly_sales": monthly_sales,

        "strongest_month": strongest_month,

        "weakest_month": weakest_month
    }


def get_top_products(
    df,
    product_column,
    revenue_definition,
    top_n=5
):
    data = df.copy()

    data["_revenue"] = _get_revenue(
        data,
        revenue_definition
    )

    try:
        top_n = int(top_n)
    except (TypeError, ValueError):
        top_n = 5

    top_n = max(
        1,
        top_n
    )

    result = (
        data
        .groupby(product_column)["_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )

    result = result.rename(
        columns={
            "_revenue": "revenue"
        }
    )

    return result.to_dict(
        orient="records"
    )


def get_customer_statistics(
    df,
    customer_column,
    revenue_definition
):
    data = df.copy()

    data["_revenue"] = _get_revenue(
        data,
        revenue_definition
    )

    result = (
        data
        .groupby(customer_column)["_revenue"]
        .agg(
            transactions="count",
            total_revenue="sum",
            average_revenue="mean"
        )
        .reset_index()
    )

    return result.to_dict(
        orient="records"
    )


def compare_periods(
    df,
    date_column,
    revenue_definition,
    period1,
    period2
):
    data = df.copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce"
    )

    data["_revenue"] = _get_revenue(
        data,
        revenue_definition
    )

    data = data.dropna(
        subset=[date_column]
    )

    data["_period"] = (
        data[date_column]
        .dt.to_period("M")
        .astype(str)
    )

    revenue1 = data.loc[
        data["_period"] == period1,
        "_revenue"
    ].sum()

    revenue2 = data.loc[
        data["_period"] == period2,
        "_revenue"
    ].sum()

    change = revenue2 - revenue1

    if revenue1 != 0:
        percentage_change = (
            change / revenue1
        ) * 100
    else:
        percentage_change = None

    return {
        "period1": period1,
        "period2": period2,
        "period1_revenue": float(revenue1),
        "period2_revenue": float(revenue2),
        "change": float(change),
        "percentage_change": (
            float(percentage_change)
            if percentage_change is not None
            else None
        )
    }