from flask import jsonify, Blueprint
import psycopg2
import random
from app import db_params

def generate_id():
    return random.randint(1, 999)

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('', methods=['GET'])
def Analytics():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        # Query to retrieve total number of unique order IDs
        query_unique_orders = "SELECT COUNT(DISTINCT \"Order ID\") FROM orders;"

        # Query to retrieve total sum of Item Total
        query_total_item_total = "SELECT SUM(\"Item Total\") FROM orders;"

        # Execute the queries
        cursor.execute(query_unique_orders)
        total_unique_orders = cursor.fetchone()[0]

        cursor.execute(query_total_item_total)
        total_item_total = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return jsonify(TotalOrders = total_unique_orders, TotalItems = total_item_total), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500