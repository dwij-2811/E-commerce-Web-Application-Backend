from flask import request, jsonify, Blueprint
import random, psycopg2
from app import db_params

def generate_id():
    return random.randint(1, 999)

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/<int:category_id>', methods=['PUT'])
def edit_category(category_id):
    try:
        edited_category = request.json
        if not edited_category:
            return jsonify({"error": "No category data provided"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = """
        UPDATE categories
        SET name = %s, products = %s
        WHERE id = %s;
        """
        cursor.execute(update_query, (
            edited_category["name"],
            edited_category["products"],
            category_id
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "category edited successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        delete_query = "DELETE FROM categories WHERE id = %s;"
        cursor.execute(delete_query, (category_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "category deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@categories_bp.route('', methods=['POST'])
def add_category():
    try:
        new_category = request.json
        print (new_category)
        if not new_category:
            return jsonify({"error": "No category data provided"}), 400

        while True:
            try:
                connection = psycopg2.connect(**db_params)
                cursor = connection.cursor()

                insert_query = """
                INSERT INTO categories (id, name, products, position)
                VALUES (%s, %s, %s, %s) RETURNING id;
                """
                cursor.execute(insert_query, (
                    new_category["id"],
                    new_category["name"],
                    new_category["products"],
                    new_category["position"],
                ))
                new_category_id = cursor.fetchone()[0]
                connection.commit()

                cursor.close()
                connection.close()

                return jsonify({"message": "category added successfully", "category_id": new_category_id})
            except psycopg2.IntegrityError as e:
                connection.rollback()  # Roll back the failed transaction
                new_category["id"] = generate_id()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@categories_bp.route('', methods=['GET'])
def get_all_categories():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        select_query = "SELECT * FROM categories ORDER BY position;"
        cursor.execute(select_query)
        categories = cursor.fetchall()

        cursor.close()
        connection.close()

        categories_list = []
        for category in categories:
            category_dict = {
                "id": category[0],
                "name": category[1],
                "products": category[2],
                "position": category[3],
            }
            categories_list.append(category_dict)

        return jsonify(categories_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@categories_bp.route('/update_category_positions', methods=['POST'])
def update_category_positions():
    try:
        new_positions = request.get_json()

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        for category in new_positions:
            cursor.execute(
                "UPDATE categories SET position = %s WHERE id = %s",
                (category["position"], category["id"])
            )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'message': 'Category positions updated successfully'}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500