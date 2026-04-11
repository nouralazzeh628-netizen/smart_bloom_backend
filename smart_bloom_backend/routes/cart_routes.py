from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_db_connection

cart_bp = Blueprint("cart", __name__)


#get active cart ID for user
def get_active_cart_id(cursor, user_id):
    cursor.execute("""
        SELECT CartID FROM Cart 
        WHERE UserID = ? AND IsActive = 1
    """, (user_id,))
    cart = cursor.fetchone()
    return cart[0] if cart else None


#GET OR CREATE CART
@cart_bp.route("/cart/get-or-create", methods=["POST"])
@jwt_required()                              
def get_or_create_cart():
    user_id = int(get_jwt_identity())       
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cart_id = get_active_cart_id(cursor, user_id)
        if cart_id:
            return jsonify({"message": "Active cart found", "cart_id": cart_id}), 200

        cursor.execute("""
            INSERT INTO Cart (UserID, IsActive)
            OUTPUT INSERTED.CartID
            VALUES (?, 1)
        """, (user_id,))
        cart_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"message": "New cart created", "cart_id": cart_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not get or create cart"}), 500
    finally:
        cursor.close()
        conn.close()


# ADD TO CART
@cart_bp.route("/cart/add", methods=["POST"])
@jwt_required()
def add_to_cart():
    user_id = int(get_jwt_identity())
    data = request.json
    flower_id = data.get("flower_id")
    quantity = data.get("quantity")

    if not flower_id or not quantity:
        return jsonify({"error": "flower_id and quantity are required"}), 400
    if not isinstance(quantity, int) or quantity <= 0:   # quantity guard
        return jsonify({"error": "Quantity must be a positive integer"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Stock check before adding
        cursor.execute("""
            SELECT Stock FROM Flower WHERE FlowerID = ?
        """, (flower_id,))
        flower = cursor.fetchone()
        if not flower:
            return jsonify({"error": "Flower not found"}), 404
        if flower[0] < quantity:
            return jsonify({"error": f"Only {flower[0]} items in stock"}), 400

        cart_id = get_active_cart_id(cursor, user_id)
        if not cart_id:
            cursor.execute("""
                INSERT INTO Cart (UserID, IsActive)
                OUTPUT INSERTED.CartID
                VALUES (?, 1)
            """, (user_id,))
            cart_id = cursor.fetchone()[0]

        cursor.execute("""
            SELECT Quantity FROM CartItems 
            WHERE CartID = ? AND FlowerID = ?
        """, (cart_id, flower_id))
        existing = cursor.fetchone()

        if existing:
            new_qty = existing[0] + quantity
            if new_qty > flower[0]:               # stock check against total
                return jsonify({"error": f"Only {flower[0]} items in stock"}), 400
            cursor.execute("""
                UPDATE CartItems SET Quantity = ? 
                WHERE CartID = ? AND FlowerID = ?
            """, (new_qty, cart_id, flower_id))
            message = "Quantity updated"
        else:
            cursor.execute("""
                INSERT INTO CartItems (CartID, FlowerID, Quantity) 
                VALUES (?, ?, ?)
            """, (cart_id, flower_id, quantity))
            message = "Item added to cart"

        conn.commit()
        return jsonify({"message": message, "cart_id": cart_id}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not add item to cart"}), 500
    finally:
        cursor.close()
        conn.close()


#VIEW CART
@cart_bp.route("/cart", methods=["GET"])
@jwt_required()
def view_cart():
    user_id = int(get_jwt_identity())     

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cart_id = get_active_cart_id(cursor, user_id)
        if not cart_id:
            return jsonify({"items": [], "total_price": 0, "message": "No active cart found"}), 200

        cursor.execute("""
            SELECT f.FlowerID, f.FlowerName, f.Price, ci.Quantity, f.ImageURL
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        rows = cursor.fetchall()

        cart_items = []
        total_price = 0.0
        for row in rows:
            price, quantity = float(row[2]), row[3]
            item_total = price * quantity
            total_price += item_total
            cart_items.append({
                "flower_id": row[0],
                "flower_name": row[1],
                "price": price,
                "quantity": quantity,
                "item_total": round(item_total, 2),
                "image_url": row[4]
            })

        return jsonify({
            "cart_id": cart_id,
            "items": cart_items,
            "total_price": round(total_price, 2)
        }), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve cart"}), 500
    finally:
        cursor.close()
        conn.close()


#UPDATE ITEM QUANTITY
@cart_bp.route("/cart/update", methods=["PUT"])
@jwt_required()
def update_cart_item():
    user_id = int(get_jwt_identity())
    data = request.json
    flower_id = data.get("flower_id")
    quantity = data.get("quantity")

    if not flower_id or quantity is None:
        return jsonify({"error": "flower_id and quantity are required"}), 400
    if not isinstance(quantity, int) or quantity < 0:
        return jsonify({"error": "Quantity must be 0 or more (0 removes the item)"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cart_id = get_active_cart_id(cursor, user_id)
        if not cart_id:
            return jsonify({"error": "No active cart found"}), 404

        if quantity == 0:
            cursor.execute("""
                DELETE FROM CartItems WHERE CartID = ? AND FlowerID = ?
            """, (cart_id, flower_id))
            message = "Item removed from cart"
        else:
            # Stock check
            cursor.execute("SELECT Stock FROM Flower WHERE FlowerID = ?", (flower_id,))
            flower = cursor.fetchone()
            if not flower:
                return jsonify({"error": "Flower not found"}), 404
            if flower[0] < quantity:
                return jsonify({"error": f"Only {flower[0]} items in stock"}), 400

            cursor.execute("""
                UPDATE CartItems SET Quantity = ?
                WHERE CartID = ? AND FlowerID = ?
            """, (quantity, cart_id, flower_id))
            message = "Quantity updated"

        conn.commit()
        return jsonify({"message": message}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update cart"}), 500
    finally:
        cursor.close()
        conn.close()


#REMOVE ITEM FROM CART
@cart_bp.route("/cart/remove", methods=["DELETE"])
@jwt_required()
def remove_from_cart():
    user_id = int(get_jwt_identity())
    data = request.json
    flower_id = data.get("flower_id")

    if not flower_id:
        return jsonify({"error": "flower_id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cart_id = get_active_cart_id(cursor, user_id)
        if not cart_id:
            return jsonify({"error": "No active cart found"}), 404

        cursor.execute("""
            DELETE FROM CartItems WHERE CartID = ? AND FlowerID = ?
        """, (cart_id, flower_id))
        conn.commit()
        return jsonify({"message": "Item removed from cart"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not remove item"}), 500
    finally:
        cursor.close()
        conn.close()


# CLEAR CART 
@cart_bp.route("/cart/clear", methods=["DELETE"])
@jwt_required()
def clear_cart():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cart_id = get_active_cart_id(cursor, user_id)
        if not cart_id:
            return jsonify({"error": "No active cart found"}), 404

        cursor.execute("DELETE FROM CartItems WHERE CartID = ?", (cart_id,))
        conn.commit()
        return jsonify({"message": "Cart cleared"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not clear cart"}), 500
    finally:
        cursor.close()
        conn.close()


# SET PAYMENT METHOD
@cart_bp.route("/cart/payment-method", methods=["POST"])
@jwt_required()
def set_payment_method():
    user_id = int(get_jwt_identity())
    data = request.json
    cart_id = data.get("cart_id")
    method = data.get("method")

    if not cart_id:
        return jsonify({"error": "cart_id is required"}), 400
    if method not in ["Visa", "PayPal", "Cash"]:
        return jsonify({"error": "Invalid payment method"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        #Verify cart belongs to this user
        cursor.execute("""
            SELECT CartID FROM Cart 
            WHERE CartID = ? AND UserID = ? AND IsActive = 1
        """, (cart_id, user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Cart not found"}), 404

        cursor.execute("""
            UPDATE Cart SET PaymentMethod = ? 
            WHERE CartID = ? AND UserID = ?
        """, (method, cart_id, user_id))
        conn.commit()
        return jsonify({"message": f"Payment method set to {method}"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not set payment method"}), 500
    finally:
        cursor.close()
        conn.close()

# CHECKOUT
@cart_bp.route("/cart/checkout", methods=["POST"])
@jwt_required()
def final_checkout():
    user_id = int(get_jwt_identity())
    data = request.json
    cart_id = data.get("cart_id")

    if not cart_id:
        return jsonify({"error": "cart_id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT PaymentMethod FROM Cart 
            WHERE CartID = ? AND IsActive = 1 AND UserID = ?
        """, (cart_id, user_id))
        res = cursor.fetchone()
        if not res:
            return jsonify({"error": "Cart not found"}), 404

        payment_method = res[0]
        if not payment_method:
            return jsonify({"error": "Please set a payment method first"}), 400

        # Payment validation
        if payment_method == "Visa":
            if not data.get("card_number") or not data.get("cvv"):
                return jsonify({"error": "Visa details missing"}), 400
        elif payment_method == "PayPal":
            if not data.get("paypal_email"):
                return jsonify({"error": "PayPal email missing"}), 400

        # Stock check before confirming order
        cursor.execute("""
            SELECT ci.FlowerID, ci.Quantity, f.Stock
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        items = cursor.fetchall()

        if not items:
            return jsonify({"error": "Cart is empty"}), 400

        for flower_id, qty, stock in items:
            if stock < qty:
                return jsonify({
                    "error": f"Insufficient stock for flower ID {flower_id}"
                }), 400

        # Calculate total
        cursor.execute("""
            SELECT SUM(f.Price * ci.Quantity)
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        total = cursor.fetchone()[0]

        # Loyalty points rule
        earned_points = int(float(total))   # 1 point for each 1 JOD

        # Create order
        cursor.execute("""
            INSERT INTO Orders (UserID, TotalPrice, OrderDate, PaymentMethod, LoyaltyPointsEarned)
            OUTPUT INSERTED.OrderID
            VALUES (?, ?, GETDATE(), ?, ?)
        """, (user_id, total, payment_method, earned_points))
        order_id = cursor.fetchone()[0]

        # Move items to Order_Details
        cursor.execute("""
            INSERT INTO Order_Details (OrderID, FlowerID, Quantity, Price)
            SELECT ?, ci.FlowerID, ci.Quantity, f.Price
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (order_id, cart_id))

        # Deduct stock
        cursor.execute("""
            UPDATE f
            SET f.Stock = f.Stock - ci.Quantity
            FROM Flower f
            JOIN CartItems ci ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))

        # Add loyalty points to user
        cursor.execute("""
            UPDATE Users
            SET LoyaltyPoints = LoyaltyPoints + ?
            WHERE UserID = ?
        """, (earned_points, user_id))

        # Save loyalty transaction history
        cursor.execute("""
            INSERT INTO LoyaltyTransactions (UserID, OrderID, Points, Type)
            VALUES (?, ?, ?, 'earn')
        """, (user_id, order_id, earned_points))

        # Clear cart
        cursor.execute("DELETE FROM CartItems WHERE CartID = ?", (cart_id,))
        cursor.execute("UPDATE Cart SET IsActive = 0 WHERE CartID = ?", (cart_id,))

        conn.commit()
        return jsonify({
            "message": "Order placed successfully!",
            "order_id": order_id,
            "total_price": round(float(total), 2),
            "payment_method": payment_method,
            "earned_points": earned_points
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({
            "error": "Checkout failed",
            "details": str(e)
        }), 500
    finally:
        cursor.close()
        conn.close()
        # GET USER LOYALTY POINTS
@cart_bp.route("/loyalty/me", methods=["GET"])
@jwt_required()
def get_loyalty_points():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT LoyaltyPoints FROM Users WHERE UserID = ?
        """, (user_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "user_id": user_id,
            "loyalty_points": row[0]
        }), 200

    except:
        return jsonify({"error": "Failed to fetch loyalty points"}), 500
    finally:
        cursor.close()
        conn.close()
        
