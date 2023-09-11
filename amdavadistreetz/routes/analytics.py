from flask import jsonify, Blueprint, request
import datetime, random
from app import dynamodb, resp_headers

def generate_id():
    return random.randint(1, 999)

orders_table = dynamodb.Table('Orders')

analytics_bp = Blueprint('analytics', __name__)

def get_orders_from_date(given_date):
    try:
        response = orders_table.query(
            IndexName='order_date-index',  # Replace with your GSI name for date-based queries
            KeyConditionExpression='order_date = :date',
            ExpressionAttributeValues={':date': given_date}
        )

        # Count the number of orders for the given date
        order_count = len(response.get('Items', []))

        return order_count

    except Exception as e:
        return jsonify({'error': f'Server error {e}'}), 500,  resp_headers

@analytics_bp.route('/get-orders-from-date', methods=['GET'])
def handle_get_orders_from_date():
    given_date_str = request.args.get('given_date')

    if not given_date_str:
        return jsonify({'error': 'Please provide a valid date as a query parameter (YYYY-MM-DD)'}), 400,  resp_headers

    try:
        given_date = datetime.datetime.strptime(given_date_str, '%Y-%m-%d').date()
        orders = get_orders_from_date(given_date)

        if orders is not None:
            return jsonify({'orders': orders}), 200,  resp_headers
        else:
            return jsonify({'error': 'An error occurred while retrieving orders'}), 500,  resp_headers

    except ValueError:
        return jsonify({'error': 'Invalid date format. Please use YYYY-MM-DD'}), 400,  resp_headers

def count_orders_for_month(year, month):
    try:
        year_str = str(year)
        month_str = str(month).zfill(2)

        key_condition_expression = 'year_month = :ym'
        expression_attribute_values = {':ym': f"{year_str}-{month_str}"}

        response = orders_table.query(
            IndexName='year_month-index',
            KeyConditionExpression=key_condition_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        order_count = len(response.get('Items', []))

        return order_count

    except Exception as e:
        print(e)
        return jsonify({'error': f'Server error {e}'}), 500,  resp_headers
    
@analytics_bp.route('/count-orders-for-month', methods=['GET'])
def handle_count_orders_for_month():
    year = request.args.get('year')
    month = request.args.get('month')

    if not year or not month:
        return jsonify({'error': 'Both year and month are required as query parameters'}), 400,  resp_headers

    try:
        year = int(year)
        month = int(month)

        if 1 <= month <= 12:
            order_count = count_orders_for_month(year, month)

            if order_count is not None:
                return jsonify({'order_count': order_count}), 200,  resp_headers
            else:
                return jsonify({'error': 'An error occurred while counting orders'}), 500,  resp_headers
        else:
            return jsonify({'error': 'Invalid month. Please provide a valid month between 1 and 12'}), 400,  resp_headers

    except ValueError:
        return jsonify({'error': 'Invalid year or month format. Please use numeric values'}), 400,  resp_headers
    
def count_orders_for_year(year):
    try:
        year_str = str(year)

        key_condition_expression = 'year = :yr'
        expression_attribute_values = {':yr': year_str}

        response = orders_table.query(
            IndexName='year-index',  # Replace with your GSI name for year-based queries
            KeyConditionExpression=key_condition_expression,
            ExpressionAttributeValues=expression_attribute_values
        )

        order_count = len(response.get('Items', []))

        return order_count

    except Exception as e:
        print(e)
        return jsonify({'error': f'Server error {e}'}), 500,  resp_headers
    
@analytics_bp.route('/count-orders-for-year', methods=['GET'])
def handle_count_orders_for_year():
    year = request.args.get('year')

    if not year:
        return jsonify({'error': 'year is required as query parameters'}), 400,  resp_headers

    try:
        year = int(year)

        order_count = count_orders_for_year(year)

        if order_count is not None:
            return jsonify({'order_count': order_count}), 200,  resp_headers
        else:
            return jsonify({'error': 'An error occurred while counting orders'}), 500,  resp_headers

    except ValueError:
        return jsonify({'error': 'Invalid year or month format. Please use numeric values'}), 400,  resp_headers

