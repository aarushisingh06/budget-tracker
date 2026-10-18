import io
import os
import re
import tempfile
import unittest

from app import create_app
from app.db import get_db


class AppTestCase(unittest.TestCase):
    csrf = False

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": self.db_path,
            "CSRF_ENABLED": self.csrf,
            "SECRET_KEY": "test",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def category_id(self, name):
        with self.app.app_context():
            row = get_db().execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
            return row["id"]

    def add(self, description="Groceries run", amount="45.20", category="Groceries", day="2026-10-05"):
        return self.client.post("/transactions", data={
            "occurred_on": day,
            "description": description,
            "amount": amount,
            "category_id": self.category_id(category),
        })

    def count_transactions(self):
        with self.app.app_context():
            return get_db().execute("SELECT COUNT(*) FROM transactions").fetchone()[0]


class TransactionTests(AppTestCase):
    def test_overview_loads(self):
        response = self.client.get("/?month=2026-10")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"October", response.data)

    def test_add_transaction_updates_summary(self):
        self.add(amount="45.20")
        self.add(description="Paycheck", amount="2000", category="Salary")
        page = self.client.get("/?month=2026-10").get_data(as_text=True)
        self.assertIn("$1,954.80", page)  # net
        self.assertIn("Groceries run", page)

    def test_invalid_amount_shows_error_and_saves_nothing(self):
        response = self.add(amount="12.345")
        self.assertEqual(response.status_code, 400)
        self.assertIn("two decimal places", response.get_data(as_text=True))
        self.assertEqual(self.count_transactions(), 0)

    def test_unknown_category_rejected(self):
        response = self.client.post("/transactions", data={
            "occurred_on": "2026-10-05", "description": "x", "amount": "1", "category_id": "9999",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count_transactions(), 0)

    def test_edit_and_delete(self):
        self.add()
        self.client.post("/transactions/1/edit", data={
            "occurred_on": "2026-10-06", "description": "Farmers market",
            "amount": "30", "category_id": self.category_id("Groceries"),
        })
        page = self.client.get("/transactions?month=2026-10").get_data(as_text=True)
        self.assertIn("Farmers market", page)
        self.assertIn("$30.00", page)

        self.client.post("/transactions/1/delete")
        self.assertEqual(self.count_transactions(), 0)

    def test_missing_transaction_is_404(self):
        self.assertEqual(self.client.get("/transactions/42/edit").status_code, 404)

    def test_user_text_is_escaped(self):
        self.add(description="<script>alert(1)</script>")
        page = self.client.get("/?month=2026-10").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)


class BudgetTests(AppTestCase):
    def test_over_budget_is_flagged(self):
        rent = self.category_id("Rent")
        self.client.post("/budgets", data={f"budget_{rent}": "1000"})
        self.add(description="Rent", amount="1200", category="Rent")
        page = self.client.get("/?month=2026-10").get_data(as_text=True)
        self.assertIn("$200.00 over", page)

    def test_invalid_budget_saves_nothing(self):
        rent, food = self.category_id("Rent"), self.category_id("Groceries")
        response = self.client.post("/budgets", data={f"budget_{rent}": "900", f"budget_{food}": "lots"})
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            row = get_db().execute("SELECT monthly_budget_cents FROM categories WHERE id = ?", (rent,)).fetchone()
            self.assertIsNone(row[0])

    def test_add_category_rejects_duplicates(self):
        self.assertEqual(self.client.post("/categories", data={"name": "Pets", "kind": "expense"}).status_code, 302)
        self.assertEqual(self.client.post("/categories", data={"name": "pets", "kind": "expense"}).status_code, 400)


class CsvTests(AppTestCase):
    def upload(self, text):
        return self.client.post("/import", data={
            "file": (io.BytesIO(text.encode("utf-8")), "data.csv"),
        }, content_type="multipart/form-data")

    def test_import_valid_file(self):
        response = self.upload(
            "date,description,category,amount\n"
            "2026-10-01,Rent,Rent,1450.00\n"
            "2026-10-03,Paycheck,salary,2100\n"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count_transactions(), 2)

    def test_import_is_all_or_nothing(self):
        response = self.upload(
            "date,description,category,amount\n"
            "2026-10-01,Rent,Rent,1450.00\n"
            "not-a-date,Oops,Nope,-3\n"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Row 3", response.get_data(as_text=True))
        self.assertEqual(self.count_transactions(), 0)

    def test_import_rejects_wrong_header(self):
        response = self.upload("when,what,amount\n2026-10-01,x,1\n")
        self.assertEqual(response.status_code, 400)

    def test_export_neutralizes_formulas_and_round_trips(self):
        self.add(description="=HYPERLINK(\"http://evil\")", amount="10")
        exported = self.client.get("/export.csv").get_data(as_text=True)
        self.assertIn("'=HYPERLINK", exported)

        # Importing the exported file restores the original text.
        self.client.post("/transactions/1/delete")
        self.upload(exported)
        with self.app.app_context():
            description = get_db().execute("SELECT description FROM transactions").fetchone()[0]
        self.assertEqual(description, '=HYPERLINK("http://evil")')


class CsrfTests(AppTestCase):
    csrf = True

    def test_post_without_token_is_rejected(self):
        response = self.add()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count_transactions(), 0)

    def test_post_with_token_succeeds(self):
        page = self.client.get("/").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = self.client.post("/transactions", data={
            "csrf_token": token, "occurred_on": "2026-10-05", "description": "Coffee",
            "amount": "4.50", "category_id": self.category_id("Dining out"),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.count_transactions(), 1)


if __name__ == "__main__":
    unittest.main()
