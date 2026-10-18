"""Database queries. Routes call these instead of writing SQL inline."""

from dataclasses import dataclass, field


@dataclass
class CategorySpend:
    id: int
    name: str
    spent: int
    budget: int | None
    largest_spend: int = 0  # biggest category this month, used to scale unbudgeted bars

    @property
    def remaining(self):
        return None if self.budget is None else self.budget - self.spent

    @property
    def over_budget(self):
        return self.budget is not None and self.spent > self.budget

    @property
    def percent_used(self):
        """How full the bar should be, from 0 to 100.

        With a budget, it's the share of the budget used (capped at 100).
        Without one, it's relative to the biggest category this month.
        """
        if self.budget:
            return min(100, round(self.spent * 100 / self.budget))
        if self.budget == 0:
            return 100 if self.spent else 0
        if not self.largest_spend:
            return 0
        return round(self.spent * 100 / self.largest_spend)


@dataclass
class MonthSummary:
    income: int = 0
    expenses: int = 0
    categories: list[CategorySpend] = field(default_factory=list)

    @property
    def net(self):
        return self.income - self.expenses

    @property
    def budgeted(self):
        return sum(c.budget for c in self.categories if c.budget is not None)


# ---------------------------------------------------------------- categories

def list_categories(db, kind=None):
    sql = "SELECT id, name, kind, monthly_budget_cents FROM categories"
    params = ()
    if kind:
        sql += " WHERE kind = ?"
        params = (kind,)
    sql += " ORDER BY kind DESC, name COLLATE NOCASE"  # income first, then expenses
    return db.execute(sql, params).fetchall()


def get_category(db, category_id):
    return db.execute(
        "SELECT id, name, kind, monthly_budget_cents FROM categories WHERE id = ?",
        (category_id,),
    ).fetchone()


def category_ids_by_name(db):
    return {row["name"].casefold(): row["id"] for row in list_categories(db)}


def add_category(db, name, kind):
    cursor = db.execute("INSERT INTO categories (name, kind) VALUES (?, ?)", (name, kind))
    db.commit()
    return cursor.lastrowid


def set_budgets(db, budgets):
    """Save several budgets at once. `budgets` maps category id -> cents or None."""
    with db:
        db.executemany(
            "UPDATE categories SET monthly_budget_cents = ? WHERE id = ? AND kind = 'expense'",
            [(cents, category_id) for category_id, cents in budgets.items()],
        )


# -------------------------------------------------------------- transactions

def list_transactions(db, start=None, end=None, category_id=None, limit=None):
    sql = """
        SELECT t.id, t.occurred_on, t.description, t.amount_cents,
               c.id AS category_id, c.name AS category, c.kind
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
    """
    clauses, params = [], []
    if start:
        clauses.append("t.occurred_on >= ?")
        params.append(start)
    if end:
        clauses.append("t.occurred_on < ?")
        params.append(end)
    if category_id:
        clauses.append("t.category_id = ?")
        params.append(category_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY t.occurred_on DESC, t.id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return db.execute(sql, params).fetchall()


def get_transaction(db, transaction_id):
    return db.execute(
        "SELECT id, occurred_on, description, amount_cents, category_id FROM transactions WHERE id = ?",
        (transaction_id,),
    ).fetchone()


def create_transaction(db, occurred_on, description, amount_cents, category_id):
    cursor = db.execute(
        "INSERT INTO transactions (occurred_on, description, amount_cents, category_id) VALUES (?, ?, ?, ?)",
        (occurred_on, description, amount_cents, category_id),
    )
    db.commit()
    return cursor.lastrowid


def update_transaction(db, transaction_id, occurred_on, description, amount_cents, category_id):
    db.execute(
        """UPDATE transactions
           SET occurred_on = ?, description = ?, amount_cents = ?, category_id = ?
           WHERE id = ?""",
        (occurred_on, description, amount_cents, category_id, transaction_id),
    )
    db.commit()


def delete_transaction(db, transaction_id):
    cursor = db.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    db.commit()
    return cursor.rowcount


def insert_many(db, rows):
    """Insert all rows in one database transaction: all succeed or none do."""
    with db:
        db.executemany(
            "INSERT INTO transactions (occurred_on, description, amount_cents, category_id) VALUES (?, ?, ?, ?)",
            [(r["occurred_on"], r["description"], r["amount_cents"], r["category_id"]) for r in rows],
        )


# ------------------------------------------------------------------ reports

def month_summary(db, start, end):
    summary = MonthSummary()

    totals = db.execute(
        """SELECT c.kind, SUM(t.amount_cents) AS total
           FROM transactions t JOIN categories c ON c.id = t.category_id
           WHERE t.occurred_on >= ? AND t.occurred_on < ?
           GROUP BY c.kind""",
        (start, end),
    ).fetchall()
    for row in totals:
        if row["kind"] == "income":
            summary.income = row["total"]
        else:
            summary.expenses = row["total"]

    rows = db.execute(
        """SELECT c.id, c.name, c.monthly_budget_cents AS budget,
                  COALESCE(SUM(t.amount_cents), 0) AS spent
           FROM categories c
           LEFT JOIN transactions t
             ON t.category_id = c.id AND t.occurred_on >= ? AND t.occurred_on < ?
           WHERE c.kind = 'expense'
           GROUP BY c.id
           HAVING COALESCE(SUM(t.amount_cents), 0) > 0 OR c.monthly_budget_cents IS NOT NULL
           ORDER BY spent DESC, c.name COLLATE NOCASE""",
        (start, end),
    ).fetchall()
    largest = max((r["spent"] for r in rows), default=0)
    summary.categories = [
        CategorySpend(r["id"], r["name"], r["spent"], r["budget"], largest) for r in rows
    ]
    return summary
