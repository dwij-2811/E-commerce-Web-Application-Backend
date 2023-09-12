from flask import request, jsonify, Blueprint
from routes.utility import *
import bcrypt
import psycopg2
import datetime
from app import db_params
from functools import wraps

users_bp = Blueprint('users', __name__)

def protected_route(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        decoded_token = verify_token(token)

        if not decoded_token:
            return jsonify({'error': 'Invalid token'}), 401

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
        return jsonify({'error': 'Both email and password are required'}), 400

    hashed_password = hash_password(password)

    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        sql = "INSERT INTO users (email, password_hash, first_name, last_name) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (email, hashed_password, first_name, last_name))

        connection.commit()

        cursor.close()
        connection.close()
    except Exception as e:
        return jsonify({'error': f'An error occurred while registering the user {e}'}), 500

    return jsonify({'message': 'User registered successfully'}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Both email and password are required'}), 400

    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        cursor.execute("SELECT user_id, password_hash, current_login_attempt FROM users WHERE email = %s", (email,))
        result = cursor.fetchone()

        if result is None:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Invalid email'}), 401

        user_id, stored_hashed_password, current_login_attempt = result

        if current_login_attempt >= 5:
            if check_reset_token_status(email) == False:
                reset_token = generate_reset_token()
                expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

                if store_reset_token_in_database(email, reset_token, expiration_time):

                    if send_password_reset_email(email, reset_token):
                        cursor.close()
                        connection.close()
                        return jsonify({'error': 'Account temporarily locked. Too many login attempts.'}), 403
                    else:
                        cursor.close()
                        connection.close()
                        return jsonify({'error': 'Error resetting password'}), 404
                else:
                    cursor.close()
                    connection.close()
                    return jsonify({'error': 'Error resetting password'}), 404
            cursor.close()
            connection.close()
            return jsonify({'error': 'Account temporarily locked. Too many login attempts.'}), 403
    
        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
            current_login_attempt = 0
            auth_token = generate_auth_token(user_id)
        else:
            current_login_attempt += 1

        cursor.execute("UPDATE users SET current_login_attempt = %s WHERE email = %s", (current_login_attempt, email))
        connection.commit()

        cursor.close()
        connection.close()

        if current_login_attempt != 0:

            return jsonify({'error': 'Invalid password'}), 401

        return jsonify({'user_id': user_id, 'auth_token': auth_token, 'message': 'Login successful'}), 200

    except Exception as e:
        return jsonify({'error': f'An error occurred while authenticating the user {e}'}), 500


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
            return jsonify({'message': 'Password reset email sent'}), 200
        else:
            return jsonify({'error': 'Error resetting password'}), 404

    else:
        return jsonify({'error': 'Error resetting password'}), 404

@users_bp.route('/reset-password', methods=['POST'])
def handle_reset_password():
    data = request.get_json()
    reset_token = data.get('resetToken')
    new_password = data.get('newPassword')

    if not reset_token or not new_password:
        return jsonify({'error': 'Reset_token, and new_password are required'}), 400

    result = reset_password(reset_token, new_password)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 400
    else:
        return jsonify({'error': 'An unknown error occurred'}), 500

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
        return jsonify({'error': 'Missing required fields'}), 400

    result = store_user_address(user_id, address_line1, address_line2, city, state, postal_code, country)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 500

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
        return jsonify({'error': 'Missing required fields'}), 400

    result = store_user_payment(user_id, card_number, expiration_month, expiration_year, cvc)

    if result['status'] == 'success':
        return jsonify({'message': result['message']}), 200
    elif result['status'] == 'error':
        return jsonify({'error': result['message']}), 500

@users_bp.route('/get-user-addresses', methods=['GET'])
@protected_route
def get_user_addresses():
    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM user_addresses WHERE user_id = %s", (user_id,))
        addresses = cursor.fetchall()

        cursor.close()
        connection.close()

        address_list = [{'address_id': row[0], 'address_line1': row[1], 'address_line2': row[2], 'city': row[3], 'state': row[4], 'postal_code': row[5]} for row in addresses]

        return jsonify({'addresses': address_list}), 200

    except Exception as e:
        return jsonify({'error': 'An error occurred while retrieving user addresses'}), 500

@users_bp.route('/get-user-payments', methods=['GET'])
@protected_route
def get_user_payments():
    decoded_token = request.context.get('decoded_token')
    user_id = decoded_token.get('user_id')

    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM user_payments WHERE user_id = %s", (user_id,))
        payments = cursor.fetchall()

        cursor.close()
        connection.close()

        payment_list = [{'payment_id': row[0], 'card_number': row[1], 'expiration_month': row[2], 'expiration_year': row[3], 'cvc': row[4]} for row in payments]

        return jsonify({'payments': payment_list}), 200

    except Exception as e:
        return jsonify({'error': 'An error occurred while retrieving user payments'}), 500
    
@users_bp.route('/check-phonenumber', methods=['post'])
def check_phonenumber():
    data = request.get_json()
    if check_sms_sandbox_phone_number(data.get('phoneNumber')):
        return jsonify({'success': "Phone number already added"})
    else:
        if send_otp("+1" + data.get('phoneNumber')) == True:
            return jsonify({'error': "Phone number needs verification!"}), 401
        else:
            return jsonify({'error': "Error sending otp"}), 500
        
@users_bp.route('/verify-otp', methods=['post'])
def verify_otp():
    data = request.get_json()
    if verify_opt("+1" + data.get('phoneNumber'), data.get('otp')):
        return jsonify({'success': "Phone number added"})
    else:
        return jsonify({'error': "Error verifying OTP"}), 401