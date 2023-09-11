from flask import request, jsonify, Blueprint
import logging
from botocore.exceptions import ClientError
from app import dynamodb, resp_headers

orders_table = dynamodb.Table('Orders')

def log_warning():
    logging.basicConfig(filename='logs.log', format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    logging.error("Exception occurred", exc_info=True)

orders_bp = Blueprint('orders', __name__)

def query_dynamodb_orders(limit, offset):
    try:
        scan_params = {'Limit': limit}

        # Check if offset is greater than 0 and include ExclusiveStartKey if needed
        if offset > 0:
            scan_params['ExclusiveStartKey'] = {'orderId': offset}
        response = orders_table.scan(
            **scan_params
        )

        orders = response.get('Items', [])
        total_orders = response.get('Count', 0)

        total_amount, total_tip, total_tax = 0, 0, 0

        for order in orders:
            payment = order.get('payment', {})
            total_amount += float(payment.get('orderTotal', 0))
            total_tip += float(payment.get('tip', 0))
            total_tax += float(payment.get('tax', 0))

        return orders, total_orders, total_amount, total_tip, total_tax
    except ClientError as e:
        return None, 0, 0, 0, 0

def convert_order_item(row):
    return {
        "id": row['orderId']['S'],
        "userId": row['userId']['S'],
        "email": row['email']['S'],
        "firstName": row['firstName']['S'],
        "lastName": row['lastName']['S'],
        "billingAddress": row['billingAddress']['S'],
        "city": row['city']['S'],
        "province": row['province']['S'],
        "postalCode": row['postalCode']['S'],
        "phone": row['phone']['S'],
        "orderedOn": row['orderedOn']['S'],
        "orderStatus": row['orderStatus']['S'],
        "estimatedWaitTime": row['estimatedWaitTime']['N'],
    }

def convert_payment_item(row):
    return {
        "paymentMethod": row['paymentMethod']['S'],
        "paymentId": row['paymentId']['S'],
        "orderTotal": float(row['orderTotal']['N']),
        "subTotal": float(row['subTotal']['N']),
        "tax": float(row['tax']['N']),
        "tip": float(row['tip']['N'])
    }

def convert_item_item(row):
    return {
        "itemOrderd": row['itemOrderd']['S'],
        "itemTotal": float(row['itemTotal']['N']),
        "itemQuantity": int(row['itemQuantity']['N']),
        "itemSpiciness": int(row['itemSpiciness']['N']),
    }

def convert_addon_item(row):
    return {
        "name": row['name']['S'],
        "price": float(row['price']['N'])
    }
    
@orders_bp.route('/getallorders', methods=['GET'])
def GetAllOrders():
    try:
        limit = int(request.args.get('limit', default=10))
        offset = int(request.args.get('offset', default=0))

        orders, total_orders, total_amount, total_tip, total_tax = query_dynamodb_orders(limit, offset)

        orders_ = {
            "totalOrders": total_orders,
            "totalAmount": int(total_amount),
            "orders": []
        }

        if orders:
            current_order_id = None
            current_order = None

            for order in orders:
                if 'orderId' in order and order['orderId']['S'] != current_order_id:
                    if current_order is not None:
                        orders_['orders'].append(current_order)

                    current_order_id = order['orderId']['S']
                    current_order = convert_order_item(order)
                    current_order['payment'] = convert_payment_item(order)
                    current_order['items'] = []

                item = convert_item_item(order)
                if 'name' in order:
                    addon = convert_addon_item(order)
                    item['addOns'] = [addon]

                current_order['items'].append(item)

            if current_order is not None:
                orders_['orders'].append(current_order)

        return jsonify(orders_), 200,  resp_headers
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    
def get_order_by_id(order_id):
    try:
        response = orders_table.get_item(
            Key={'orderId': {'S': order_id}}
        )

        order_item = response.get('Item')
        if order_item:
            order = convert_dynamodb_item_to_order(order_item)
            return order
        else:
            return None
    except ClientError as e:
        return None

def convert_dynamodb_item_to_order(order_item):
    return {
        "id": order_item['orderId']['S'],
        "userId": order_item.get('userId', {}).get('S', ''),
        "email": order_item.get('email', {}).get('S', ''),
        "firstName": order_item.get('firstName', {}).get('S', ''),
        "lastName": order_item.get('lastName', {}).get('S', ''),
        "billingAddress": order_item.get('billingAddress', {}).get('S', ''),
        "city": order_item.get('city', {}).get('S', ''),
        "province": order_item.get('province', {}).get('S', ''),
        "postalCode": order_item.get('postalCode', {}).get('S', ''),
        "phone": order_item.get('phone', {}).get('S', ''),
        "orderedOn": order_item.get('orderedOn', {}).get('S', ''),
        "orderStatus": order_item.get('orderStatus', {}).get('S', ''),
        "estimatedWaitTime": int(order_item.get('estimatedWaitTime', {}).get('N', '0')),
        "payment": convert_dynamodb_item_to_payment(order_item),
        "items": convert_dynamodb_items_to_items(order_item.get('items', {}).get('L', []))
    }

def convert_dynamodb_item_to_payment(order_item):
    payment_item = order_item.get('Payment', {})
    return {
        "paymentMethod": payment_item.get('paymentMethod', {}).get('S', ''),
        "paymentId": payment_item.get('paymentId', {}).get('S', ''),
        "orderTotal": float(payment_item.get('orderTotal', {}).get('N', '0')),
        "subTotal": float(payment_item.get('subTotal', {}).get('N', '0')),
        "tax": float(payment_item.get('tax', {}).get('N', '0')),
        "tip": float(payment_item.get('tip', {}).get('N', '0'))
    }

def convert_dynamodb_items_to_items(items):
    converted_items = []
    for item in items:
        converted_item = {
            "itemOrderd": item.get('itemOrderd', {}).get('S', ''),
            "itemTotal": float(item.get('itemTotal', {}).get('N', '0')),
            "itemQuantity": int(item.get('itemQuantity', {}).get('N', '0')),
            "itemSpiciness": int(item.get('itemSpiciness', {}).get('N', '0')),
            "addOns": convert_dynamodb_items_to_addons(item.get('addOns', {}).get('L', []))
        }
        converted_items.append(converted_item)
    return converted_items

def convert_dynamodb_items_to_addons(addons):
    converted_addons = []
    for addon in addons:
        converted_addon = {
            "name": addon.get('name', {}).get('S', ''),
            "price": float(addon.get('price', {}).get('N', '0'))
        }
        converted_addons.append(converted_addon)
    return converted_addons
    
@orders_bp.route('/getorder/<string:order_id>', methods=['GET'])
def get_order(order_id):
    try:
        order = get_order_by_id(order_id)
        if order:
            return jsonify(order), 200,  resp_headers
        else:
            return jsonify({"message": "Order not found"}), 404
    except Exception as e:
        log_warning()
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@orders_bp.route('/updateorder/<string:orderId>', methods=['PUT'])
def UpdateOrder(orderId):
    try:
        content = request.json
        new_order_status = content['OrderStatus']

        update_expression = "SET #statusAttr = :newStatus"
        expression_attribute_names = {"#statusAttr": "OrderStatus"}
        expression_attribute_values = {":newStatus": {"S": new_order_status}}

        # Update the order status in DynamoDB
        response = orders_table.update_item(
            Key={'orderId': {'S': orderId}},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'  # Return the updated item
        )

        updated_order = response.get('Attributes', None)
        if updated_order:
            return jsonify(updated_order), 200,  resp_headers
        else:
            return jsonify({"message": "Order not found"}), 404
    except ClientError as e:
        return jsonify({"message": "Error updating order status"}), 500,  resp_headers  # Handle error here

