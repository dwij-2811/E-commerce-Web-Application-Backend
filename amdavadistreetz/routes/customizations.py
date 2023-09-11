from flask import request, jsonify, Blueprint
import random, time
from app import dynamodb, resp_headers
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

def generate_id():
    return random.randint(1, 999)

customizations_table = dynamodb.Table('Customizations')

customizations_bp = Blueprint('customizations', __name__)

@customizations_bp.route('/<int:customizations_id>', methods=['PUT'])
def edit_customizations(customizations_id):
    try:
        edited_customizations = request.json
        if not edited_customizations:
            return jsonify({"error": "No customizations data provided"}), 400,  resp_headers

        response = customizations_table.update_item(
            Key={
                "id": customizations_id
            },
            UpdateExpression="SET #name = :name, addons = :addons, required = :required, minimum = :minimum, maximum = :maximum, multiple = :multiple, isInStock = :isInStock",
            ExpressionAttributeNames={
                "#name": "name" 
            },
            ExpressionAttributeValues={
                ":name": edited_customizations["name"],
                ":addons": edited_customizations["addOns"],
                ":required": edited_customizations["required"],
                ":minimum": edited_customizations["minimum"],
                ":maximum": edited_customizations["maximum"],
                ":multiple": edited_customizations["multiple"],
                ":isInStock": edited_customizations["isInStock"]
            },
            ReturnValues="UPDATED_NEW"
        )

        if response.get("Attributes"):
            return jsonify({"message": "Product edited successfully"}), resp_headers
        else:
            return jsonify({"message": "Product edit failed"}), 400,  resp_headers

    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@customizations_bp.route('/instock/<int:customizations_id>', methods=['PUT'])
def update_customizations_status(customizations_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400,  resp_headers

        response = customizations_table.update_item(
            Key={
                "id": customizations_id
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
    
@customizations_bp.route('/<int:customizations_id>', methods=['DELETE'])
def delete_customizations(customizations_id):
    try:
        response = customizations_table.delete_item(
            Key={
                "id": customizations_id
            }
        )

        if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
            return jsonify({"message": "Product deleted successfully"}), resp_headers
        else:
            return jsonify({"message": "Product delete failed"}), 400,  resp_headers
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers
    
@customizations_bp.route('', methods=['POST'])
def add_customizations():
    try:
        new_customizations = request.json
        if not new_customizations:
            return jsonify({"error": "No customizations data provided"}), 400,  resp_headers

        if new_customizations["minimum"] == 0:
            required = False
        else:
            required = True

        response = customizations_table.query(
            IndexName='name-index',
            KeyConditionExpression=Key('name').eq(new_customizations["name"].lower())
        )

        while True:
            try:
                if response['Count'] == 0:
                    response = customizations_table.put_item(
                        Item={
                            "id": new_customizations["id"],
                            "name": new_customizations["name"],
                            "addons": new_customizations["addOns"],
                            "required": new_customizations["required"],
                            "minimum": required,
                            "maximum": new_customizations["maximum"],
                            "multiple": new_customizations["multiple"],
                            "isInStock": new_customizations["isInStock"]
                        },
                        ConditionExpression="attribute_not_exists(id)"
                    )

                    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
                        return jsonify({"message": "Customizations added successfully"}), resp_headers
                    else:
                        return jsonify({"message": "Customizations add failed"}), 400,  resp_headers
                else:
                    return jsonify({"error": "Duplicate name found."}), 400,  resp_headers
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
                    new_customizations["id"] = generate_id()
                else:
                    return jsonify({"message": "Error adding customizations"}), 500,  resp_headers 

            time.sleep(1)
                
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers

@customizations_bp.route('', methods=['GET'])
def get_all_customization():
    try:
        response = customizations_table.scan()

        customizations = response.get('Items', [])

        customization_list = [
            {
                "id": int(customization["id"]),
                "name": customization["name"],
                "addOns": [int(addon) for addon in customization.get("addons", [])],
                "required": customization["required"],
                "minimum": int(customization["minimum"]),
                "maximum": int(customization["maximum"]),
                "multiple": int(customization["multiple"]),
                "isInStock": customization["isInStock"]
            }
            for customization in customizations
        ]

        return jsonify(customization_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500,  resp_headers