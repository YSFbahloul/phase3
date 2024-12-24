from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mysql_connector import MySQL

app = Flask(__name__)
CORS(app)

# Update MySQL connection details
app.config['MYSQL_USER'] = 'root'  # MySQL username
app.config['MYSQL_PASSWORD'] = 'Abdo980756@'  # MySQL password
app.config['MYSQL_DATABASE'] = 'toolsdatabase'  # MySQL database name
app.config['MYSQL_HOST'] = 'db'  # MySQL container name or Docker network name

mysql = MySQL(app)

@app.route('/register', methods=['POST'])
def register():
    print("Register endpoint called")
    data = request.json
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    password = data.get('password')
    role = data.get('role')  # The role should be provided in the request

    if not all([name, email, phone, password, role]):
        return jsonify({'error': 'Please provide all required fields'}), 400

    conn = mysql.connection
    cursor = conn.cursor()

    # Begin transaction
    conn.start_transaction()

    try:
        # Insert the new user into Users table
        cursor.execute("""
            INSERT INTO Users (name, email, phone, password, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, phone, password, role))
        user_id = cursor.lastrowid  # Retrieve the ID of the newly inserted user

        if role == 'courier':
            # Insert the new courier into the Couriers table with the default courier name 'DHL'
            cursor.execute("""
                INSERT INTO Couriers (courier_id, courier_name)
                VALUES (%s, %s)
            """, (user_id, 'DHL'))

        conn.commit()  # Commit the transaction if all operations were successful
        return jsonify({'message': 'User registered successfully'}), 201

    except Exception as e:
        print("Error during registration:", e)
        conn.rollback()  # Roll back the transaction on error
        return jsonify({'error': str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route('/login', methods=['POST'])
def login():
    print("Login endpoint called")
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'error': 'Please provide email and password'}), 400

    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, name, role FROM Users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()

        if user:
            user_id, name, role = user

            # Check if already logged in, and update role if already logged
            cursor.execute("SELECT user_id FROM LoggedInUsers WHERE user_id = %s", (user_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE LoggedInUsers SET role = %s WHERE user_id = %s", (role, user_id))
            else:
                cursor.execute("INSERT INTO LoggedInUsers (user_id, role) VALUES (%s, %s)", (user_id, role))

            conn.commit()
            return jsonify(
                {'message': 'Login successful', 'user': {'user_id': user_id, 'name': name, 'role': role}}), 200
        else:
            return jsonify({'error': 'Invalid email or password'}), 401
    except Exception as e:
        conn.rollback()
        print("Error during login:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/logout', methods=['POST'])
def logout():
    print("Logout endpoint called")
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user ID'}), 400

    conn = mysql.connection
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM LoggedInUsers WHERE user_id = %s", (user_id,))
        conn.commit()
        if cursor.rowcount:
            return jsonify({'message': 'Successfully logged out'}), 200
        else:
            return jsonify({'message': 'No session found or already logged out'}), 404
    except Exception as e:
        print("Error during logout:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/create_order', methods=['POST'])
def create_order():
    print("Create Order endpoint called")
    data = request.json
    product_id = data.get('product_id')
    delivery_address = data.get('delivery_address')

    if not all([product_id, delivery_address]):
        return jsonify({"message": "Product ID and delivery address are required"}), 400

    conn = mysql.connection
    cursor = conn.cursor()

    # Ensure a non-courier is making the order
    cursor.execute("SELECT user_id FROM LoggedInUsers WHERE role != 'courier' ORDER BY login_time DESC LIMIT 1")
    logged_in_user = cursor.fetchone()

    if not logged_in_user:
        return jsonify({"message": "No logged-in user or invalid role"}), 400

    user_id = logged_in_user[0]
    cursor.execute("SELECT email FROM Users WHERE user_id = %s", (user_id,))
    user_data = cursor.fetchone()
    email = user_data[0] if user_data else None
    if not email:
        return jsonify({"message": "Email for user not found"}), 404
    cursor.execute("INSERT INTO Orders (user_id, email, product_id, delivery_address) VALUES (%s, %s, %s, %s)",
                   (user_id, email, product_id, delivery_address))
    conn.commit()
    return jsonify({"message": "Order created successfully"}), 201
    cursor.close()
    conn.close()


@app.route('/my_orders', methods=['GET'])
def get_my_orders():
    print("Fetch Orders endpoint called")
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id FROM LoggedInUsers LIMIT 1")
    logged_in_user = cursor.fetchone()

    if not logged_in_user:
        return jsonify({"message": "No logged-in user found"}), 404

    user_id = logged_in_user['user_id']
    cursor.execute("SELECT * FROM Orders WHERE user_id = %s", (user_id,))
    orders = cursor.fetchall()

    if not orders:
        return jsonify({"message": "No orders found for the user"}), 404

    return jsonify({"orders": orders}), 200


@app.route('/order/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        if order:
            return jsonify(order), 200
        else:
            return jsonify({'message': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/order/<int:order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)  # Ensure the cursor returns dictionary objects
    try:
        cursor.execute("SELECT status FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()  # Fetch one record; this should now be a dictionary

        if order is None:
            return jsonify({'message': 'Order not found'}), 404

        if order['status'] == 'pending':  # Access status directly from the dictionary
            cursor.execute("UPDATE Orders SET status = 'cancelled' WHERE order_id = %s", (order_id,))
            conn.commit()
            return jsonify({'message': 'Order cancelled successfully'}), 200
        else:
            return jsonify({'message': 'Order cannot be cancelled, not in pending status'}), 409
    except Exception as e:
        conn.rollback()  # Rollback in case of any error
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/order/<int:order_id>/accept', methods=['PUT'])
def accept_order(order_id):
    print("Accept Order endpoint called")
    conn = mysql.connection
    cursor = conn.cursor()
    try:
        # Update the order status to 'accepted' for the given order_id
        cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", ("accepted", order_id))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'message': 'Order not found or already accepted'}), 404

        return jsonify({'message': 'Order status updated to accepted'}), 200
    except Exception as e:
        print("Error updating order status:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/order/<int:order_id>/reject', methods=['PUT'])
def reject_order(order_id):
    print("Accept Order endpoint called")
    conn = mysql.connection
    cursor = conn.cursor()
    try:
        # Update the order status to 'accepted' for the given order_id
        cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", ("accepted", order_id))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'message': 'Order not found or already accepted'}), 404

        return jsonify({'message': 'Order status updated to rejection'}), 200
    except Exception as e:
        print("Error updating order status:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/update_order_status_delivered', methods=['POST'])
def update_order_status_delivered():
    data = request.get_json()
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({"message": "Order ID is required"}), 400

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)  # Ensure the cursor returns dictionary objects

    try:
        print("Checking courier credentials...")
        # Ensure only logged-in couriers can perform this action
        cursor.execute("SELECT user_id FROM LoggedInUsers WHERE role = 'courier'")
        courier = cursor.fetchone()

        if not courier:
            return jsonify({"message": "Action allowed only for logged-in couriers"}), 403

        print("Fetching order...")
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            return jsonify({"message": "Order not found"}), 404

        if order['status'] == "Canceled":
            return jsonify({"message": "Order is already Canceled"}), 403

        print("Updating order status...")
        cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", ("Delivered", order_id))
        conn.commit()

        return jsonify({"message": "Order status updated to Delivered"}), 200

    except Exception as e:
        conn.rollback()
        print("Error updating order status:", e)
        return jsonify({"message": "Error updating order status", "error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route('/update_order_status_inTransit', methods=['POST'])
def update_order_status_inTransit():
    data = request.get_json()
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({"message": "Order ID is required"}), 400

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)  # Set the cursor to return dictionary

    try:
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            return jsonify({"message": "Order not found"}), 404

        if order['status'] in ['Canceled', 'Delivered']:  # Assuming 'Delivered' is a terminal status
            return jsonify({"message": "Order cannot be updated to 'in Transit'"}), 403

        cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", ('in Transit', order_id))
        conn.commit()

        return jsonify({"message": "Order is in transit"}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/orders/AssignedOrders/<string:courier_name>', methods=['GET'])
def get_assigned_orders(courier_name):
    print(f"Fetch Orders for {courier_name} endpoint called")
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM Orders WHERE courier = %s", (courier_name,))
        assigned_orders = cursor.fetchall()

        if not assigned_orders:
            return jsonify({'message': f'No orders assigned to {courier_name}'}), 404

        return jsonify({'assigned_orders': assigned_orders}), 200
    except Exception as e:
        print(f"Error fetching assigned orders for {courier_name}:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/update_order_status_pickedup', methods=['POST'])
def update_order_status_pickedup():
    data = request.get_json()
    order_id = data.get('order_id')

    if not order_id:
        return jsonify({"message": "Order ID is required"}), 400

    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)  # Ensure the cursor returns dictionary objects

    try:
        print("Checking courier credentials...")
        # Ensure only logged-in couriers can perform this action
        cursor.execute("SELECT user_id FROM LoggedInUsers WHERE role = 'courier'")
        courier = cursor.fetchone()

        if not courier:
            return jsonify({"message": "Action allowed only for logged-in couriers"}), 403

        print("Fetching order...")
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            return jsonify({"message": "Order not found"}), 404

        if order['status'] == "Canceled":
            return jsonify({"message": "Order is already Canceled"}), 403

        print("Updating order status...")
        cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", ("picked up", order_id))
        conn.commit()

        return jsonify({"message": "Order status updated to picked up"}), 200

    except Exception as e:
        conn.rollback()
        print("Error updating order status:", e)
        return jsonify({"message": "Error updating order status", "error": str(e)}), 500

    finally:
        cursor.close()
        conn.close()


@app.route('/manage_get_all', methods=['GET'])
def get_all_orders():
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)

    # Fetch the role of the logged-in user
    cursor.execute("SELECT role FROM LoggedInUsers WHERE role = 'admin'")
    admin_check = cursor.fetchone()

    if not admin_check:  # If no admin is logged in or fetched user is not an admin
        return jsonify({"message": "Action allowed only for logged-in Admin"}), 403

    try:
        # Fetch all orders from the database
        cursor.execute("SELECT * FROM Orders")
        orders = cursor.fetchall()

        # Process and return the orders
        order_list = []
        for order in orders:
            order_info = {
                "order_id": order['order_id'],
                "user_id": order['user_id'],
                "product_id": order.get('product_id'),
                "email": order.get('email'),
                "delivery_address": order.get('delivery_address'),
                "order_status": order.get('order_status'),
                "courier": order.get('courier')
            }
            order_list.append(order_info)

        return jsonify({"orders": order_list}), 200

    except Exception as e:
        print(f"Error fetching orders: {e}")
        return jsonify({"message": f"Error retrieving orders: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()
        # Feature #10: Reassign Order to a New Courier


@app.route('/reassign_order', methods=['PUT'])
def reassign_order():
    data = request.get_json()
    order_id = data.get('order_id')  # Fixed variable name from order_name to order_id
    new_courier_id = data.get('courier')
    conn = mysql.connection
    cursor = conn.cursor(dictionary=True)

    # Fetch the role of the logged-in user
    cursor.execute("SELECT role FROM LoggedInUsers WHERE role = 'admin'")
    admin_check = cursor.fetchone()

    if not admin_check:  # If no admin is logged in or fetched user is not an admin
        return jsonify({"message": "Action allowed only for logged-in Admin"}), 403

    if not order_id or not new_courier_id:
        return jsonify({"message": "Order ID and new Courier ID are required"}), 400

    try:
        # Check if the order exists
        cursor.execute("SELECT * FROM Orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            return jsonify({"message": "Order not found"}), 404

        # Update the order to reassign it to the new courier
        cursor.execute("UPDATE Orders SET courier = %s WHERE order_id = %s", (new_courier_id, order_id))
        conn.commit()

        return jsonify({"message": "Order reassigned to new courier successfully"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": f"Error reassigning order: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    app.run(debug=True, port=8080)