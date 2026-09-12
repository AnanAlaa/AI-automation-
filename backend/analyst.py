import json

from backend.schema_analyzer import analyze_schema
from backend.ollama_client import ask_qwen

from backend.analysis_tools import (
    get_total_revenue,
    get_monthly_sales,
    get_top_products,
    get_customer_statistics,
    compare_periods,
)


class BusinessAnalyst:

    def __init__(self):
        self.df = None
        self.schema = None

    def load_data(self, df):
        self.df = df
        self.schema = analyze_schema(df)

    def ask(self, question):

        if self.df is None:
            raise ValueError(
                "No dataset has been loaded."
            )

        # ==========================================================
        # STEP 1: QWEN UNDERSTANDS THE QUESTION
        # ==========================================================

        planning_prompt = f"""
You are an AI Business Analyst.

You are given a dataset schema and a user's business question.

Your job is to understand the BUSINESS MEANING of the question
and create a Python tool execution plan.

You are the reasoning and decision-making layer.

Python/Pandas will perform ALL actual calculations.

Do NOT calculate numerical results yourself.


==========================================================
DATASET SCHEMA
==========================================================

{json.dumps(
    self.schema,
    indent=2,
    default=str
)}


==========================================================
USER QUESTION
==========================================================

{question}


==========================================================
AVAILABLE TOOLS
==========================================================

You may ONLY use these five tools:

1. get_total_revenue
2. get_monthly_sales
3. get_top_products
4. get_customer_statistics
5. compare_periods


==========================================================
REVENUE DEFINITION
==========================================================

Choose ONE revenue definition for the ENTIRE plan.

All tools in this question must use the SAME revenue definition.

If a direct revenue/sales column exists, USE IT.

If both gross and net revenue exist and the user simply says
"revenue" or "sales", prefer NET revenue.

A revenue column must NEVER be multiplied by another column.


==========================================================
DIRECT REVENUE
==========================================================

Use:

{{
    "type": "column",
    "column": "EXACT_COLUMN_NAME"
}}

when a suitable direct revenue column exists.


==========================================================
DERIVED REVENUE
==========================================================

ONLY use derived revenue when there is no suitable direct
revenue/sales column.

Quantity × Price:

{{
    "type": "multiply",
    "quantity_column": "EXACT_QUANTITY_COLUMN",
    "price_column": "EXACT_PRICE_COLUMN"
}}

Quantity × Price × (1 - Discount):

{{
    "type": "multiply_discount",
    "quantity_column": "EXACT_QUANTITY_COLUMN",
    "price_column": "EXACT_PRICE_COLUMN",
    "discount_column": "EXACT_DISCOUNT_COLUMN"
}}


==========================================================
SEMANTIC COLUMN MAPPING
==========================================================

Do NOT assume fixed column names.

Understand the meaning of columns using:

- column names
- data types
- sample values
- unique values

Possible date columns:

Date
Order_Date
Transaction_Date
Purchase_Date

Possible product columns:

Product
Product_Name
Product_Line
Item
Item_Name

Possible customer columns:

Customer
Customer_ID
Client
Client_ID
Customer_Type
Customer_Segment

Possible quantity columns:

Quantity
Qty
Units
Units_Sold
Quantity_Sold

Possible price columns:

Price
Unit_Price
Selling_Price
Unit_Price_USD


==========================================================
TOP PRODUCTS
==========================================================

If user says:

top 3 → top_n = 3
top 5 → top_n = 5
top 10 → top_n = 10

If no number is specified:

top_n = 5


==========================================================
COMPARE PERIODS
==========================================================

compare_periods works with MONTHLY periods.

Use YYYY-MM.

January 2025 → 2025-01
February 2025 → 2025-02


==========================================================
MULTI-TOOL QUESTIONS
==========================================================

A question can require multiple tools.

Use ALL relevant tools needed to answer the complete question.

Do not limit the plan to one tool.

Example:

"What is total revenue, what are the top 3 products,
which customer segment generates the most revenue,
and which month was strongest?"

Use:

get_total_revenue
get_top_products
get_customer_statistics
get_monthly_sales


==========================================================
TOOL PARAMETERS
==========================================================

get_total_revenue:

{{
    "function": "get_total_revenue",
    "parameters": {{}}
}}


get_monthly_sales:

{{
    "function": "get_monthly_sales",
    "parameters": {{
        "date_column": "EXACT_DATE_COLUMN"
    }}
}}


get_top_products:

{{
    "function": "get_top_products",
    "parameters": {{
        "product_column": "EXACT_PRODUCT_COLUMN",
        "top_n": 5
    }}
}}


get_customer_statistics:

{{
    "function": "get_customer_statistics",
    "parameters": {{
        "customer_column": "EXACT_CUSTOMER_COLUMN"
    }}
}}


compare_periods:

{{
    "function": "compare_periods",
    "parameters": {{
        "date_column": "EXACT_DATE_COLUMN",
        "period1": "YYYY-MM",
        "period2": "YYYY-MM"
    }}
}}


==========================================================
OUTPUT FORMAT
==========================================================

Return ONLY valid JSON.

No markdown.
No ```json.
No explanation.

Use exactly:

{{
    "revenue_definition": {{
        "type": "column",
        "column": "EXACT_COLUMN_NAME"
    }},

    "tools": [
        {{
            "function": "get_total_revenue",
            "parameters": {{}}
        }}
    ]
}}

The revenue_definition MUST appear ONCE at the top level.

Do NOT put revenue_definition inside individual tools.
"""

        planning_response = ask_qwen(
            planning_prompt
        )

        clean_response = (
            planning_response.strip()
        )

        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]

        elif clean_response.startswith("```"):
            clean_response = clean_response[3:]

        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]

        clean_response = clean_response.strip()

        # ==========================================================
        # PARSE QWEN PLAN
        # ==========================================================

        try:
            plan = json.loads(
                clean_response
            )

        except json.JSONDecodeError:
            raise ValueError(
                "Qwen returned invalid JSON:\n"
                + planning_response
            )

        tools = plan.get("tools")

        if not isinstance(tools, list) or not tools:
            raise ValueError(
                "Qwen did not return any tools."
            )

        revenue_definition = (
            plan.get("revenue_definition")
        )

        if not isinstance(
            revenue_definition,
            dict
        ):
            raise ValueError(
                "Qwen did not return a revenue definition."
            )

        # ==========================================================
        # BASIC VALIDATION
        # ==========================================================

        allowed_functions = {
            "get_total_revenue",
            "get_monthly_sales",
            "get_top_products",
            "get_customer_statistics",
            "compare_periods",
        }

        valid_columns = set(
            self.df.columns
        )

        revenue_type = (
            revenue_definition.get("type")
        )

        if revenue_type == "column":

            column = revenue_definition.get(
                "column"
            )

            if column not in valid_columns:
                raise ValueError(
                    f"Invalid revenue column selected by Qwen: {column}"
                )

        elif revenue_type == "multiply":

            quantity_column = (
                revenue_definition.get(
                    "quantity_column"
                )
            )

            price_column = (
                revenue_definition.get(
                    "price_column"
                )
            )

            if quantity_column not in valid_columns:
                raise ValueError(
                    f"Invalid quantity column selected by Qwen: {quantity_column}"
                )

            if price_column not in valid_columns:
                raise ValueError(
                    f"Invalid price column selected by Qwen: {price_column}"
                )

        elif revenue_type == "multiply_discount":

            required = [
                "quantity_column",
                "price_column",
                "discount_column"
            ]

            for key in required:

                column = (
                    revenue_definition.get(key)
                )

                if column not in valid_columns:
                    raise ValueError(
                        f"Invalid column selected by Qwen: {column}"
                    )

        else:

            raise ValueError(
                f"Unsupported revenue definition: {revenue_type}"
            )

        # ==========================================================
        # STEP 2: EXECUTE PYTHON TOOLS
        # ==========================================================

        results = []

        for tool in tools:

            function_name = (
                tool.get("function")
            )

            parameters = (
                tool.get(
                    "parameters",
                    {}
                )
            )

            if function_name not in allowed_functions:
                raise ValueError(
                    f"Unknown function selected by Qwen: {function_name}"
                )

            if function_name == "get_total_revenue":

                result = get_total_revenue(
                    self.df,
                    revenue_definition
                )

            elif function_name == "get_monthly_sales":

                date_column = (
                    parameters.get(
                        "date_column"
                    )
                )

                if date_column not in valid_columns:
                    raise ValueError(
                        f"Invalid date column: {date_column}"
                    )

                result = get_monthly_sales(
                    self.df,
                    date_column,
                    revenue_definition
                )

            elif function_name == "get_top_products":

                product_column = (
                    parameters.get(
                        "product_column"
                    )
                )

                top_n = (
                    parameters.get(
                        "top_n",
                        5
                    )
                )

                if product_column not in valid_columns:
                    raise ValueError(
                        f"Invalid product column: {product_column}"
                    )

                result = get_top_products(
                    self.df,
                    product_column,
                    revenue_definition,
                    top_n
                )

            elif function_name == "get_customer_statistics":

                customer_column = (
                    parameters.get(
                        "customer_column"
                    )
                )

                if customer_column not in valid_columns:
                    raise ValueError(
                        f"Invalid customer column: {customer_column}"
                    )

                result = get_customer_statistics(
                    self.df,
                    customer_column,
                    revenue_definition
                )

            elif function_name == "compare_periods":

                date_column = (
                    parameters.get(
                        "date_column"
                    )
                )

                period1 = (
                    parameters.get(
                        "period1"
                    )
                )

                period2 = (
                    parameters.get(
                        "period2"
                    )
                )

                if date_column not in valid_columns:
                    raise ValueError(
                        f"Invalid date column: {date_column}"
                    )

                result = compare_periods(
                    self.df,
                    date_column,
                    revenue_definition,
                    period1,
                    period2
                )

            results.append({
                "function": function_name,
                "result": result
            })

        # ==========================================================
        # STEP 3: QWEN INTERPRETS PYTHON RESULTS
        # ==========================================================

        final_prompt = f"""
You are an AI Business Analyst.

The user asked:

{question}


Python/Pandas executed the required business analyses.

The results are:

{json.dumps(
    results,
    indent=2,
    default=str
)}


==========================================================
YOUR TASK
==========================================================

Give ONE clear, coherent answer to the user's original question.

Answer EVERY part of the question.

Combine the results from all relevant tools naturally.


==========================================================
ABSOLUTE SOURCE OF TRUTH
==========================================================

Python/Pandas results are the ONLY source of truth.

You MUST NOT:

- invent numbers
- change numbers
- recalculate numbers
- estimate numbers
- reinterpret numerical results
- substitute one value for another


==========================================================
NAMES
==========================================================

Preserve product names EXACTLY as returned by Python.

Preserve customer names EXACTLY as returned by Python.

Preserve dates EXACTLY as returned by Python.

NEVER:

- shorten a product name
- abbreviate a product name
- modify capitalization
- replace a name with a similar name


==========================================================
STRONGEST AND WEAKEST MONTH
==========================================================

Python/Pandas has already determined these values.

If the results contain:

"strongest_month"

use it EXACTLY.

If the results contain:

"weakest_month"

use it EXACTLY.

DO NOT calculate strongest or weakest month yourself.

DO NOT choose another month.

DO NOT infer these values from memory.

The strongest month is exactly the month and revenue
inside "strongest_month".

The weakest month is exactly the month and revenue
inside "weakest_month".


==========================================================
CUSTOMER SEGMENTS
==========================================================

Keep these metrics separate:

- transactions
- total_revenue
- average_revenue

Do NOT confuse total revenue with average revenue.

If identifying the customer segment with the highest
total revenue, use the largest total_revenue.

If identifying the customer segment with the highest
average revenue per transaction, use the largest
average_revenue.

Do NOT claim that one segment has the highest value
unless the Python results actually show that.


==========================================================
PRODUCT RANKINGS
==========================================================

Use the exact ranking returned by Python.

Do NOT change the order.

Do NOT shorten product names.

Do NOT calculate a different ranking.


==========================================================
PERCENTAGES AND CALCULATIONS
==========================================================

Do NOT perform new calculations.

Only report percentages or derived metrics if they are
already present in the Python results.

If a percentage is not present in the Python results,
do not invent one.


==========================================================
TRENDS
==========================================================

Do not describe a general trend unless the Python results
actually support it.

A comparison between two months only supports a comparison
between those two months.

Do NOT call the entire business trend "increasing" or
"decreasing" based only on two months.

Do not use words such as:

- slight
- significant
- dramatic
- strong
- weak

unless clearly supported by the calculated results.


==========================================================
BUSINESS DIAGNOSIS
==========================================================

You may provide business insights ONLY when they are directly
supported by the Python results.

For example, you may identify:

- the highest revenue product
- the highest revenue customer segment
- the highest average transaction segment
- the strongest month
- the weakest month
- an increase or decrease between two compared periods

But do NOT invent reasons such as:

- promotions
- seasonality
- marketing campaigns
- customer behavior
- market conditions

unless such information is actually present in the results.


==========================================================
FINAL ANSWER
==========================================================

Use the Python results exactly.

Do not hallucinate.

Do not recalculate.

Do not modify names.

Do not change rankings.

Do not confuse values.

Return ONLY the final answer.
"""

        final_answer = ask_qwen(
            final_prompt
        )

        return final_answer