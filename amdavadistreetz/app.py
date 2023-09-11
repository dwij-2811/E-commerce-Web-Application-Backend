
from flask import request, jsonify
import logging, boto3
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask import Response
from werkzeug.utils import secure_filename
import random, string, stripe
from datetime import datetime, timedelta
from flask_lambda import FlaskLambda
import jwt
from botocore.exceptions import ClientError

stripe.api_key = "" ##Sripe Key Here...

secret_key = '' #Auth Secret Key Here...

app = FlaskLambda(__name__)
bcrypt = Bcrypt(app)
CORS(app, send_wildcard=True, origins=["*"])

s3 = boto3.client("s3")

app.config['S3_BUCKET'] = "amdavadistreetzimages"
app.config['S3_LOCATION'] = 'http://{}.s3.amazonaws.com/'.format("amdavadistreetzimages")

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

loyalty_table = dynamodb.Table('UsersLoyalty')

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

resp_headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET,DELETE,PUT",
}

def configure_app():
    from routes.orders import orders_bp
    from routes.products import products_bp
    from routes.customizations import customizations_bp
    from routes.analytics import analytics_bp
    from routes.addons import addons_bp
    from routes.categories import categories_bp
    from routes.users import users_bp
    
    app.register_blueprint(orders_bp, url_prefix='/orders')
    CORS(orders_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(products_bp, url_prefix='/products')
    CORS(products_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(customizations_bp, url_prefix='/customizations')
    CORS(customizations_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(analytics_bp, url_prefix='/analytics')
    CORS(analytics_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(addons_bp, url_prefix='/addons')
    CORS(addons_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(categories_bp, url_prefix='/categories')
    CORS(categories_bp, send_wildcard=True, origins=["*"])
    app.register_blueprint(users_bp, url_prefix='/users')
    CORS(users_bp, send_wildcard=True, origins=["*"])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def upload_file_to_s3(file, bucket_name):
    try:
        s3.upload_fileobj(
            file,
            bucket_name,
            file.filename,
            ExtraArgs={
                "ContentType": file.content_type
            }
        )
    except Exception as e:
        print("Something Happened: ", e)
        return e
    return "{}{}".format(app.config["S3_LOCATION"], file.filename)

@app.before_request
def basic_authentication():
    if request.method.lower() == 'options':
        return Response()
    
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', "OPTIONS,POST,GET,DELETE,PUT")
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response
    
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

@app.route('/placeorder', methods=['POST'])
def placeorder():
    try:
        content = request.json
        if not content:
            return jsonify({"error": "No checkout data provided"}), 400,  resp_headers
        OrderId = generate_order_id()

        user_id = None
        message = None

        Email = content["email"].strip()
        payment = content["payment"]

        token = request.headers.get('Authorization')

        if token:
            decoded_token = verify_token(token)

            if not decoded_token:
                return jsonify({'error': 'Invalid token'}), 401, resp_headers
            
            user_id = decoded_token.get('user_id')

        if payment['paymentMethod'] == "online":
            payment_status = process_payment(payment['token'], payment['orderTotal'], OrderId, Email)

            if payment_status[0] == True:
                paymentId = payment_status[1]
            
            else:
                return payment_status[1], 403

        else:
            paymentId = ""
        
        OrderdOn = get_current_time()


        orders_table = dynamodb.Table('Orders')
        payments_table = dynamodb.Table('Payments')
        items_table = dynamodb.Table('OrderItems')

        content["order"]["orderId"] = OrderId
        content["order"]['userId'] = user_id
        content["order"]['orderedOn'] = OrderdOn
        content["order"]['orderStatus'] = "Submitted"
        content["order"]['estimatedWaitTime'] = str(current_time + timedelta(minutes=estimated_wait_time_minutes))
        content["payment"]['paymentId'] = paymentId

        orders_table.put_item(Item=content["order"])

        payments_table.put_item(Item=content["payment"])
        
        for item in content["cart"]["items"]:
            item_data = {
                "orderId": OrderId,
                "itemOrderd": item["name"],
                "itemTotal": item["itemTotal"],
                "itemQuantity": item["quantity"],
                "itemSpiciness": item["spiciness"]
            }
            response = items_table.put_item(Item=item_data)

            for addon in item.get("addOns", []):
                addon_data = {
                    "ItemID": response['Attributes']['ItemID'],
                    "name": addon["name"],
                    "price": addon["price"]
                }

                response = items_table.put_item(Item=addon_data)

        current_time = datetime.now()
        estimated_wait_time_minutes = 15

        if user_id is not None:
            points_to_add = int(content["order"]["orderTotal"]) * 100
            success, message = add_loyalty_points(user_id, points_to_add)
            
            if success:
                message += f" {points_to_add} loyalty points added."
                
        # socketio.emit('new_order', content, namespace='/')
        
        return jsonify(
            message = f'Order placed successfully.{message}',
            orderId = OrderId,
            estimatedWaitTime = current_time + timedelta(minutes=estimated_wait_time_minutes),
        ), 200, resp_headers

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@app.route('/', methods=['POST'])
def hello():
    return jsonify(
            message = f'Api working well!',
        ), 200, resp_headers

configure_app()