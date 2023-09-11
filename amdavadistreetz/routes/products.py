from flask import request, jsonify, Blueprint
import random, time
from app import dynamodb, resp_headers
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

def generate_id():
    return random.randint(1, 999)

product_table = dynamodb.Table('Products')

products_bp = Blueprint('products', __name__)

@products_bp.route('/<int:product_id>', methods=['PUT'])
def edit_product(product_id):
    try:
        edited_product = request.json
        if not edited_product:
            return jsonify({"error": "No product data provided"}), 400,  resp_headers

        update_expression = (
            "SET #name = :name, #price = :price, #quantity = :quantity, "
            "#description = :description, #image = :image, "
            "#customizations = :customizations, #spiciness = :spiciness, "
            "#isinstock = :isinstock"
        )
        expression_attribute_names = {
            "#name": "name",
            "#price": "price",
            "#quantity": "quantity",
            "#description": "description",
            "#image": "image",
            "#customizations": "customizations",
            "#spiciness": "spiciness",
            "#isinstock": "isinstock"
        }
        expression_attribute_values = {
            ":name": edited_product["name"],
            ":price": edited_product["price"],
            ":quantity": edited_product["quantity"],
            ":description": edited_product["description"],
            ":image": edited_product["image"],
            ":customizations": edited_product["customizations"],
            ":spiciness": edited_product["spiciness"],
            ":isinstock": edited_product["isInStock"]
        }

        response = product_table.update_item(
            Key={'id': product_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'
        )

        updated_product = response.get('Attributes', None)
        if updated_product:
            return jsonify(updated_product), 200,  resp_headers
        else:
            return jsonify({"message": "Product not found"}), 404
    except ClientError as e:
        return jsonify({"message": "Error updating product"}), 500,  resp_headers 
    
@products_bp.route('/instock/<int:product_id>', methods=['PUT'])
def update_product_status(product_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400,  resp_headers

        response = product_table.update_item(
            Key={'id': product_id},
            UpdateExpression="SET #statusAttr = :newStatus",
            ExpressionAttributeNames={"#statusAttr": "isInStock"},
            ExpressionAttributeValues={":newStatus": new_status},
            ReturnValues='ALL_NEW'  # Return the updated item
        )

        updated_product = response.get('Attributes', None)
        if updated_product:
            return jsonify(updated_product), 200,  resp_headers
        else:
            return jsonify({"message": "Product not found"}), 404
    except ClientError as e:
        return jsonify({"message": "Error updating product status"}), 500,  resp_headers
    
@products_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        response = product_table.delete_item(
            Key={'id': product_id}
        )

        # Check if the delete operation was successful
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            return jsonify({"message": "Product deleted successfully"}), 200,  resp_headers
        else:
            return jsonify({"message": "Product not found"}), 404
    except ClientError as e:
        return jsonify({"message": "Error deleting product"}), 500,  resp_headers
    
@products_bp.route('', methods=['POST'])
def add_product():
    try:
        new_product = request.json
        if not new_product:
            return jsonify({"error": "No product data provided"}), 400,  resp_headers
        
        response = product_table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(new_product["name"].lower())
        )
        
        while True:
            try:
                if response['Count'] == 0:
                    response = product_table.put_item(
                        Item={
                            "id": new_product["id"],
                            "name": new_product["name"],
                            "price": new_product["price"],
                            "quantity": new_product["quantity"],
                            "description": new_product["description"],
                            "image": new_product["image"],
                            "customizations": new_product["customizations"],
                            "spiciness": new_product["spiciness"],
                            "isInStock": new_product["isInStock"]
                        },
                        ConditionExpression="attribute_not_exists(id)"
                    )

                    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                        return jsonify({"message": "Product added successfully", "product_id": new_product["id"]}), 200,  resp_headers
                else:
                    return jsonify({"error": "Duplicate name found."}), 400,  resp_headers

            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    new_product["id"] = generate_id()
                else:
                    return jsonify({"message": "Error adding product"}), 500,  resp_headers 

            time.sleep(1)

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers

@products_bp.route('', methods=['GET'])
def get_all_products():
    try:
            
        response = product_table.scan()

        products = response.get('Items', [])

        products_list = []
        for product in products:
            product_dict = {
                "id": int(product["id"]),
                "name": product["name"],
                "price": float(product["price"]),
                "quantity": int(product["quantity"]),
                "description": product.get("description", ""),
                "image": product.get("image", ""),
                "customizations": [int(customization) for customization in product.get("customizations", [])],
                "spiciness": int(product["spiciness"]),
                "isInStock": bool(product["isInStock"])
            }
            products_list.append(product_dict)

        return jsonify(products_list), 200,  resp_headers
    except Exception as e:
        return jsonify({"message": f"Error fetching products {e}"}), 500,  resp_headers