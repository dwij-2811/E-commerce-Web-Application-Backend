from flask import request, jsonify, Blueprint
import psycopg2
import random
from app import db_params

def generate_id():
    return random.randint(1, 999)

customizations_bp = Blueprint('customizations', __name__)

@customizations_bp.route('/<int:customizations_id>', methods=['PUT'])
def edit_customizations(customizations_id):
    try:
        edited_customizations = request.json
        if not edited_customizations:
            return jsonify({"error": "No customizations data provided"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = """
        UPDATE customizations
        SET name = %s, addons = %s, required = %s, minimum = %s, maximum = %s, multiple = %s, isinstock = %s
        WHERE id = %s;
        """
        cursor.execute(update_query, (
            edited_customizations["name"],
            edited_customizations["addOns"],
            edited_customizations["required"],
            edited_customizations["minimum"],
            edited_customizations["maximum"],
            edited_customizations["multiple"],
            edited_customizations["isInStock"],
            customizations_id
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product edited successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customizations_bp.route('/instock/<int:customizations_id>', methods=['PUT'])
def update_customizations_status(customizations_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = "UPDATE customizations SET isInStock = %s WHERE id = %s;"
        cursor.execute(update_query, (new_status, customizations_id))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product isInStock updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customizations_bp.route('/<int:customizations_id>', methods=['DELETE'])
def delete_customizations(customizations_id):
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        delete_query = "DELETE FROM customizations WHERE id = %s;"
        cursor.execute(delete_query, (customizations_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customizations_bp.route('', methods=['POST'])
def add_customizations():
    try:
        new_customizations = request.json
        if not new_customizations:
            return jsonify({"error": "No customizations data provided"}), 400

        while True:
            try:
                connection = psycopg2.connect(**db_params)
                cursor = connection.cursor()

                insert_query = """
                INSERT INTO customizations (id, name, addons, required, minimum, maximum, multiple, isinstock)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                """
                cursor.execute(insert_query, (
                    new_customizations["id"],
                    new_customizations["name"],
                    new_customizations["addOns"],
                    new_customizations["required"],
                    new_customizations["minimum"],
                    new_customizations["maximum"],
                    new_customizations["multiple"],
                    new_customizations["isInStock"]
                ))
                new_customizations_id = cursor.fetchone()[0]
                connection.commit()

                cursor.close()
                connection.close()

                return jsonify({"message": "Customizations added successfully", "customizations_id": new_customizations_id})
            except psycopg2.IntegrityError as e:
                connection.rollback()  # Roll back the failed transaction
                new_customizations["id"] = generate_id()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@customizations_bp.route('', methods=['GET'])
def get_all_customization():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        select_query = "SELECT * FROM customizations ORDER BY name;"
        cursor.execute(select_query)
        customization = cursor.fetchall()

        cursor.close()
        connection.close()

        customization_list = []
        for customizations in customization:
            customizations_dict = {
                "id": customizations[0],
                "name": customizations[1],
                "addOns": customizations[2],
                "required": customizations[3],
                "minimum": customizations[4],
                "maximum": customizations[5],
                "multiple": customizations[6],
                "isInStock": customizations[7]
            }
            customization_list.append(customizations_dict)

        return jsonify(customization_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500