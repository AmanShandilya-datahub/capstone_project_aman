import calendar
import json
import os
from itertools import combinations

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("TASK 1: LOAD AND INSPECT")
orders = pd.read_csv(os.path.join(BASE, "data", "orders.csv"))
customers = pd.read_csv(os.path.join(BASE, "data", "customers.csv"))
products = pd.read_csv(os.path.join(BASE, "data", "products.csv"))
print("orders.shape:", orders.shape)
print("customers.shape:", customers.shape)
print("products.shape:", products.shape)
print(orders.head())
print(orders.isnull().sum())

raw_merged = orders.merge(products, on="product_id")
raw_merged["order_value"] = raw_merged["quantity"] * raw_merged["price"] * (1 - raw_merged["discount_pct"].fillna(0) / 100)
raw_total = round(raw_merged["order_value"].sum(), 2)
print("Raw revenue over all", len(raw_merged), "rows (same formula as Part 1 report a):", f"{raw_total:.2f}")

print("\nTASK 2: STANDARDISE PAYMENT METHOD CASING")
print("distinct values before:", orders["payment_method"].nunique(), orders["payment_method"].unique().tolist())
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
print("distinct values after:", orders["payment_method"].nunique(), orders["payment_method"].unique().tolist())
print(orders["payment_method"].value_counts())

print("\nTASK 3: REMOVE DUPLICATE ORDERS")
natural_key = ["customer_id", "product_id", "order_date", "quantity", "discount_pct", "payment_method", "rating", "returned"]
is_duplicate = orders.duplicated(subset=natural_key, keep="first")
dropped = orders[is_duplicate]
print("duplicate rows flagged:", int(is_duplicate.sum()))
print("dropped order_ids:", dropped["order_id"].tolist())
orders_clean = orders[~is_duplicate].reset_index(drop=True)
print("orders_clean.shape:", orders_clean.shape)

print("\nTASK 4: IMPUTE MISSING VALUES")
print("missing discount_pct rows:", int(orders_clean["discount_pct"].isnull().sum()))
print("missing rating rows:", int(orders_clean["rating"].isnull().sum()))
median_rating = orders_clean["rating"].median()
print("median of non-null ratings (before imputing):", median_rating)
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(median_rating)
print("nulls after imputing:", orders_clean[["discount_pct", "rating"]].isnull().sum().to_dict())

print("\nTASK 5: MERGE AND RECONCILE AGAINST PART 1")
merged = orders_clean.merge(products, on="product_id").merge(customers, on="customer_id")
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
clean_total = round(merged["order_value"].sum(), 2)
print("merged.shape:", merged.shape)
print("Total order_value across the", len(merged), "cleaned rows:", f"{clean_total:.2f}")

dropped_values = dropped.merge(products, on="product_id")
dropped_values["order_value"] = dropped_values["quantity"] * dropped_values["price"] * (1 - dropped_values["discount_pct"].fillna(0) / 100)
dropped_total = round(dropped_values["order_value"].sum(), 2)
difference = round(raw_total - clean_total, 2)
print("order_value of each dropped row:")
print(dropped_values[["order_id", "order_value"]].to_string(index=False))
print("sum of the dropped rows:", f"{dropped_total:.2f}")
print("difference equals the dropped rows:", difference == dropped_total)

print(
    "\nRECONCILIATION NOTE: Part 1 report (a) gives a raw total of Rs." + f"{raw_total:,.2f}" +
    " over all " + str(len(raw_merged)) + " orders, while the cleaned total here is Rs." + f"{clean_total:,.2f}" +
    " over " + str(len(merged)) + " orders, so the cleaned figure is lower by Rs." + f"{difference:,.2f}" +
    ". That whole difference comes from the " + str(len(dropped)) + " double-submitted duplicate orders (" +
    ", ".join(dropped["order_id"]) + ") removed in Task 3: summed on their own with the same order_value formula, " +
    "those rows come to Rs." + f"{dropped_total:,.2f}" + ", which matches the difference exactly. " +
    "The imputation in Task 4 plays no part in it: a missing discount only becomes 0, which is what the " +
    "revenue formula already did with a NULL discount in Part 1, and the rating is never used in order_value."
)

print("\nTASK 6: IQR OUTLIERS ON QUANTITY")
q1 = merged["quantity"].quantile(0.25)
q3 = merged["quantity"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
print(f"Q1 = {q1}, Q3 = {q3}, IQR = {iqr}, lower = {lower}, upper = {upper}")
merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
outliers = merged[merged["is_outlier"]]
print("outlier rows flagged:", len(outliers))
print(outliers[["order_id", "order_date", "quantity"]].to_string(index=False))
print("rows still in merged (flagged, not dropped):", len(merged))

print("\nTASK 7: DOES COD HAVE A HIGHER RETURN RATE?")
print("Hypothesis: COD orders have a higher return rate than Card and UPI orders.")
by_payment = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
by_payment["return_rate_pct"] = (by_payment["mean"] * 100).round(1)
print(by_payment)
verdict = "Confirmed" if by_payment["mean"].idxmax() == "COD" else "Not confirmed"
print("Hypothesis verdict:", verdict)

print("\nTASK 8: PAYMENT METHOD x CITY TIER")
segments = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
segments["return_rate_pct"] = (segments["mean"] * 100).round(1)
print(segments)
for tier in sorted(merged["city_tier"].unique()):
    n = int(segments.loc[("COD", tier), "count"])
    rate = segments.loc[("COD", tier), "return_rate_pct"]
    print(f"COD + Tier-{tier}: {n} orders, return rate {rate}%")
risk_method, risk_tier = segments["mean"].idxmax()
risk_rate = segments.loc[(risk_method, risk_tier), "return_rate_pct"]
print(f"Highest-risk segment: {risk_method} + Tier-{risk_tier} cities at {risk_rate}%")
print("COD risk is not the same in every tier, so the blended COD rate hides where the problem is concentrated.")

print("\nTASK 9: CORRELATION ANALYSIS")
corr_cols = ["rating", "returned", "discount_pct", "quantity"]
corr = merged[corr_cols].corr()
print(corr.round(3))


def band(r):
    r = abs(r)
    if r < 0.2:
        return "negligible"
    if r < 0.4:
        return "weak"
    if r < 0.7:
        return "moderate"
    return "strong"


bands = {}
for a, b in combinations(corr_cols, 2):
    bands[(a, b)] = band(corr.loc[a, b])
    print(f"{a} vs {b}: r = {corr.loc[a, b]:.3f} -> {bands[(a, b)]}")
r_discount = corr.loc["discount_pct", "returned"]
discount_verdict = "Confirmed" if (r_discount < 0 and band(r_discount) != "negligible") else "Busted"
print(f"Hypothesis 'higher discounts reduce returns': r = {r_discount:.3f} ({band(r_discount)}) -> {discount_verdict}")

print("\nTASK 10: OUTLIER-CORRECTED MONTHLY REVENUE")
merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.strftime("%Y-%m")
monthly_with = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_without = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
print("Monthly revenue INCLUDING the outlier orders:")
print(monthly_with.map("{:.2f}".format).to_string())
print("Monthly revenue EXCLUDING the outlier orders:")
print(monthly_without.map("{:.2f}".format).to_string())

apparent_month = monthly_with.idxmax()
true_month = monthly_without.idxmax()
true_month_name = calendar.month_name[int(true_month[-2:])]
outlier_rows = merged[merged["is_outlier"]]
outlier_text = ", ".join(f"{row.order_id} on {row.order_date.date()}" for row in outlier_rows.itertuples())
print(
    f"{apparent_month} looks like the best month only because the bulk orders ({outlier_text}) landed in it: "
    f"it falls from Rs.{monthly_with[apparent_month]:,.2f} to Rs.{monthly_without[apparent_month]:,.2f} without them. "
    f"Once they are excluded, {true_month_name} ({true_month}) is the genuine peak month at Rs.{monthly_without[true_month]:,.2f}."
)

print("\nSELF-CHECK AGAINST THE BRIEF")
expected_months = {"2026-01": 11637.10, "2026-02": 13195.50, "2026-03": 20318.90, "2026-04": 9495.30, "2026-05": 13151.10, "2026-06": 11615.40}
self_checks = [
    ("raw orders shape (180, 9)", orders.shape == (180, 9)),
    ("raw revenue 99860.20", raw_total == 99860.20),
    ("payment counts CARD 70 / UPI 55 / COD 55", orders["payment_method"].value_counts().to_dict() == {"CARD": 70, "UPI": 55, "COD": 55}),
    ("dropped ids O0176-O0180", dropped["order_id"].tolist() == ["O0176", "O0177", "O0178", "O0179", "O0180"]),
    ("orders_clean shape (175, 9)", orders_clean.shape == (175, 9)),
    ("median rating 3.0", median_rating == 3.0),
    ("cleaned revenue 97358.30", clean_total == 97358.30),
    ("difference 2501.90", difference == 2501.90 == dropped_total),
    ("IQR values 1.0 / 2.0 / 1.0 / -0.5 / 3.5", (q1, q3, iqr, lower, upper) == (1.0, 2.0, 1.0, -0.5, 3.5)),
    ("outliers O0011 and O0098", sorted(outliers["order_id"]) == ["O0011", "O0098"]),
    ("return rates CARD 14.7 / COD 44.4 / UPI 18.9", by_payment["return_rate_pct"].to_dict() == {"CARD": 14.7, "COD": 44.4, "UPI": 18.9}),
    ("highest-risk segment COD Tier-2 at 54.5", (risk_method, risk_tier, risk_rate) == ("COD", 2, 54.5)),
    ("all six correlation pairs negligible", len(bands) == 6 and set(bands.values()) == {"negligible"}),
    ("discount vs returned about -0.09", round(r_discount, 2) == -0.09),
    ("January with outliers 29582.10 (apparent peak)", monthly_with["2026-01"] == 29582.10 and apparent_month == "2026-01"),
    ("corrected monthly series", monthly_without.to_dict() == expected_months),
    ("true peak month is March", true_month == "2026-03"),
]
for label, ok in self_checks:
    print("PASS" if ok else "FAIL", "-", label)
print("ALL CHECKS PASSED" if all(ok for _, ok in self_checks) else "SOME CHECKS FAILED")

print("\nEXPORT: narrator/findings.json")
findings = {
    "cleaned_total_revenue_inr": float(clean_total),
    "raw_total_revenue_inr": float(raw_total),
    "duplicate_reconciliation_delta_inr": float(difference),
    "return_rate_by_payment": {m: float(by_payment.loc[m, "return_rate_pct"]) for m in ["COD", "CARD", "UPI"]},
    "highest_risk_segment": {
        "payment_method": str(risk_method),
        "city_tier": int(risk_tier),
        "return_rate_pct": float(risk_rate),
    },
    "true_peak_month": {"month": str(true_month), "revenue_inr": float(monthly_without[true_month])},
    "outlier_inflated_month": {
        "month": str(apparent_month),
        "apparent_revenue_inr": float(monthly_with[apparent_month]),
        "corrected_revenue_inr": float(monthly_without[apparent_month]),
    },
}
findings_path = os.path.join(BASE, "narrator", "findings.json")
with open(findings_path, "w", encoding="utf-8") as f:
    json.dump(findings, f, indent=2)
print(json.dumps(findings, indent=2))
print("saved", findings_path)
