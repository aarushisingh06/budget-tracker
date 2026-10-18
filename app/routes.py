"""HTTP routes."""

from datetime import date

from flask import (
    Blueprint, Response, abort, flash, redirect, render_template, request, url_for,
)

from . import queries
from .csv_io import import_csv, export_csv
from .db import get_db
from .forms import validate_category, validate_transaction
from .money import MoneyError, cents_to_plain, parse_amount
from .months import month_bounds, month_key, parse_month, shift_month

bp = Blueprint("main", __name__)


def _month_context(month):
    return {
        "month": month,
        "month_key": month_key(month),
        "prev_key": month_key(shift_month(month, -1)),
        "next_key": month_key(shift_month(month, 1)),
        "is_current_month": month == date.today().replace(day=1),
    }


def _default_date(month):
    today = date.today()
    return today.isoformat() if today.replace(day=1) == month else month.isoformat()


# ----------------------------------------------------------------- overview

def _render_overview(month, form=None, errors=None, status=200):
    db = get_db()
    start, end = month_bounds(month)
    context = _month_context(month)
    return render_template(
        "overview.html",
        summary=queries.month_summary(db, start, end),
        recent=queries.list_transactions(db, start, end, limit=8),
        categories=queries.list_categories(db),
        form=form or {"occurred_on": _default_date(month)},
        errors=errors or {},
        **context,
    ), status


@bp.get("/")
def overview():
    return _render_overview(parse_month(request.args.get("month")))


@bp.post("/transactions")
def create_transaction():
    db = get_db()
    data, errors = validate_transaction(request.form, db)
    if errors:
        month = parse_month(request.form.get("month"))
        return _render_overview(month, form=request.form, errors=errors, status=400)

    queries.create_transaction(db, **data)
    flash(f"Added “{data['description']}”.", "success")
    return redirect(url_for("main.overview", month=data["occurred_on"][:7]))


# ------------------------------------------------------------- transactions

@bp.get("/transactions")
def transactions():
    db = get_db()
    month = parse_month(request.args.get("month"))
    start, end = month_bounds(month)
    category_id = request.args.get("category", type=int)
    rows = queries.list_transactions(db, start, end, category_id=category_id)
    income = sum(r["amount_cents"] for r in rows if r["kind"] == "income")
    spent = sum(r["amount_cents"] for r in rows if r["kind"] == "expense")
    return render_template(
        "transactions.html",
        rows=rows,
        income=income,
        spent=spent,
        categories=queries.list_categories(db),
        selected_category=category_id,
        **_month_context(month),
    )


@bp.route("/transactions/<int:transaction_id>/edit", methods=["GET", "POST"])
def edit_transaction(transaction_id):
    db = get_db()
    existing = queries.get_transaction(db, transaction_id)
    if existing is None:
        abort(404)

    if request.method == "POST":
        data, errors = validate_transaction(request.form, db)
        if not errors:
            queries.update_transaction(db, transaction_id, **data)
            flash("Saved changes.", "success")
            return redirect(url_for("main.transactions", month=data["occurred_on"][:7]))
        form = request.form
        status = 400
    else:
        form = {
            "occurred_on": existing["occurred_on"],
            "description": existing["description"],
            "amount": cents_to_plain(existing["amount_cents"]),
            "category_id": str(existing["category_id"]),
        }
        errors, status = {}, 200

    return render_template(
        "edit.html",
        transaction=existing,
        form=form,
        errors=errors,
        categories=queries.list_categories(db),
        back_month=existing["occurred_on"][:7],
    ), status


@bp.post("/transactions/<int:transaction_id>/delete")
def delete_transaction(transaction_id):
    db = get_db()
    existing = queries.get_transaction(db, transaction_id)
    if existing is None:
        abort(404)
    queries.delete_transaction(db, transaction_id)
    flash(f"Deleted “{existing['description']}”.", "success")
    return redirect(url_for("main.transactions", month=existing["occurred_on"][:7]))


# ------------------------------------------------------------------ budgets

def _render_budgets(budget_form=None, budget_errors=None, category_form=None,
                    category_errors=None, status=200):
    db = get_db()
    month = date.today().replace(day=1)
    start, end = month_bounds(month)
    spent = {c.id: c.spent for c in queries.month_summary(db, start, end).categories}
    expense_categories = queries.list_categories(db, kind="expense")
    if budget_form is None:
        budget_form = {
            f"budget_{c['id']}": cents_to_plain(c["monthly_budget_cents"])
            for c in expense_categories
            if c["monthly_budget_cents"] is not None
        }
    return render_template(
        "budgets.html",
        expense_categories=expense_categories,
        income_categories=queries.list_categories(db, kind="income"),
        spent=spent,
        month=month,
        budget_form=budget_form,
        budget_errors=budget_errors or {},
        category_form=category_form or {"kind": "expense"},
        category_errors=category_errors or {},
    ), status


@bp.get("/budgets")
def budgets():
    return _render_budgets()


@bp.post("/budgets")
def save_budgets():
    db = get_db()
    updates, errors = {}, {}
    for category in queries.list_categories(db, kind="expense"):
        key = f"budget_{category['id']}"
        raw = (request.form.get(key) or "").strip()
        if not raw:
            updates[category["id"]] = None
            continue
        try:
            updates[category["id"]] = parse_amount(raw, allow_zero=True)
        except MoneyError as exc:
            errors[key] = str(exc)

    if errors:
        return _render_budgets(budget_form=request.form, budget_errors=errors, status=400)

    queries.set_budgets(db, updates)
    flash("Saved budgets.", "success")
    return redirect(url_for("main.budgets"))


@bp.post("/categories")
def create_category():
    db = get_db()
    data, errors = validate_category(request.form, db)
    if errors:
        return _render_budgets(category_form=request.form, category_errors=errors, status=400)
    queries.add_category(db, data["name"], data["kind"])
    flash(f"Added the “{data['name']}” category.", "success")
    return redirect(url_for("main.budgets"))


# ---------------------------------------------------------- import / export

@bp.get("/data")
def data():
    month = date.today().replace(day=1)
    return render_template("data.html", month_key=month_key(month), month=month)


@bp.post("/import")
def import_transactions():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        flash("Choose a CSV file to import.", "error")
        return redirect(url_for("main.data"))

    result = import_csv(get_db(), upload.read())
    if result.errors:
        return render_template(
            "data.html",
            import_errors=result.errors,
            month_key=month_key(date.today().replace(day=1)),
            month=date.today().replace(day=1),
        ), 400

    flash(f"Imported {result.imported} transaction{'s' if result.imported != 1 else ''}.", "success")
    return redirect(url_for("main.transactions"))


@bp.get("/export.csv")
def export_transactions():
    db = get_db()
    raw_month = request.args.get("month")
    if raw_month:
        month = parse_month(raw_month)
        rows = queries.list_transactions(db, *month_bounds(month))
        filename = f"transactions-{month_key(month)}.csv"
    else:
        rows = queries.list_transactions(db)
        filename = "transactions-all.csv"

    return Response(
        export_csv(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ------------------------------------------------------------------- errors

@bp.app_errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Request not accepted", message=error.description), 400


@bp.app_errorhandler(404)
def not_found(_error):
    return render_template(
        "error.html", title="Not found",
        message="That page or transaction doesn’t exist. It may have been deleted.",
    ), 404


@bp.app_errorhandler(413)
def too_large(_error):
    return render_template(
        "error.html", title="File too large", message="Imports are limited to 2 MB.",
    ), 413
