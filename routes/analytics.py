from flask import jsonify, Blueprint
import psycopg2
import random
from app import db_params
from datetime import datetime, timedelta

def generate_id():
    return random.randint(1, 999)

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('', methods=['GET'])
def Analytics():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        count_query = "SELECT COUNT(*) FROM orders;"
        cursor.execute(count_query)
        total_orders = cursor.fetchone()[0]

        select_query = 'SELECT SUM("subTotal") FROM payments;'
        cursor.execute(select_query)
        total_amount = cursor.fetchone()[0]

        select_query = 'SELECT AVG("subTotal") FROM payments;'
        cursor.execute(select_query)
        average_ticket = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        return jsonify(totalOrders = total_orders, totalAmount = float(total_amount), averageTicket = float(average_ticket)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def fetch_orders_line(time_period):
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    if time_period == 'week':
        # Calculate the start and end of the week (7 days ago to today)
        end_of_week = datetime.now()
        start_of_week = end_of_week - timedelta(days=6)
        
        # SQL query to fetch orders for the current week
        query = """
            SELECT DATE("Ordered On"), COUNT(*) FROM orders
            WHERE "Ordered On" >= %s AND "Ordered On" <= %s
            GROUP BY DATE("Ordered On")
        """
        cur.execute(query, (start_of_week, end_of_week))
    elif time_period == 'month':
        # Calculate the start and end of the current month
        today = datetime.now()
        start_of_month = today.replace(day=1)
        end_of_month = start_of_month.replace(
            day=1, month=today.month + 1) - timedelta(days=1)
        
        # SQL query to fetch orders for the current month
        query = """
            SELECT DATE("Ordered On"), COUNT(*) FROM orders
            WHERE "Ordered On" >= %s AND "Ordered On" <= %s
            GROUP BY DATE("Ordered On")
        """
        cur.execute(query, (start_of_month, end_of_month))
    else:  # 'year'
        # SQL query to fetch orders for the current year
        query = """
            SELECT DATE_TRUNC('month', "Ordered On"), COUNT(*) FROM orders
            WHERE EXTRACT(YEAR FROM "Ordered On") = EXTRACT(YEAR FROM NOW())
            GROUP BY DATE_TRUNC('month', "Ordered On")
        """
        cur.execute(query)

    orders = cur.fetchall()
    conn.close()
    return orders

def generate_labels_for_month(year, month):
    num_days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days
    labels = [str(i) for i in range(1, num_days_in_month + 1)]
    return labels

@analytics_bp.route('/get_orders/<time_period>')
def get_orders(time_period):
    orders = fetch_orders_line(time_period)

    if time_period == 'week':
        data_label = "Weekly Orders"
        labels = [(datetime.now() - timedelta(days=i)).strftime('%A') for i in range(6, -1, -1)]
        daily_counts = [0] * 7

        for order_date, count in orders:
            day_index = labels.index(order_date.strftime('%A'))
            daily_counts[day_index] = count

    elif time_period == 'year':
        data_label = "Yearly Orders"
        labels = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        daily_counts = [0] * len(labels)

        for order_date, count in orders:
            month = order_date.month
            index = month - 1  # Adjust for 0-based index
            daily_counts[index] = count
    else:
        data_label = "Monthly Orders"
        today = datetime.now()
        year = today.year
        month = today.month
        labels = generate_labels_for_month(year, month)
        daily_counts = [0] * len(labels)

        for order_date, count in orders:
            day = order_date.day
            index = day - 1
            daily_counts[index] = count

    data = {
        'labels': labels,
        'datasets': [
            {
                'label': data_label,
                'data': daily_counts,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.5)',
            },
        ],
    }

    return jsonify(data)

def fetch_orders(time_config):
    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()

    if time_config == 'today':
        today = datetime.now()
        start_of_day = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        query = """
            SELECT "Ordered On" FROM orders
            WHERE "Ordered On" >= %s AND "Ordered On" <= %s
        """
        cur.execute(query, (start_of_day, end_of_day))
    else:  # 'yesterday'
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        start_of_yesterday = yesterday.replace(
            hour=0, minute=0, second=0, microsecond=0)
        end_of_yesterday = yesterday.replace(
            hour=23, minute=59, second=59, microsecond=999999)
        
        query = """
            SELECT "Ordered On" FROM orders
            WHERE "Ordered On" >= %s AND "Ordered On" <= %s
        """
        cur.execute(query, (start_of_yesterday, end_of_yesterday))

    orders = cur.fetchall()
    conn.close()
    return orders

@analytics_bp.route('/get_hourly_orders/<time_config>')
def get_hourly_orders(time_config):
    orders = fetch_orders(time_config)

    ordered_hours = [order[0].hour for order in orders]
    hourly_counts = [ordered_hours.count(hour) for hour in range(24)]

    labels = [str(hour) + ':00' for hour in range(24)]
    data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Hourly Orders',
                'data': hourly_counts,
                'borderColor': 'rgb(255, 99, 132)',
                'backgroundColor': 'rgba(255, 99, 132, 0.5)',
            },
        ],
    }

    return jsonify(data)