from flask import request, jsonify, Blueprint
import random, time, json
from app import dynamodb, resp_headers
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

def generate_id():
    return random.randint(1, 999)


addons_table = dynamodb.Table('Addons')

addons_bp = Blueprint('addons', __name__)


@addons_bp.route('', methods=['POST'])
def add_addon():
    try:
        new_addon = request.json
        if not new_addon:
            return jsonify({"error": "No addon data provided"}), 400,  resp_headers
        
        response = addons_table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(new_addon["name"].lower())
        )
        while True:
            try:
                if response['Count'] == 0:
                    response = addons_table.put_item(
                        Item={
                            "id": new_addon["id"],
                            "name": new_addon["name"].lower(),
                            "price": new_addon["price"],
                            "isInStock": new_addon["isInStock"]
                        },
                        ConditionExpression="attribute_not_exists(id)"
                    )

                    return jsonify({"message": "Addon added successfully"}), resp_headers
                else:
                    return jsonify({"error": "Duplicate name found."}), 400,  resp_headers
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    new_addon["id"] = generate_id()
                else:
                    return jsonify({"message": "Error adding addon"}), 500,  resp_headers 

            time.sleep(1)

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers


@addons_bp.route('', methods=['GET'])
def get_all_addons():
    try:
        response = addons_table.scan()

        addons = response.get('Items', [])

        addons_list = [
            {
                "id": int(addon["id"]),
                "name": addon["name"],
                "price": float(addon["price"]),
                "isInStock": addon["isInStock"]
            }
            for addon in addons
        ]

        return jsonify(addons_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers


@addons_bp.route('/<int:addon_id>', methods=['PUT'])
def edit_addon(addon_id):
    try:
        edited_addon = request.json
        if not edited_addon:
            return jsonify({"error": "No addon data provided"}), 400,  resp_headers

        response = addons_table.update_item(
            Key={
                "id": addon_id
            },
            UpdateExpression="SET #name = :name, price = :price, isInStock = :isInStock",
            ExpressionAttributeNames={
                "#name": "name" 
            },
            ExpressionAttributeValues={
                ":name": edited_addon["name"],
                ":price": edited_addon["price"],
                ":isInStock": edited_addon["isInStock"]
            },
            ReturnValues="UPDATED_NEW"
        )

        if response.get("Attributes"):
            return jsonify({"message": "Addon edited successfully"}), resp_headers
        else:
            return jsonify({"message": "Error updating addons"}), 400,  resp_headers

        
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers


@addons_bp.route('/<int:addon_id>', methods=['DELETE'])
def delete_addon(addon_id):
    try:
        response = addons_table.delete_item(
            Key={
                "id": addon_id
            }
        )

        if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",  # Allow requests from any origin
                },
                "body": json.dumps({"message": "Addon deleted successfully"})
            }
            # return jsonify({"message": "Addon deleted successfully"}), resp_headers
        else:
            return {
                "statusCode": 400,
                "headers": {
                    "Access-Control-Allow-Origin": "*",  # Allow requests from any origin
                },
                "body": json.dumps({"message": "Addon deleted failed"})
            }
        
        # jsonify({"message": "Addon deleted failed"}), 400,  resp_headers

    except Exception as e:
        return {
                "statusCode": 500,
                "headers": {
                    "Access-Control-Allow-Origin": "*",  # Allow requests from any origin
                },
                "body": json.dumps({"error": str(e)})
            }
    
    # jsonify({"error": str(e)}), 500,  resp_headers


@addons_bp.route('/instock/<int:addon_id>', methods=['PUT'])
def update_addon_status(addon_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400,  resp_headers

        response = addons_table.update_item(
            Key={
                "id": addon_id
            },
            UpdateExpression="SET isInStock = :new_status",
            ExpressionAttributeValues={
                ":new_status": new_status
            },
            ReturnValues="UPDATED_NEW"
        )

        if response.get("Attributes"):
            return jsonify({"message": "Product isInStock updated successfully"}), resp_headers
        else:
            return jsonify({"message": "Product isInStock update failed"}), 400,  resp_headers
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
