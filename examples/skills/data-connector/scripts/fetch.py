# SPDX-License-Identifier: MIT
"""Run a query and return rows."""


def fetch(connection, query):
    cursor = connection.cursor()
    cursor.execute(query)
    return cursor.fetchall()
