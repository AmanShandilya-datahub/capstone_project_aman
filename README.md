# Mamaearth Returns & Growth Intelligence Pipeline

Capstone project - Data Analytics with AI & Gen AI, E&ICT Academy IIT Roorkee.

## About this project

Hi, I'm Aman Shandilya, and this is my capstone project for Data Analytics with AI & Gen AI at E&ICT Academy, IIT Roorkee. I chose to focus on Mamaearth's returns and revenue because I wanted to understand how data cleaning and analysis can help answer real business questions. One thing that stood out to me was how duplicate orders and a few bulk orders could change the revenue figures and even make the wrong month look like the peak. If I were to take this project further, I would look at more order-level details to understand why returns happen and how businesses could reduce them.

## The problem

Mamaearth's growth team suspects that returns are reducing margins on some orders, but the data needs to be analysed properly to understand where the problem comes from. This project looks at two main questions: **where are the returns really coming from**, and **what is the true revenue once the data is cleaned?**

I built the project in three layers. Each layer reports only the numbers it calculates itself or receives from the layer before it.

```
data/*.csv  ->  sql/  ->  analysis/  ->  narrator/
 raw files      load +      clean +       findings.json -> SCR narrative
                report      reconcile
```

1. **SQL layer (`sql/`)** loads the three raw CSVs into SQLite and runs 9 business reports on the raw data. The total revenue of Rs.99,860.20 is the baseline that the Python layer needs to reconcile against.
2. **Python layer (`analysis/`)** cleans the same raw CSVs using pandas, explains why its total differs from the SQL total, identifies return patterns, creates two charts, and writes `narrator/findings.json` at the end of `clean_and_eda.py`.
3. **GenAI layer (`narrator/`)** reads `findings.json` and uses Gemini to write a Situation / Complication / Resolution narrative. If there is no API key or the API call fails, it switches to an offline template, so the project can still run.

## Repo structure

```
README.md
requirements.txt
sql/
  schema.sql          tables: customers, products, orders
  seed_data.sql       re-runnable INSERTs generated from the CSVs (blank cells become NULL)
  reports.sql         9 reports (a-i), exact output pasted above each query
data/
  customers.csv       45 rows  (never edited by hand)
  products.csv        16 rows
  orders.csv          180 rows
analysis/
  clean_and_eda.py    Part 2 tasks 1-10, prints every result, writes narrator/findings.json
  visualize.py        Part 2 task 11, writes the two charts
visualizations/
  return_rate_by_payment.png
  monthly_revenue_trend.png
narrator/
  findings.json       written by clean_and_eda.py, never typed by hand
  generate_narrative.py
  sample_output.txt   the narrative from the latest run, checked against the five required figures
```

## Setup

Python 3.9 or newer.

```
pip install -r requirements.txt
```

In Google Colab, put `!` in front of every command below (for example `!pip install -r requirements.txt`).

Run everything from the repo root. The scripts also work from other folders because they find the files relative to themselves.

## How to run (in this order)

### 1. SQL layer

```
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

If the `sqlite3` command is not installed, Python can run the same SQL files:

```python
import sqlite3
conn = sqlite3.connect("mamaearth.db")
for name in ["schema", "seed_data", "reports"]:
    conn.executescript(open(f"sql/{name}.sql").read())
print(conn.execute("SELECT (SELECT COUNT(*) FROM customers), (SELECT COUNT(*) FROM products), (SELECT COUNT(*) FROM orders)").fetchone())
```

The row counts should be 45 / 16 / 180. The output of every report is already pasted as a comment above its query in `sql/reports.sql`.

`schema.sql` drops and recreates the tables, so run the three files in this order on the same database. Report i adds a column, which means running `reports.sql` twice without running `schema.sql` again would cause an error.

## Why I made these choices

I kept the SQL and Python work separate so I could compare the raw revenue with the cleaned revenue instead of relying on just one result. I also kept the original CSV files unchanged and handled the cleaning in Python, making it easier to trace where the differences came from.

The order of the cleaning steps matters too. I fixed casing first, removed duplicates before imputing missing values, and flagged outliers instead of dropping them before building the monthly trend. This helped me keep the analysis consistent and understand how each cleaning step affected the results.

I also added an automated check to the GenAI layer. Instead of accepting the generated narrative without checking it, the script checks the saved output against five required figures. The offline template is there so the pipeline can still produce a narrative without depending on a successful API call.

## 2. Python layer

```
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` works directly with the raw CSVs, prints every intermediate result, ends with a self-check against the expected numbers, and **writes `narrator/findings.json`**.

`visualize.py` rebuilds the cleaned data from the same CSVs and saves the two charts into `visualizations/`. Running both scripts again produces the same numbers and PNG files.

The cleaning order is important: casing is fixed first, duplicates are removed before imputing, and outliers are flagged rather than dropped before the monthly trend is built.

## 3. GenAI narrator

```
python narrator/generate_narrative.py
```

**With no API key**, the script uses the offline template (`generate_scr_narrative_offline`). No network connection or additional setup is needed for this option.

**With a Gemini key**, you can get a free one from Google AI Studio. Set it as an environment variable and run the same command:

```
# Windows PowerShell
$env:GEMINI_API_KEY = "your-key"

# macOS / Linux
export GEMINI_API_KEY="your-key"

# Google Colab
%env GEMINI_API_KEY=your-key
```

The default model is `gemini-3.6-flash`. To use another model, set `GEMINI_MODEL` the same way.

**About `sample_output.txt`:** The current sample output was produced by a real Gemini run using `gemini-3.6-flash` and checked against the five required figures. If you run the script without an API key, it switches to the offline narrator and overwrites `narrator/sample_output.txt` with the offline-generated text.

Never put the API key in a file inside the repo.

The call uses a separate system instruction, `temperature=0.0`, `max_output_tokens=2048` and a 30 second timeout (the SDK counts timeouts in milliseconds, so the code passes 30000). If the call fails for any reason, the function returns an error dict and the script falls back to the offline template.

Whichever option runs, the script saves the narrative to `narrator/sample_output.txt` and then checks that saved file. The checker prints a PASS / FAIL line for each of the five required figures: cleaned revenue, COD return rate, the highest-risk segment rate, the duplicate gap and the peak month with its revenue.

## Results

| Finding | Value |
|---|---|
| Raw revenue, 180 orders (SQL report a) | Rs.99,860.20 |
| Cleaned revenue, 175 orders | Rs.97,358.30 |
| Gap | Rs.2,501.90 - exactly the 5 duplicate orders O0176-O0180 |
| Return rate: COD / UPI / CARD | 44.4% / 18.9% / 14.7% |
| Highest-risk segment | COD in Tier-2 cities, 54.5% (COD in Tier-1: 37.5%) |
| Discount vs returns | r = -0.09, negligible, so "bigger discounts reduce returns" is busted |
| January with the two bulk orders | Rs.29,582.10 (looks like the peak) |
| January without them | Rs.11,637.10 |
| True peak month | March, Rs.20,318.90 |
