"""
reports/models.py

The Reports app has no database models of its own.
All reports are computed on demand by querying the other apps' models.

This is intentional — storing pre-computed reports creates stale data problems.
Every report is a live query so the numbers are always accurate.

Data sources:
  - greenhouse_app  → Greenhouse, House, Bed, Crop
  - operations      → Operation
  - inventory       → InventoryItem, InventoryTransaction
  - financials      → Sale, Expense
"""
