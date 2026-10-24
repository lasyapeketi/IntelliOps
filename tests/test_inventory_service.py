
from modules.inventory_optimization.service import optimize_inventory
def main():
    product_id = "85123A"
    try:
        result = optimize_inventory(
            product_id=product_id,
            current_stock=100,
            lead_time_days=5,
            review_period_days=7,
            safety_stock_days=3
        )
        print("\nINVENTORY OPTIMIZATION RESULT")
        print("-" * 35)
        for key, value in result.items():
            print(f"{key}: {value}")
    except Exception as e:
        print(f"Error: {e}")
if __name__ == "__main__":
    main()
