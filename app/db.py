"""SQLite connection handling and schema setup."""

import sqlite3

import click
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    kind                 TEXT    NOT NULL CHECK (kind IN ('income', 'expense')),
    monthly_budget_cents INTEGER CHECK (monthly_budget_cents IS NULL OR monthly_budget_cents >= 0)
);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_on  TEXT    NOT NULL,                          -- ISO date, YYYY-MM-DD
    description  TEXT    NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0), -- direction comes from the category
    category_id  INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_occurred_on ON transactions (occurred_on);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category_id);
"""

DEFAULT_CATEGORIES = [
    ("Salary", "income"),
    ("Other income", "income"),
    ("Rent", "expense"),
    ("Groceries", "expense"),
    ("Dining out", "expense"),
    ("Transport", "expense"),
    ("Utilities", "expense"),
    ("Entertainment", "expense"),
    ("Health", "expense"),
    ("Shopping", "expense"),
    ("Other", "expense"),
]


def get_db():
    """Return the request's database connection, opening one if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist and seed default categories once."""
    db = get_db()
    db.executescript(SCHEMA)
    (count,) = db.execute("SELECT COUNT(*) FROM categories").fetchone()
    if count == 0:
        db.executemany("INSERT INTO categories (name, kind) VALUES (?, ?)", DEFAULT_CATEGORIES)
    db.commit()


@click.command("reset-db")
@click.confirmation_option(prompt="This deletes all transactions. Continue?")
def reset_db_command():
    """Drop all data and start fresh."""
    db = get_db()
    db.executescript("DROP TABLE IF EXISTS transactions; DROP TABLE IF EXISTS categories;")
    init_db()
    click.echo("Database reset.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(reset_db_command)
