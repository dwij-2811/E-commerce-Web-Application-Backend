from flask import request, jsonify, Blueprint
import psycopg2, logging
from app import db_params
from routes.utility import send_sms_notification

def log_warning():
    logging.basicConfig(filename='logs.log', format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
    logging.error("Exception occurred", exc_info=True)

orders_bp = Blueprint('orders', __name__)
    
@orders_bp.route('/getallorders', methods=['GET'])
def GetAllOrders():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        limit = int(request.args.get('limit', default=10))
        offset = int(request.args.get('offset', default=0))

        select_all_orders_query = """
        SELECT o.OrderID, o.Email, o."First Name", o."Last Name", o."billingAddress", o."city", o."province", o."postalCode", o."phone", o."Ordered On", o."Order Status", o."Estimated Wait Time",
            p."paymentMethod", p."paymentId", p."orderTotal", p."subTotal", p."tax", p."tip", 
            i."Item Ordered", i."Item Total", i."Item Quantity", i."Item Spiciness",
            a."Addon Name", a."Addon Price"
        FROM orders o
        JOIN ordersItems i ON o.OrderID = i.OrderID
        LEFT JOIN ordersItemsAddOns a ON i.ItemID = a.ItemID
        JOIN payments p ON o.OrderID = p.OrderID
        ORDER BY o."Ordered On" DESC
        LIMIT %s OFFSET %s;

        """
        cursor.execute(select_all_orders_query, (limit, offset))
        orders = cursor.fetchall()

        count_query = "SELECT COUNT(*) FROM orders;"
        cursor.execute(count_query)
        total_orders = cursor.fetchone()[0]

        select_query = 'SELECT SUM("subTotal") FROM payments;'
        cursor.execute(select_query)
        total_amount = cursor.fetchone()[0]

        select_query = 'SELECT SUM("tip") FROM payments;'
        cursor.execute(select_query)
        total_tip = cursor.fetchone()[0]

        select_query = 'SELECT SUM("tax") FROM payments;'
        cursor.execute(select_query)
        total_tax = cursor.fetchone()[0]

        cursor.close()
        connection.close()

        orders_ = {}

        if not total_orders:
            total_orders = 0
        if not total_amount:
            total_amount = 0

        orders_['totalOrders'] = total_orders
        orders_['totalAmount'] = int(total_amount)
        orders_list = []

        current_order_id = None
        current_order = None

        for row in orders:
            if row[0] != current_order_id:

                if current_order is not None:
                    orders_list.append(current_order)
                current_order_id = row[0]
                payment = {
                    "paymentMethod": row[12], 
                    "paymentId": row[13], 
                    "orderTotal": float(row[14]), 
                    "subTotal": float(row[15]), 
                    "tax": float(row[16]), 
                    "tip": float(row[17])
                }

                current_order = {
                    "id": row[0],
                    "email": row[1],
                    "firstName": row[2],
                    "lastName": row[3],
                    "billingAddress": row[4],
                    "city": row[5],
                    "province": row[6],
                    "postalCode": row[7],
                    "phone": row[8],
                    "orderedOn": row[9],
                    "orderStatus": row[10],
                    "estimatedWaitTime": int(row[11]),
                    "payment": payment,
                    "items": []
                }

            item = {
                "itemOrderd": row[18],
                "itemTotal": float(row[19]),
                "itemQuantity": int(row[20]),
                "itemSpiciness": int(row[21]),
                "addOns": []
            }
            if row[22]:
                addon = {
                    "name": row[22],
                    "price": float(row[23])
                }
                item["addOns"].append(addon)
            current_order["items"].append(item)
            
        if current_order is not None:
            orders_list.append(current_order)

        orders_['orders'] = orders_list

        return jsonify(orders_), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    
@orders_bp.route('/getorder/<string:order_id>', methods=['GET'])
def get_order(order_id):
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        select_order_query = """
        SELECT o.OrderID, o.Email, o."First Name", o."Last Name", o."billingAddress", o."city", o."province", o."postalCode", o."phone", o."Ordered On", o."Order Status", o."Estimated Wait Time",
               p."paymentMethod", p."paymentId", p."orderTotal", p."subTotal", p."tax", p."tip", 
               i."Item Ordered", i."Item Total", i."Item Quantity", i."Item Spiciness",
               a."Addon Name", a."Addon Price"
        FROM Orders o
        JOIN ordersItems i ON o.OrderID = i.OrderID
        LEFT JOIN ordersItemsAddOns a ON i.ItemID = a.ItemID
        JOIN payments p ON o.OrderID = p.OrderID
        WHERE o.OrderID = %s;
        """

        cursor.execute(select_order_query, (order_id,))
        order_data = cursor.fetchall()

        cursor.close()
        connection.close()

        if not order_data:
            return jsonify({"message": "Order not found"}), 404
        
        print (order_data)

        payment = {
            "paymentMethod": order_data[0][12],
            "paymentId": order_data[0][13],
            "orderTotal": float(order_data[0][14]), 
            "subTotal": float(order_data[0][15]), 
            "tax": float(order_data[0][16]), 
            "tip": float(order_data[0][17])
        }

        order = {
            "id": order_data[0][0],
            "email": order_data[0][1],
            "firstName": order_data[0][2],
            "lastName": order_data[0][3],
            "billingAddress": order_data[0][4],
            "city": order_data[0][5],
            "province": order_data[0][6],
            "postalCode": order_data[0][7],
            "phone": order_data[0][8],
            "orderedOn": order_data[0][9],
            "orderStatus": order_data[0][10],
            "estimatedWaitTime": int(order_data[0][11]),
            "payment": payment,
            "items": []
        }

        for row in order_data:
            item = {
                "itemOrderd": row[18],
                "itemTotal": float(row[19]),
                "itemQuantity": int(row[20]),
                "itemSpiciness": int(row[21]),
                "addOns": []
            }
            if row[22]:
                addon = {
                    "name": row[22],
                    "price": float(row[23])
                }
                item["addOns"].append(addon)
            order["items"].append(item)

        return jsonify(order), 200
    except Exception as e:
        log_warning()
        return jsonify({"error": str(e)}), 500
    
@orders_bp.route('/updateorder/<string:orderId>', methods=['PUT'])
def UpdateOrder(orderId):
    try:
        content = request.json
        new_order_status = content['OrderStatus']
        new_estimated_wait_time = content['EstimatedWaitTime']

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = """
            UPDATE orders
            SET "Order Status" = %s, "Estimated Wait Time" = %s
            WHERE OrderID = %s;
            """

        cursor.execute(update_query, (new_order_status, new_estimated_wait_time, orderId))
        connection.commit()

        cursor.close()
        connection.close()

        try:
            if new_order_status == "Ready":
                send_sms_notification(content['phoneNumber'], "order_ready")
            elif new_order_status == "Completed":
                send_sms_notification(content['phoneNumber'], "order_pickedup")
        except:
            pass

        return jsonify(
                new_estimated_wait_time = new_estimated_wait_time,
                new_order_status = new_order_status
            ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500