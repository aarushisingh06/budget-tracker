"""Validation for user input. Returns cleaned data plus a dict of field errors."""

from datetime import date

from .money import MoneyError, parse_amount
from . import queries

MAX_DESCRIPTION = 120
MAX_CATEGORY_NAME = 40


def clean_basic_fields(raw_date, raw_description, raw_amount):
    """Validate the fields shared by the web form and CSV import."""
    data, errors = {}, {}

    try:
        data["occurred_on"] = date.fromisoformat((raw_date or "").strip()).isoformat()
    except ValueError:
        errors["occurred_on"] = "Enter a date in the format YYYY-MM-DD."

    description = (raw_description or "").strip()
    if not description:
        errors["description"] = "Add a short description."
    elif len(description) > MAX_DESCRIPTION:
        errors["description"] = f"Keep the description under {MAX_DESCRIPTION} characters."
    data["description"] = description

    try:
        data["amount_cents"] = parse_amount(raw_amount)
    except MoneyError as exc:
        errors["amount"] = str(exc)

    return data, errors


def validate_transaction(form, db):
    data, errors = clean_basic_fields(
        form.get("occurred_on"), form.get("description"), form.get("amount")
    )
    try:
        category_id = int(form.get("category_id", ""))
    except ValueError:
        category_id = None
    if category_id is None or queries.get_category(db, category_id) is None:
        errors["category_id"] = "Choose a category."
    data["category_id"] = category_id
    return data, errors


def validate_category(form, db):
    name = (form.get("name") or "").strip()
    kind = form.get("kind")
    errors = {}
    if not name:
        errors["name"] = "Enter a name for the category."
    elif len(name) > MAX_CATEGORY_NAME:
        errors["name"] = f"Keep the name under {MAX_CATEGORY_NAME} characters."
    elif name.casefold() in queries.category_ids_by_name(db):
        errors["name"] = f"You already have a category called “{name}”."
    if kind not in ("income", "expense"):
        errors["kind"] = "Choose income or expense."
    return {"name": name, "kind": kind}, errors
