import pandas as pd
import os
from datetime import datetime

CSV_PATH = '../data/expenses.csv'

def init_db():
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=['id', 'date', 'category', 'description', 'amount', 'payment_method'])
        df.to_csv(CSV_PATH, index=False)

def get_df():
    return pd.read_csv(CSV_PATH)

def save_expense(data):
    df = get_df()
    new_id = int(df['id'].max() + 1) if not df.empty else 1
    data['id'] = new_id
    new_row = pd.DataFrame([data])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CSV_PATH, index=False)
    return data