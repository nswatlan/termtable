"""Data access. Every SQL statement in the app lives in this package.

Repository functions take plain arguments (ids, values), run SQL through
app.db and return rows as dicts. They never commit and never raise HTTP
errors: transactions and rules belong to the services.
"""
