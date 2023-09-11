import random
import string
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import jwt
from app import dynamodb, secret_key
from botocore.exceptions import ClientError

user_table = dynamodb.Table('Users')
address_table = dynamodb.Table('UserAddresses')
payment_table  = dynamodb.Table('UserPayments')
loyalty_table = dynamodb.Table('UsersLoyalty')

def verify_token(token):
    try:
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        return decoded_token
    except jwt.ExpiredSignatureError:
        return None  # Token has expired
    except jwt.InvalidTokenError:
        return None  # Invalid token

def generate_auth_token(user_id):

    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    
    payload = {
        'user_id': user_id,
        'exp': expiration_time
    }
    
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token

def generate_reset_token():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def email_exists_in_database(email):
    try:
        response = user_table.get_item(
            Key={
                'email': email
            },
            ProjectionExpression="email"
        )

        # Check if the user was found in DynamoDB
        user = response.get('Item', None)
        return user is not None

    except Exception as e:
        print(f"Error checking email existence: {e}")
        return False
    
def store_reset_token_in_database(email, reset_token, expiration_time):
    try:
        # Update the reset_token and reset_token_expiration attributes in DynamoDB
        response = user_table.update_item(
            Key={'email': email},
            UpdateExpression="SET reset_token = :reset_token, reset_token_expiration = :reset_token_expiration",
            ExpressionAttributeValues={
                ":reset_token": reset_token,
                ":reset_token_expiration": expiration_time
            }
        )

        # Check if the update operation was successful
        return response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200
    except ClientError as e:
        return False
    
def send_password_reset_email(email, reset_token):
    # Email configuration (replace with your own SMTP server and email credentials)
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    sender_email = 'your_email@gmail.com'
    sender_password = 'your_email_password'

    # Email content
    subject = 'Password Reset'
    body = f'Click the link below to reset your password:\n\nhttps://example.com/reset-password?token={reset_token}'
    recipient_email = email

    try:
        context = smtplib.SMTP(smtp_server, smtp_port)
        context.starttls()

        context.login(sender_email, sender_password)

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        context.sendmail(sender_email, recipient_email, msg.as_string())

        context.quit()

        return True

    except Exception as e:
        return False
    
def check_reset_token_status(email):
    try:
        response = user_table.get_item(
            Key={'email': email},
            ProjectionExpression="reset_token, reset_token_expiration"
        )

        user_item = response.get('Item')
        if user_item:
            reset_token = user_item.get('reset_token')
            expiration_time = user_item.get('reset_token_expiration')
            
            if reset_token and expiration_time:
                current_time = datetime.now(timezone.utc)
                if expiration_time >= current_time:
                    return True

    except ClientError as e:
        pass  # Handle errors here

    return False

def reset_password(reset_token, new_password, bcrypt):
    try:
        # Query DynamoDB to retrieve the reset_token_expiration for the user
        response = user_table.query(
            IndexName='reset_token-index',
            KeyConditionExpression='reset_token = :reset_token',
            ExpressionAttributeValues={
                ':reset_token': reset_token
            },
            ProjectionExpression='reset_token_expiration'
        )

        # Check if the user was found and has reset_token_expiration attribute
        items = response.get('Items')
        if items:
            item = items[0]
            expiration_time = item.get('reset_token_expiration')
            
            # Check if the expiration time is in the future
            current_time = datetime.now(timezone.utc)
            if expiration_time >= current_time:
                hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

                # Update the user's password and remove reset token in DynamoDB
                user_table.update_item(
                    Key={'email': item['email']},
                    UpdateExpression='SET password_hash = :password_hash, reset_token = :reset_token, reset_token_expiration = :reset_token_expiration',
                    ExpressionAttributeValues={
                        ':password_hash': hashed_password,
                        ':reset_token': None,
                        ':reset_token_expiration': None
                    }
                )

                return {'status': 'success', 'message': 'Password reset successfully!'}
            else:
                return {'status': 'error', 'message': 'Invalid or expired reset token!'}
        else:
            return {'status': 'error', 'message': 'No reset token found!'}

    except ClientError as e:
        print(f"Error resetting password: {e}")
        return {'status': 'error', 'message': 'An error occurred while resetting the password'}

def hash_password(password, bcrypt):
    hashed_password = bcrypt.generate_password_hash(password.encode('utf-8'))
    return hashed_password.decode('utf-8')

def store_user_address(user_id, address_line1, address_line2, city, state, postal_code, country):
    try:
        address_table.put_item(
            Item={
                'user_id': user_id,
                'address_line1': address_line1,
                'address_line2': address_line2,
                'city': city,
                'state': state,
                'postal_code': postal_code,
                'country': country
            }
        )

        return {'status': 'success', 'message': 'User address stored successfully'}
    except ClientError as e:
        print(f"Error storing user address: {e}")
        return {'status': 'error', 'message': 'An error occurred while storing the user address'}

    
def store_user_payment(user_id, card_number, expiration_month, expiration_year, cvc):
    try:
        payment_table.put_item(
            Item={
                'user_id': user_id,
                'card_number': card_number,
                'expiration_month': expiration_month,
                'expiration_year': expiration_year,
                'cvc': cvc
            }
        )

        return {'status': 'success', 'message': 'User payment information stored successfully'}
    except ClientError as e:
        print(f"Error storing user payment information: {e}")
        return {'status': 'error', 'message': 'An error occurred while storing user payment information'}


def redeem_loyalty_points(user_id, points_to_redeem):
    try:
        response = loyalty_table.get_item(
            Key={'user_id': user_id},
            ProjectionExpression='points'
        )

        user_item = response.get('Item')
        if user_item:
            current_points = user_item.get('points', 0)

            if current_points < points_to_redeem:
                return False, "Insufficient points"

            new_points = current_points - points_to_redeem

            loyalty_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET points = :new_points, points_redeemed = points_redeemed + :points_to_redeem',
                ExpressionAttributeValues={
                    ':new_points': new_points,
                    ':points_to_redeem': points_to_redeem
                }
            )

            return True, "Points redeemed successfully"
        else:
            return False, "User not found"
    except ClientError as e:
        print(f"Error redeeming loyalty points: {e}")
        return False, "An error occurred while redeeming points"

    
def add_loyalty_points(user_id, points_to_add):
    try:
        response = loyalty_table.get_item(
            Key={'user_id': user_id},
            ProjectionExpression='lifetime_points'
        )

        user_item = response.get('Item')
        if user_item:
            lifetime_points = user_item.get('lifetime_points', 0)

            new_lifetime_points = lifetime_points + points_to_add

            loyalty_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET points = points + :points_to_add, lifetime_points = :new_lifetime_points',
                ExpressionAttributeValues={
                    ':points_to_add': points_to_add,
                    ':new_lifetime_points': new_lifetime_points
                }
            )

            return True, "Points added successfully"
        else:
            return False, "User not found"
    except ClientError as e:
        print(f"Error adding lifetime points: {e}")
        return False, "An error occurred while adding points"

    
def get_loyalty_points(user_id):
    try:
        response = loyalty_table.get_item(
            Key={'user_id': user_id},
            ProjectionExpression='points'
        )

        user_item = response.get('Item')
        if user_item:
            loyalty_points = user_item.get('points', 0)
            return loyalty_points

    except ClientError as e:
        print(f"Error retrieving loyalty points: {e}")

    return None
