# Budget Tracker

A personal budget tracker built with Flask and SQLite. Log income and spending, set monthly budgets per category, and see at a glance how much is left in each one.

<!-- Add a screenshot: save one as docs/screenshot.png and uncomment the next line -->
<!-- ![Overview page](docs/screenshot.png) -->

## Features

- **Monthly overview** showing money in, money out, and what's left over, with month-by-month navigation
- **Category budgets** with progress bars that turn red when you go over
- **Transactions** you can add, edit, delete, and filter by category
- **CSV import and export** compatible with Excel, Numbers, and Google Sheets
- **Custom categories** for both income and spending
- **Light and dark mode** following your system setting

## Getting started

Requires Python 3.10 or newer.

```bash
git clone https://github.com/aarushisingh06/budget-tracker.git
cd budget-tracker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
flask --app app run --debug
```

Then open http://127.0.0.1:5000. The database is created automatically in `instance/budget.sqlite`.

To try it with example data, go to **Import and export** and upload `sample_data.csv`.

To wipe all data and start over:

```bash
flask --app app reset-db
```

## Running the tests

```bash
python -m unittest discover -s tests -t . -v
```

The tests also run automatically on GitHub Actions for every push.

## Project structure

```
app/
  __init__.py      Application factory
  db.py            SQLite connection, schema, default categories
  queries.py       All SQL lives here; routes stay thin
  forms.py         Input validation
  money.py         Parsing and formatting amounts
  months.py        Month arithmetic
  csv_io.py        CSV import and export
  security.py      CSRF protection and security headers
  routes.py        Pages and form handlers
  templates/       Jinja templates
  static/          CSS and a small JS file
tests/             Unit and integration tests
```

## Design decisions

**Money is stored as integer cents.** Floating-point numbers can't represent values like 0.10 exactly, so `0.1 + 0.2` isn't `0.3`. User input is parsed with Python's `Decimal`, validated (positive, at most two decimal places), and stored as an integer number of cents. Amounts are always positive; whether a transaction is income or spending comes from its category.

**Imports are all-or-nothing.** Every row of an uploaded CSV is validated before anything is written, and the insert happens inside a single database transaction. If row 47 has a typo, you get a clear error list and no half-imported data.

**CSV exports are protected against formula injection.** Spreadsheet apps execute cells that start with `=`, `+`, `-`, or `@`. Exported text fields that start with those characters are prefixed with an apostrophe, and the prefix is removed again on import so data round-trips cleanly.

**Every form is protected against CSRF.** Each session gets a random token that state-changing requests must send back, compared in constant time. It's implemented by hand in `security.py` (about 20 lines) to show how it works, rather than pulled in from a library.

**Strict Content Security Policy.** No inline scripts or styles are allowed, which limits the damage from any XSS bug. That's why progress bar widths use CSS classes instead of inline `style` attributes.

**Database constraints back up app validation.** The schema uses `CHECK` constraints and foreign keys, so invalid data is rejected even if a bug slips past the Python validation.

## Ideas for future work

- User accounts with password hashing so multiple people can use one instance
- Recurring transactions (rent, subscriptions) that add themselves each month
- Charts showing spending trends over several months
- Importing bank statement formats directly
- Multi-currency support

## License

MIT. See [LICENSE](LICENSE).
