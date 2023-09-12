from flask import request, jsonify, Blueprint
import psycopg2
import random
from app import db_params

def generate_id():
    return random.randint(1, 999)

addons_bp = Blueprint('addons', __name__)

@addons_bp.route('', methods=['POST'])
def add_addon():
    try:
        new_addon = request.json
        if not new_addon:
            return jsonify({"error": "No addon data provided"}), 400

        while True:
            try:
                connection = psycopg2.connect(**db_params)
                cursor = connection.cursor()

                insert_query = """
                INSERT INTO addons (id, name, price, isinstock)
                VALUES (%s, %s, %s, %s) RETURNING id;
                """
                cursor.execute(insert_query, (
                    new_addon["id"],
                    new_addon["name"].lower(),
                    new_addon["price"],
                    new_addon["isInStock"]
                ))
                new_addon_id = cursor.fetchone()[0]
                connection.commit()

                cursor.close()
                connection.close()

                return jsonify({"message": "Addon added successfully", "addon_id": new_addon_id})
            except psycopg2.IntegrityError as e:
                connection.rollback()  # Roll back the failed transaction
                new_addon["id"] = generate_id()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@addons_bp.route('', methods=['GET'])
def get_all_addons():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        select_query = "SELECT * FROM addons ORDER BY name;"
        cursor.execute(select_query)
        addons = cursor.fetchall()

        cursor.close()
        connection.close()

        addons_list = []
        for addon in addons:
            addon_dict = {
                "id": addon[0],
                "name": addon[1],
                "price": float(addon[2]),
                "isInStock": addon[3]
            }
            addons_list.append(addon_dict)

        return jsonify(addons_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@addons_bp.route('/<int:addon_id>', methods=['PUT'])
def edit_addon(addon_id):
    try:
        edited_addon = request.json
        if not edited_addon:
            return jsonify({"error": "No addon data provided"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = """
        UPDATE addons
        SET name = %s, price = %s, isinstock = %s
        WHERE id = %s;
        """
        cursor.execute(update_query, (
            edited_addon["name"],
            edited_addon["price"],
            edited_addon["isInStock"],
            addon_id
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Addon edited successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@addons_bp.route('/<int:addon_id>', methods=['DELETE'])
def delete_addon(addon_id):
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        delete_query = "DELETE FROM addons WHERE id = %s;"
        cursor.execute(delete_query, (addon_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Addon deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@addons_bp.route('/instock/<int:addon_id>', methods=['PUT'])
def update_addon_status(addon_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = "UPDATE addons SET isInStock = %s WHERE id = %s;"
        cursor.execute(update_query, (new_status, addon_id))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product isInStock updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500