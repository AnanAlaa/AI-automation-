from backend.data_loader import load_csv
from backend.analyst import BusinessAnalyst


df = load_csv(
    "data/business_performance_test_v2.csv"
)

analyst = BusinessAnalyst()
analyst.load_data(df)


questions = [

    """
    Give me a detailed business performance analysis using the dataset.
    Determine the total revenue, identify the top 3 products by revenue,
    analyze revenue and transaction performance across customer segments,
    identify the strongest and weakest sales months, and compare January
    2025 with February 2025 to determine whether revenue increased or
    decreased and by how much. Use all relevant analysis tools and base
    every numerical result strictly on Python/Pandas calculations.
    """,

    """
    I want a management-level performance review of this business.
    Find the overall revenue, rank the top 5 offerings by revenue,
    determine which client segment generated the highest total revenue
    and which client segment had the highest average revenue per
    transaction, identify the best and worst months by revenue, and
    compare January 2025 against February 2025. Explain the findings
    clearly and combine the results from all relevant analysis tools
    into one coherent answer. Use the dataset itself to determine the
    correct columns and calculations.
    """
]


for i, question in enumerate(questions, start=1):

    print("\n" + "=" * 70)
    print(f"TEST {i}")
    print("=" * 70)

    print("\nQuestion:")
    print(question)

    try:
        answer = analyst.ask(question)

        print("\nAnswer:")
        print(answer)

    except Exception as e:

        print("\nERROR:")
        print(e)