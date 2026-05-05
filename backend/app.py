from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'expenses.csv')

def get_fresh_data():
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=['id', 'date', 'category', 'description', 'amount' , 'payment_method'])
        df.to_csv(CSV_PATH, index=False)
    df = pd.read_csv(CSV_PATH)
    return df.fillna('') # Critical: Replaces empty/NaN with ""

@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    df = get_fresh_data()
    return jsonify(df.to_dict(orient='records'))

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    data = request.json
    df = get_fresh_data()
    new_id = int(df['id'].max() + 1) if not df.empty else 1
    new_row = pd.DataFrame([{
        'id': new_id,
        'date': data.get('date'),
        'category': data.get('category'),
        'description': data.get('description', ''),
        'payment_method': data.get('payment_method', ''),
        'amount': float(data.get('amount', 0))
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(CSV_PATH, index=False)
    return jsonify({"status": "success"}), 201

@app.route('/api/expenses/<int:id>', methods=['DELETE'])
def delete_expense(id):
    df = get_fresh_data()
    df = df[df['id'] != id]
    df.to_csv(CSV_PATH, index=False)
    return jsonify({"status": "deleted"}), 200

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    df = get_fresh_data()
    if df.empty: return jsonify({"total": 0, "categories": {}})
    total = float(df['amount'].sum())
    cats = df.groupby('category')['amount'].sum().to_dict()
    return jsonify({"total": total, "categories": cats})


## Banks

BANK_CSV_PATH = os.path.join(BASE_DIR, 'banks.csv')

def get_bank_data():
    if not os.path.exists(BANK_CSV_PATH):
        pd.DataFrame(columns=['id', 'bank_name', 'balance']).to_csv(BANK_CSV_PATH, index=False)
    return pd.read_csv(BANK_CSV_PATH).fillna('')

@app.route('/api/banks', methods=['GET'])
def get_banks():
    return jsonify(get_bank_data().to_dict(orient='records'))

@app.route('/api/banks', methods=['POST'])
def add_bank():
    data = request.json
    df = get_bank_data()
    new_id = int(df['id'].max() + 1) if not df.empty else 1
    new_row = pd.DataFrame([{
        'id': new_id,
        'bank_name': data.get('bank_name'),
        'balance': float(data.get('balance', 0))
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(BANK_CSV_PATH, index=False)
    return jsonify({"status": "success"}), 201

@app.route('/api/banks/<int:id>', methods=['DELETE'])
def delete_bank(id):
    df = get_bank_data()
    df = df[df['id'] != id]
    df.to_csv(BANK_CSV_PATH, index=False)
    return jsonify({"status": "deleted"}), 200

## Update

# --- UPDATE EXPENSE ---
@app.route('/api/expenses/<int:id>', methods=['PUT'])
def update_expense(id):
    data = request.json
    df = get_fresh_data()
    if id in df['id'].values:
        df.loc[df['id'] == id, ['date', 'category', 'description', 'amount', 'payment_method']] = [
            data.get('date'), data.get('category'), 
            data.get('description'), float(data.get('amount')),
            data.get('payment_method')
        ]
        df.to_csv(CSV_PATH, index=False)
        return jsonify({"status": "updated"}), 200
    return jsonify({"error": "Not found"}), 404

# --- UPDATE BANK ---
@app.route('/api/banks/<int:id>', methods=['PUT'])
def update_bank(id):
    data = request.json
    df = get_bank_data()
    if id in df['id'].values:
        df.loc[df['id'] == id, ['bank_name', 'balance']] = [
            data.get('bank_name'), float(data.get('balance'))
        ]
        df.to_csv(BANK_CSV_PATH, index=False)
        return jsonify({"status": "updated"}), 200
    return jsonify({"error": "Not found"}), 404



## Credit cards
BILL_CSV = os.path.join(BASE_DIR, 'credit_bills.csv')

def get_bill_data():
    if not os.path.exists(BILL_CSV):
        pd.DataFrame(columns=['id', 'card_name', 'bill_date', 'bill_amount', 'paid_amount', 'paid_date', 'from_bank']).to_csv(BILL_CSV, index=False)
    return pd.read_csv(BILL_CSV).fillna('')

@app.route('/api/bills', methods=['GET', 'POST'])
def handle_bills():
    if request.method == 'POST':
        data = request.json
        df = get_bill_data()
        new_id = int(df['id'].max() + 1) if not df.empty else 1
        new_row = pd.DataFrame([{**data, 'id': new_id}])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(BILL_CSV, index=False)
        return jsonify({"status": "success"}), 201
    return jsonify(get_bill_data().to_dict(orient='records'))

# --- UPDATE BILL ---
@app.route('/api/bills/<int:id>', methods=['PUT'])
def update_bill(id):
    data = request.json
    df = get_bill_data()

    if id in df['id'].values:

        df.loc[df['id'] == id, 'card_name'] = data.get('card_name', '')
        df.loc[df['id'] == id, 'bill_date'] = data.get('bill_date', '')
        df.loc[df['id'] == id, 'paid_date'] = data.get('paid_date', '')
        df.loc[df['id'] == id, 'from_bank'] = data.get('from_bank', '')

        df.loc[df['id'] == id, 'bill_amount'] = float(data.get('bill_amount', 0))
        df.loc[df['id'] == id, 'paid_amount'] = float(data.get('paid_amount', 0))

        df.to_csv(BILL_CSV, index=False)

        return jsonify({"status": "updated"}), 200

    return jsonify({"error": "Not found"}), 404

@app.route('/api/bills/<int:id>', methods=['DELETE'])
def delete_bill(id):
    df = get_bill_data()
    df = df[df['id'] != id].to_csv(BILL_CSV, index=False)
    return jsonify({"status": "deleted"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)