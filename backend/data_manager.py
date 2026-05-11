import os

import pandas as pd

import database as db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def init_db():
    db.init_db()


def get_df(user_id: int):
    return pd.DataFrame(db.expenses_list(user_id))


def save_expense(data, user_id: int):
    new_id = db.expense_add(user_id, data)
    return {**data, "id": new_id}
