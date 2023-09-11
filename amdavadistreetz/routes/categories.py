from flask import request, jsonify, Blueprint
import random
from app import dynamodb, resp_headers
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

def generate_id():
    return random.randint(1, 999)

categories_table = dynamodb.Table('Categories')

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/<int:category_id>', methods=['PUT'])
def edit_category(category_id):
    try:
        edited_category = request.json
        if not edited_category:
            return jsonify({"error": "No category data provided"}), 400,  resp_headers

        response = categories_table.update_item(
            Key={
                "id": category_id
            },
            UpdateExpression="SET #name = :name, products = :products",
            ExpressionAttributeNames={
                "#name": "name"
            },
            ExpressionAttributeValues={
                ":name": edited_category["name"],
                ":products": edited_category["products"]
            },
            ReturnValues="UPDATED_NEW"
        )

        if response.get("Attributes"):
            return jsonify({"message": "category edited successfully"}), resp_headers
        else:
            return jsonify({"message": "category edite failed"}), 400,  resp_headers

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@categories_bp.route('/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        response = categories_table.delete_item(
            Key={
                "id": category_id
            }
        )

        if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
            return jsonify({"message": "category deleted successfully"}), resp_headers
        else:
            return jsonify({"message": "category delete failed"}), 400,  resp_headers

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@categories_bp.route('', methods=['POST'])
def add_category():
    try:
        new_category = request.json
        if not new_category:
            return jsonify({"error": "No category data provided"}), 400,  resp_headers
        
        response = categories_table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(new_category["name"].lower())
        )

        while True:
            try:
                if response['Count'] == 0:
                    response = categories_table.put_item(
                        Item={
                            "id": new_category["id"],
                            "name": new_category["name"],
                            "products": new_category["products"]
                        },
                        ConditionExpression="attribute_not_exists(id)"
                    )

                    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
                        return jsonify({"message": "category added successfully"}), resp_headers
                    else:
                        return jsonify({"message": "category add failed"}), 400,  resp_headers
                else:
                    return jsonify({"error": "Duplicate name found."}), 400,  resp_headers
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    new_category["id"] = generate_id()
                else:
                    return jsonify({"message": "Error adding category"}), 500,  resp_headers 

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers

@categories_bp.route('', methods=['GET'])
def get_all_categories():
    try:
        response = categories_table.scan()

        categories = response.get('Items', [])

        categories_list = [
            {
                "id": int(category["id"]),
                "name": category["name"],
                "products": [int(product) for product in category.get("products", [])]
            }
            for category in categories
        ]

        return jsonify(categories_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers