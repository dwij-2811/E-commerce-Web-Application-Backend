
from flask import Flask, request, jsonify
import logging, boto3, psycopg2, os
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
# from flask_socketio import SocketIO
import random, string, stripe
from datetime import datetime, timedelta
import jwt
from botocore.exceptions import ClientError

stripe.api_key = "" ##Sripe Key Here...

secret_key = '' #Auth Secret Key Here...

db_params = {
    "dbname": "",
    "user": "",
    "password": "",
    "host": "",
    "port": 5432,
}

app = Flask(__name__)
bcrypt = Bcrypt(app)
# socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app, send_wildcard=True, origins=["*"])

s3 = boto3.client("s3")

sns = boto3.client('sns', region_name='us-west-2')

app.config['S3_BUCKET'] = "amdavadistreetzimages"
app.config['S3_LOCATION'] = 'http://{}.s3.amazonaws.com/'.format("amdavadistreetzimages")

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

loyalty_table = dynamodb.Table('UsersLoyalty')

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def configure_app():
    from routes.orders import orders_bp
    from routes.products import products_bp
    from routes.customizations import customizations_bp
    from routes.analytics import analytics_bp
    from routes.addons import addons_bp
    from routes.categories import categories_bp
    from routes.users import users_bp
    
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(customizations_bp, url_prefix='/customizations')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    app.register_blueprint(addons_bp, url_prefix='/addons')
    app.register_blueprint(categories_bp, url_prefix='/categories')
    app.register_blueprint(users_bp, url_prefix='/users')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def upload_file_to_s3(file, bucket_name):
    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            file.filename,
            ExtraArgs={
                "ContentType": file.content_type    #Set appropriate content type as per the file
            }
        )
    except Exception as e:
        print("Something Happened: ", e)
        return e
    return "{}{}".format(app.config["S3_LOCATION"], file.filename)
    
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            file.filename = secure_filename(file.filename)
            output = upload_file_to_s3(file, app.config["S3_BUCKET"])
            return jsonify({'message': 'File uploaded successfully', 'path': str(output)})
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    except Exception as e:
        print(f"Error uploading Image: {e}")
        return jsonify({'error': f"Error uploading Image: {e}"}), 500
    
def generate_order_id(length=5):
    characters = string.ascii_uppercase + string.digits
    order_id = ''.join(random.choice(characters) for _ in range(length))
    return order_id

def get_current_time():
    current_timestamp = datetime.now()
    formatted_timestamp = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return formatted_timestamp

def process_payment(token, amount, OrderId, email):
    try:
        charge = stripe.Charge.create(
            amount= round((amount * 100)), # Amount in cents
            currency='cad',
            source=token,
            description='OrderID: ' + OrderId,
            receipt_email=email,
        )
        return True, charge['id']
    except stripe.error.CardError as e:
        # Payment failed, handle the error
        return False, jsonify({'error': str(e)})

def log_warning():
    logging.basicConfig(filename='logs.log', format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    logging.error("Exception occurred", exc_info=True)

def verify_token(token):
    try:
        decoded_token = jwt.decode(token, secret_key, algorithms=['HS256'])
        return decoded_token
    except jwt.ExpiredSignatureError:
        return None  # Token has expired
    except jwt.InvalidTokenError:
        return None  # Invalid token
    
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
    
def send_sms_notification(phoneNumber, Message):
    try:
        response = sns.publish(
            PhoneNumber=phoneNumber,
            Message=Message,
        )
        if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
            return True
        else:
            print (response)
            return False
    except Exception as e:
        return e
    
def sms_notification(phoneNumber, status):
    match status:
        case 'order_placed':
            message = "Thank you for placing your order."
        case 'order_ready':
            message = "Your order is ready to be picked up."
        case 'order_pickedup':
            message = "Thank you for your business. Please leave us a 5 star review."

    return send_sms_notification(phoneNumber, message)

@app.route('/placeorder', methods=['POST'])
def placeorder():
    try:
        content = request.json
        if not content:
            return jsonify({"error": "No checkout data provided"}), 400
        OrderId = generate_order_id()

        Email = content["customerDetails"]["email"].strip()
        FirstName = content["customerDetails"]["firstName"]
        LastName = content["customerDetails"]["lastName"]
        billingAddress = content["customerDetails"]["billingAddress"]
        city = content["customerDetails"]["city"]
        province = content["customerDetails"]["province"]
        postalCode = content["customerDetails"]["postalCode"]
        phone = content["customerDetails"]["phone"]

        cart = content["cart"]
        payment = content["payment"]

        if payment['paymentMethod'] == "online":
            payment_status = process_payment(payment['token'], payment['orderTotal'], OrderId, Email)

            if payment_status[0] == True:
                paymentId = payment_status[1]
            
            else:
                return payment_status[1], 403

        else:
            paymentId = ""
        
        OrderdOn = get_current_time()

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        insert_order_query = """
        INSERT INTO Orders (OrderID, Email, "First Name", "Last Name", "billingAddress", "city", "province", "postalCode", "phone", "Ordered On", "Order Status", "Estimated Wait Time")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING OrderID;
        """
        cursor.execute(insert_order_query, (OrderId, Email, FirstName, LastName, billingAddress, city, province, postalCode, phone, OrderdOn, "Submitted", 15))
        order_id = cursor.fetchone()[0]

        OrderTotal = payment["orderTotal"]
        PaymentMethod = payment["paymentMethod"]
        subTotal = payment["subTotal"]
        tax = payment["tax"]
        tip = payment["tip"]

        insert_item_query = """
        INSERT INTO payments (OrderID, "paymentMethod", "paymentId", "orderTotal", "subTotal", "tax", "tip")
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_item_query, (order_id, PaymentMethod, paymentId, OrderTotal, subTotal, tax, tip))

        for item in cart['items']:
            item_ordered = item["name"]
            item_total = item["itemTotal"]
            item_quantity = item["quantity"]
            item_spiciness = item["spiciness"]
            addons = item["addOns"]

            insert_item_query = """
            INSERT INTO ordersItems (OrderID, "Item Ordered", "Item Total", "Item Quantity", "Item Spiciness")
            VALUES (%s, %s, %s, %s, %s)
            RETURNING ItemID;
            """
            cursor.execute(insert_item_query, (order_id, item_ordered, item_total, item_quantity, item_spiciness))
            item_id = cursor.fetchone()[0]

            for addon in addons:
                addon_name = addon["name"]
                addon_price = addon["price"]

                insert_addon_query = """
                INSERT INTO ordersItemsAddOns (ItemID, "Addon Name", "Addon Price")
                VALUES (%s, %s, %s);
                """
                cursor.execute(insert_addon_query, (item_id, addon_name, addon_price))

        connection.commit()

        cursor.close()
        connection.close()

        current_time = datetime.now()
        estimated_wait_time_minutes = 15

        try:
            sms_notification(phone, "order_placed")
        except:
            pass

        return jsonify(
            orderId = OrderId,
            estimatedWaitTime = current_time + timedelta(minutes=estimated_wait_time_minutes),
        ), 200

    except psycopg2.Error as e:
        error_message = f"PostgreSQL error: {e.pgerror}" if e.pgerror else "Unknown PostgreSQL error"
        return jsonify({"error": error_message}), 500
    except Exception as e:
        log_warning()
        return jsonify({"error": str(e)}), 500

    
@app.route('/', methods=['GET'])
def hello():
    return jsonify(
            message = f'Hello World.',
        ), 200
        
if 'dwij0' in str(os.environ):
    pass
else:
    configure_app()

if __name__ == '__main__':
   configure_app()
# # #    socketio.run(app, debug=True, host='0.0.0.0')
   app.run(debug = True, host='0.0.0.0')