import psycopg2
import random
import string
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import bcrypt
import jwt, boto3
from app import db_params, secret_key
from botocore.exceptions import ClientError

sns = boto3.client('sns')

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
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users WHERE email = %s", (email,))
        count = cur.fetchone()[0]

        cur.close()
        conn.close()

        return count > 0

    except Exception as e:
        print(f"Error checking email existence: {e}")
        return False

def store_reset_token_in_database(email, reset_token, expiration_time):
    try:
        conn = psycopg2.connect(**db_params)

        cur = conn.cursor()

        cur.execute("UPDATE users SET reset_token = %s, reset_token_expiration = %s WHERE email = %s", (reset_token, expiration_time, email))

        conn.commit()

        cur.close()
        conn.close()

        return True

    except Exception as e:
        return False

def send_password_reset_email(email, reset_token):
    # Email configuration (replace with your own SMTP server and email credentials)
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    sender_email = ''
    sender_password = ''

    # Email content
    subject = 'Password Reset'
    body = f'Click the link below to reset your password:\n\nhttps://www.amdavadistreetz.com/reset-password?token={reset_token}'
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

        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        cur.execute("SELECT reset_token, reset_token_expiration FROM users WHERE email = %s", (email,))
        result = cur.fetchone()

        if result:
            reset_token, expiration_time = result

            if expiration_time >= datetime.datetime.utcnow():
                return True
            else:
                return False
        else:
            return False

    except Exception as e:
        return False

def reset_password(reset_token, new_password):
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        cur.execute("SELECT reset_token_expiration FROM users WHERE reset_token = %s", (reset_token,))
        result = cur.fetchone()

        if result:
            expiration_time = result[0]

            if expiration_time >= datetime.datetime.utcnow():
                hashed_password = hash_password(new_password)

                cur.execute("UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expiration = NULL WHERE reset_token = %s", (hashed_password, reset_token))
                conn.commit()
                return {'status': 'success', 'message': 'Password reset successfully!'}
            else:
                return {'status': 'error', 'message': 'Invalid or expired reset token!'}
        else:
            return {'status': 'error', 'message': 'Invalid or expired reset token!'}

    except Exception as e:
        print(f"Error resetting password: {e}")
        return {'status': 'error', 'message': 'An error occurred while resetting the password'}

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')

def store_user_address(user_id, address_line1, address_line2, city, state, postal_code, country):
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO user_addresses (user_id, address_line1, address_line2, city, state, postal_code, country)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, address_line1, address_line2, city, state, postal_code, country)
        )

        conn.commit()

        cur.close()
        conn.close()

        return {'status': 'success', 'message': 'User address stored successfully'}

    except Exception as e:
        print(f"Error storing user address: {e}")
        return {'status': 'error', 'message': 'An error occurred while storing the user address'}

def store_user_payment(user_id, card_number, expiration_month, expiration_year, cvc):
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO user_payments (user_id, card_number, expiration_month, expiration_year, cvc)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, card_number, expiration_month, expiration_year, cvc)
        )

        conn.commit()

        cur.close()
        conn.close()

        return {'status': 'success', 'message': 'User payment information stored successfully'}

    except Exception as e:
        print(f"Error storing user payment information: {e}")
        return {'status': 'error', 'message': 'An error occurred while storing user payment information'}
    
def send_sms_notification(phoneNumber, Message):
    try:
        response = sns.publish(
            PhoneNumber="+1" + phoneNumber,
            Message=Message,
        )
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            return True
        else:
            print (response)
            return False
    except Exception as e:
        print (e)
        return e
    
def sms_notification(phoneNumber, status):
    if status == 'order_placed':
        message = "Thank you for placing your order."
    elif status == 'order_ready':
        message = "Your order is ready to be picked up."
    elif status == 'order_pickedup':
        message = "Thank you for your business. Please leave us a 5 star review."

    return send_sms_notification(phoneNumber, message)

def send_otp(phoneNumber):
    response = sns.create_sms_sandbox_phone_number(
        PhoneNumber=phoneNumber,
        LanguageCode='en-US'
    )
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return True
    else:
        print (response)
        return False

def verify_opt(phoneNumber, otp):
    try:
        response = sns.verify_sms_sandbox_phone_number(
            PhoneNumber=phoneNumber,
            OneTimePassword=otp
        )
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            return True
        else:
            return None
    except sns.exceptions.VerificationException:
        return False
    
def check_sms_sandbox_phone_number(phoneNumber):
    NextToken = None
    while NextToken != False:
        if not NextToken:
            response = sns.list_sms_sandbox_phone_numbers(
            )
            try:
                NextToken = response["NextToken"]
            except:
                NextToken = False
        else:
            response = sns.list_sms_sandbox_phone_numbers(
                NextToken=NextToken,
            )
            try:
                NextToken = response["NextToken"]
            except:
                NextToken = False
        if phoneNumber in str(response["PhoneNumbers"]):
            if any(numbers["PhoneNumber"] == "+1"+phoneNumber and numbers["Status"] != "Pending" for numbers in response["PhoneNumbers"]):
                return True
            else:
                return False
    
    return False
