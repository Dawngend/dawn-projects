# Market Notebook

A Jupyter notebook that explores the job postings data.
It reads `data/job_observations.csv` (one row per posting, with source, salary and first and last seen columns), cleans the columns, then counts sources, eligible postings, common title words, tags, salary coverage and observation spans.

## Run

Use Python 3. Run this from `projects/market_notebook`.
Install the notebook dependencies with `python -m pip install jupyter pandas matplotlib`.

```bash
python -m jupyter nbconvert --to notebook --execute --inplace market_notebook.ipynb
```

The notebook runs top to bottom and writes the outputs back into `market_notebook.ipynb`.
Open that file in Jupyter to see the charts and the wrap-up at the end.

The CSV lives in `data/` beside the notebook. Git ignores `data/` and `*.csv`, so keep a copy of the CSV in that folder or the notebook cannot run.
