from flask import request, jsonify, Blueprint
from routes.utility import *
import datetime
from functools import wraps
from app import bcrypt, resp_headers, dynamodb

user_table = dynamodb.Table('Users')
address_table = dynamodb.Table('UserAddresses')
payment_table  = dynamodb.Table('UserPayments')
loyalty_table = dynamodb.Table('UsersLoyalty')

def generate_id():
    return random.randint(1, 999)

users_bp = Blueprint('users', __name__)

def protected_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token is missing'}), 401,  resp_headers

        decoded_token = verify_token(token)

        if not decoded_token:
            return jsonify({'error': 'Invalid token'}), 401,  resp_headers

        return f(*args, **kwargs)

    return decorated_function

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('firstName')
    last_name = data.get('lastName')

    if not email or not password:
        return jsonify({'error': 'Both email and password are required'}), 400,  resp_headers

    hashed_password = hash_password(password, bcrypt)

    try:
        response = user_table.query(
            IndexName='email-index',  # Replace with your GSI name
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={
                ':email': email
            }
        )

        if response.get('Items'):
            return jsonify({'error': 'Email is already registered'}), 401,  resp_headers

        user_id = generate_id

        user_table.put_item(
            Item={
                'user_id': user_id,
                'email': email,
                'password_hash': hashed_password,
                'first_name': first_name,
                'last_name': last_name
            }
        )

        auth_token = generate_auth_token(user_id)

    except Exception as e:
        print (e)
        return jsonify({'error': 'An error occurred while registering the user'}), 500,  resp_headers

    return jsonify({'auth_token': auth_token, 'message': 'User registered successfully'}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Both email and password are required'}), 400,  resp_headers

    try:
        response = user_table.get_item(Key={'email': email})
        user_data = response.get('Item')

        if user_data is None:
            return jsonify({'error': 'Invalid email'}), 401,  resp_headers

        user_id = user_data['user_id']
        stored_hashed_password = user_data['password_hash']
        current_login_attempt = user_data.get('current_login_attempt', 0)

        if current_login_attempt >= 5:
            if not check_reset_token_status(email):
                reset_token = generate_reset_token()
                expiration_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).isoformat()

                if store_reset_token_in_database(email, reset_token, expiration_time):
                    if send_password_reset_email(email, reset_token):
                        return jsonify({'error': 'Account temporarily locked. Too many login attempts.'}), 403,  resp_headers
                    else:
                        return jsonify({'error': 'Error resetting password'}), 404
                else:
                    return jsonify({'error': 'Error resetting password'}), 404

            return jsonify({'error': 'Account temporarily locked. Too many login attempts.'}), 403,  resp_headers

        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
            current_login_attempt = 0
            auth_token = generate_auth_token(user_id)
        else:
            current_login_attempt += 1

        user_table.update_item(
            Key={'email': email},
            UpdateExpression="SET current_login_attempt = :val",
            ExpressionAttributeValues={':val': current_login_attempt}
        )

        if current_login_attempt != 0:
            return jsonify({'error': 'Invalid password'}), 401,  resp_headers

        return jsonify({'auth_token': auth_token, 'message': 'Login successful'}), 200,  resp_headers

    except Exception as e:
        print (e)
        return jsonify({'error': 'An error occurred while authenticating the user'}), 500,  resp_headers


@users_bp.route('/reset-password-request', methods=['POST'])
def reset_password_request():
    data = request.get_json()
    email = data.get('email')

    if not email_exists_in_database(email):
        return jsonify({'error': 'Email not found'}), 404

    reset_token = generate_reset_token()
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

    if store_reset_token_in_database(email, reset_token, expiration_time):

        if send_password_reset_email(email, reset_token):
            return jsonify({'message': 'Password reset email sent'}), 200,  resp_headers
        else:
            return jsonify({'error': 'Error resetting password'}), 404
    
    else:
        return jsonify({'error': 'Error resetting password'}), 404
    
@users_bp.route('/reset-password', methods=['POST'])
def handle_reset_password():
    data = request.get_json()
    reset_token = data.get('reset_token')
    new_password = data.get('new_password')

    if not reset_token or not new_password:
        return jsonify({'error': 'Reset_token, and new_password are required'}), 400,  resp_headers

    result = reset_password(reset_token, new_password, bcrypt)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200,  resp_headers
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 400,  resp_headers
    else:
        return jsonify({'error': 'An unknown error occurred'}), 500,  resp_headers
    
@users_bp.route('/store-user-address', methods=['POST'])
@protected_route
def handle_store_user_address():
    data = request.get_json()

    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    address_line1 = data.get('address_line1')
    address_line2 = data.get('address_line2')
    city = data.get('city')
    state = data.get('state')
    postal_code = data.get('postal_code')
    country = data.get('country')

    if not user_id or not address_line1 or not city or not state or not postal_code or not country:
        return jsonify({'error': 'Missing required fields'}), 400,  resp_headers

    result = store_user_address(user_id, address_line1, address_line2, city, state, postal_code, country)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200,  resp_headers
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 500,  resp_headers
    
@users_bp.route('/store-user-payment', methods=['POST'])
@protected_route
def handle_store_user_payment():
    data = request.get_json()

    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    card_number = data.get('card_number')
    expiration_month = data.get('expiration_month')
    expiration_year = data.get('expiration_year')
    cvc = data.get('cvc')

    if not user_id or not card_number or not expiration_month or not expiration_year or not cvc:
        return jsonify({'error': 'Missing required fields'}), 400,  resp_headers

    result = store_user_payment(user_id, card_number, expiration_month, expiration_year, cvc)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200,  resp_headers
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 500,  resp_headers
    
@users_bp.route('/get-user-addresses', methods=['GET'])
@protected_route
def get_user_addresses():
    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    try:
        response = address_table.query(
            IndexName='user_id-index',  # Replace with your GSI name
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )

        addresses = response.get('Items', [])

        address_list = [{'address_id': int(row['address_id']), 'address_line1': row['address_line1'], 'address_line2': row.get('address_line2', ''), 'city': row['city'], 'state': row['state'], 'postal_code': row['postal_code']} for row in addresses]

        return jsonify({'addresses': address_list}), 200,  resp_headers

    except Exception as e:
        print(e)
        return jsonify({'error': 'An error occurred while fetching user addresses'}), 500,  resp_headers


@users_bp.route('/get-user-payments', methods=['GET'])
@protected_route
def get_user_payments():
    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    try:
        response = payment_table.query(
            IndexName='user_id-index',  # Replace with your GSI name
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )

        payments = response.get('Items', [])

        # Transform DynamoDB response into a list of payments
        payment_list = [{'payment_id': int(row['payment_id']), 'card_number': int(row['card_number']), 'expiration_month': int(row['expiration_month']), 'expiration_year': int(row['expiration_year']), 'cvc': int(row['cvc'])} for row in payments]

        return jsonify({'payments': payment_list}), 200,  resp_headers

    except Exception as e:
        print(e)
        return jsonify({'error': 'An error occurred while retrieving user payments'}), 500,  resp_headers

    
@users_bp.route('/redeem-loyalty-points', methods=['POST'])
@protected_route
def handle_redeem_loyalty_points():
    data = request.get_json()

    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    points_to_redeem = data.get('points_to_redeem')

    if not points_to_redeem:
        return jsonify({'error': 'points_to_redeem is required'}), 400,  resp_headers

    success, message = redeem_loyalty_points(user_id, points_to_redeem)

    if success:
        return jsonify({'message': message}), 200,  resp_headers
    else:
        return jsonify({'error': message}), 400,  resp_headers
    
@users_bp.route('/get-loyalty-points', methods=['GET'])
@protected_route
def handle_get_loyalty_points():

    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    if not user_id:
        return jsonify({'error': 'User ID is required as a query parameter'}), 400,  resp_headers

    loyalty_points = get_loyalty_points(user_id)

    if loyalty_points is not None:
        return jsonify({'loyalty_points': int(loyalty_points)}), 200,  resp_headers
    else:
        return jsonify({'error': 'An error occurred while retrieving loyalty points'}), 500,  resp_headers
