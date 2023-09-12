from flask import request, jsonify, Blueprint
import psycopg2
import random
from app import db_params

def generate_id():
    return random.randint(1, 999)

products_bp = Blueprint('products', __name__)

@products_bp.route('/<int:product_id>', methods=['PUT'])
def edit_product(product_id):
    try:
        edited_product = request.json
        if not edited_product:
            return jsonify({"error": "No product data provided"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = """
        UPDATE products
        SET name = %s, price = %s, quantity = %s, description = %s,
            image = %s, customizations = %s, spiciness = %s, isinstock = %s
        WHERE id = %s;
        """
        cursor.execute(update_query, (
            edited_product["name"],
            edited_product["price"],
            edited_product["quantity"],
            edited_product["description"],
            edited_product["image"],
            edited_product["customizations"],
            edited_product["spiciness"],
            edited_product["isInStock"],
            product_id
        ))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product edited successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route('/instock/<int:product_id>', methods=['PUT'])
def update_product_status(product_id):
    try:
        new_status = request.json.get('isInStock')
        if new_status is None:
            return jsonify({"error": "Missing 'isInStock' parameter"}), 400

        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        update_query = "UPDATE products SET isInStock = %s WHERE id = %s;"
        cursor.execute(update_query, (new_status, product_id))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product isInStock updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route('/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        delete_query = "DELETE FROM products WHERE id = %s;"
        cursor.execute(delete_query, (product_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({"message": "Product deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route('', methods=['POST'])
def add_product():
    try:
        new_product = request.json
        if not new_product:
            return jsonify({"error": "No product data provided"}), 400

        while True:
            try:
                connection = psycopg2.connect(**db_params)
                cursor = connection.cursor()

                insert_query = """
                INSERT INTO products (id, name, price, quantity, description, image, customizations, spiciness, isinstock)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                """
                cursor.execute(insert_query, (
                    new_product["id"],
                    new_product["name"],
                    new_product["price"],
                    new_product["quantity"],
                    new_product["description"],
                    new_product["image"],
                    new_product["customizations"],
                    new_product["spiciness"],
                    new_product["isInStock"]
                ))
                new_product_id = cursor.fetchone()[0]
                connection.commit()

                cursor.close()
                connection.close()

                return jsonify({"message": "Product added successfully", "product_id": new_product_id})
            except psycopg2.IntegrityError as e:
                connection.rollback()  # Roll back the failed transaction
                new_product["id"] = generate_id()

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@products_bp.route('', methods=['GET'])
def get_all_products():
    try:
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        select_query = "SELECT * FROM products ORDER BY name;"
        cursor.execute(select_query)
        products = cursor.fetchall()

        cursor.close()
        connection.close()

        products_list = []
        for product in products:
            product_dict = {
                "id": product[0],
                "name": product[1],
                "price": float(product[2]),
                "quantity": product[3],
                "description": product[4],
                "image": product[5],
                "customizations": product[6],
                "spiciness": product[7],
                "isInStock": product[8]
            }
            products_list.append(product_dict)

        return jsonify(products_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500