import calendar
import json
import os

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def month_name(month_text):
    return calendar.month_name[int(month_text.split("-")[1])]


def build_prompt(findings):
    rates = findings["return_rate_by_payment"]
    risk = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]
    return (
        "Write the Situation, Complication and Resolution narrative from these verified findings.\n\n"
        f"Cleaned total revenue: Rs.{findings['cleaned_total_revenue_inr']:,.2f}\n"
        f"Raw total revenue before cleaning: Rs.{findings['raw_total_revenue_inr']:,.2f}\n"
        f"Gap caused by duplicate orders: Rs.{findings['duplicate_reconciliation_delta_inr']:,.2f}\n"
        f"Return rate by payment method: COD {rates['COD']}%, CARD {rates['CARD']}%, UPI {rates['UPI']}%\n"
        f"Highest-risk segment: {risk['payment_method']} orders in Tier-{risk['city_tier']} cities at {risk['return_rate_pct']}%\n"
        f"True peak month: {month_name(peak['month'])} ({peak['month']}) with Rs.{peak['revenue_inr']:,.2f}\n"
        f"Outlier-inflated month: {month_name(inflated['month'])} ({inflated['month']}) looked like Rs.{inflated['apparent_revenue_inr']:,.2f} "
        f"but is really Rs.{inflated['corrected_revenue_inr']:,.2f} after removing the bulk-order outliers\n\n"
        f"The same findings as JSON:\n{json.dumps(findings, indent=2)}"
    )


def generate_scr_narrative_offline(findings):
    try:
        rates = findings["return_rate_by_payment"]
        risk = findings["highest_risk_segment"]
        peak = findings["true_peak_month"]
        inflated = findings["outlier_inflated_month"]
        narrative = (
            "Situation\n"
            f"After cleaning the order data, total revenue is Rs.{findings['cleaned_total_revenue_inr']:,.2f}. "
            f"The raw data showed Rs.{findings['raw_total_revenue_inr']:,.2f}, and the Rs.{findings['duplicate_reconciliation_delta_inr']:,.2f} "
            "gap is entirely the duplicate double-submitted orders that were removed.\n\n"
            "Complication\n"
            f"Returns are not spread evenly. COD orders are returned at {rates['COD']}%, against {rates['CARD']}% for CARD "
            f"and {rates['UPI']}% for UPI. The worst segment is {risk['payment_method']} orders in Tier-{risk['city_tier']} cities, "
            f"where the return rate reaches {risk['return_rate_pct']}%. Revenue also gave a false signal: "
            f"{month_name(inflated['month'])} looked like the best month at Rs.{inflated['apparent_revenue_inr']:,.2f}, "
            f"but two bulk orders inflated it and its corrected revenue is Rs.{inflated['corrected_revenue_inr']:,.2f}.\n\n"
            "Resolution\n"
            f"The real peak month is {month_name(peak['month'])} with Rs.{peak['revenue_inr']:,.2f}, so growth planning should "
            f"learn from {month_name(peak['month'])} and not from {month_name(inflated['month'])}. Ops and finance should target "
            f"{risk['payment_method']} orders in Tier-{risk['city_tier']} cities first, for example with address confirmation "
            "or a prepaid incentive, instead of changing payment policy everywhere."
        )
        return {"status": "success", "narrative": narrative, "tokens": None}
    except Exception as err:
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative(findings, use_fallback=True):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        result = {"status": "error", "narrative": None, "message": "GEMINI_API_KEY is not set"}
    else:
        try:
            if genai is None:
                raise ImportError("google-genai is not installed")

            system_instruction = (
                "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
                "Write about 250 words in exactly three labeled sections: Situation, Complication, Resolution. "
                "Every number in your answer must come from the findings you are given and must appear with the "
                "same value. Do not invent, estimate or recalculate any statistic. Name the peak month in words."
            )

            # temperature 0.0: this is a factual business report, not creative writing,
            # so the same findings should give the same narrative every time
            config_args = {
                "system_instruction": system_instruction,
                "temperature": 0.0,
                "max_output_tokens": 2048,
                "http_options": types.HttpOptions(timeout=30000),
            }
            if "2.5" in MODEL and "pro" not in MODEL:
                config_args["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=MODEL,
                contents=build_prompt(findings),
                config=types.GenerateContentConfig(**config_args),
            )

            text = response.text
            if not text:
                raise ValueError("Gemini returned an empty response")
            if not all(label in text for label in ("Situation", "Complication", "Resolution")):
                raise ValueError("Gemini response is missing one of the three sections")

            tokens = response.usage_metadata.total_token_count if response.usage_metadata else None
            print("Gemini narrative generated with", MODEL, "- tokens used:", tokens)
            result = {"status": "success", "narrative": text, "tokens": tokens}
        except Exception as err:
            result = {"status": "error", "narrative": None, "message": str(err)}

    if result["status"] == "error" and use_fallback:
        print("Gemini path not used:", result["message"])
        print("Falling back to the offline template.")
        return generate_scr_narrative_offline(findings)
    return result


def check_numbers(narrative, findings):
    text = narrative.replace(",", "")
    peak = findings["true_peak_month"]
    cleaned = findings["cleaned_total_revenue_inr"]
    delta = findings["duplicate_reconciliation_delta_inr"]
    checks = [
        (f"cleaned total revenue {cleaned:,.2f}", f"{cleaned:.2f}" in text or f"{cleaned:g}" in text),
        (f"COD return rate {findings['return_rate_by_payment']['COD']}", str(findings["return_rate_by_payment"]["COD"]) in text),
        (f"highest-risk segment rate {findings['highest_risk_segment']['return_rate_pct']}", str(findings["highest_risk_segment"]["return_rate_pct"]) in text),
        (f"duplicate delta {delta:,.2f}", f"{delta:.2f}" in text or f"{delta:g}" in text),
        (
            f"peak month {month_name(peak['month'])} with {peak['revenue_inr']:,.2f}",
            month_name(peak["month"]).lower() in text.lower()
            and (f"{peak['revenue_inr']:.2f}" in text or f"{peak['revenue_inr']:g}" in text),
        ),
    ]
    for label, ok in checks:
        print("PASS" if ok else "FAIL", "-", label)
    assert all(ok for _, ok in checks), "the narrative is missing at least one required figure"
    return True


if __name__ == "__main__":
    with open(os.path.join(HERE, "findings.json"), encoding="utf-8") as f:
        findings = json.load(f)

    result = generate_scr_narrative(findings)
    print()
    print(result["narrative"])

    sample_path = os.path.join(HERE, "sample_output.txt")
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(result["narrative"] + "\n")
    print("\nsaved", sample_path)

    print("\nChecking the saved sample_output.txt:")
    with open(sample_path, encoding="utf-8") as f:
        check_numbers(f.read(), findings)
    print("All five figures are present.")
