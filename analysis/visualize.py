import calendar
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.join(BASE, "visualizations")
os.makedirs(out_dir, exist_ok=True)

orders = pd.read_csv(os.path.join(BASE, "data", "orders.csv"))
customers = pd.read_csv(os.path.join(BASE, "data", "customers.csv"))
products = pd.read_csv(os.path.join(BASE, "data", "products.csv"))

orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
natural_key = ["customer_id", "product_id", "order_date", "quantity", "discount_pct", "payment_method", "rating", "returned"]
orders = orders[~orders.duplicated(subset=natural_key, keep="first")].reset_index(drop=True)
orders["discount_pct"] = orders["discount_pct"].fillna(0)
orders["rating"] = orders["rating"].fillna(orders["rating"].median())

merged = orders.merge(products, on="product_id").merge(customers, on="customer_id")
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)

q1 = merged["quantity"].quantile(0.25)
q3 = merged["quantity"].quantile(0.75)
iqr = q3 - q1
merged["is_outlier"] = (merged["quantity"] < q1 - 1.5 * iqr) | (merged["quantity"] > q3 + 1.5 * iqr)
merged["year_month"] = pd.to_datetime(merged["order_date"]).dt.strftime("%Y-%m")

rates = (merged.groupby("payment_method")["returned"].mean() * 100).round(1).sort_values(ascending=False)
top_method = rates.index[0]
lowest_rate = rates.min()

plt.figure(figsize=(8, 5))
colors = ["tab:red" if m == top_method else "tab:blue" for m in rates.index]
bars = plt.bar(rates.index, rates.values, color=colors)
for bar, value in zip(bars, rates.values):
    plt.text(bar.get_x() + bar.get_width() / 2, value + 0.8, f"{value:.1f}%", ha="center", fontweight="bold")
plt.title(f"{top_method} Returns at {rates.iloc[0]:.1f}% - {rates.iloc[0] / lowest_rate:.0f}x the Lowest ({rates.index[-1]})")
plt.xlabel("Payment method")
plt.ylabel("Return rate (%)")
plt.ylim(0, rates.max() * 1.2)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "return_rate_by_payment.png"), dpi=150)
plt.close()

monthly = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
peak_month = monthly.idxmax()
peak_name = calendar.month_name[int(peak_month[-2:])]

plt.figure(figsize=(9, 5))
plt.plot(monthly.index, monthly.values, marker="o", color="tab:blue")
plt.scatter([peak_month], [monthly[peak_month]], color="tab:red", s=120, zorder=3)
values = list(monthly.values)
for i, (month, value) in enumerate(monthly.items()):
    is_dip = 0 < i < len(values) - 1 and value < values[i - 1] and value < values[i + 1]
    if is_dip:
        plt.text(month, value - 900, f"{value:,.0f}", ha="center")
    else:
        plt.text(month, value + 500, f"{value:,.0f}", ha="center")
plt.title(f"Outlier-Corrected Monthly Revenue - Peak Month: {peak_name} ({peak_month})")
plt.xlabel("Month")
plt.ylabel("Revenue (Rs.)")
plt.ylim(0, monthly.max() * 1.15)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "monthly_revenue_trend.png"), dpi=150)
plt.close()

print("saved", os.path.join(out_dir, "return_rate_by_payment.png"))
print("saved", os.path.join(out_dir, "monthly_revenue_trend.png"))
