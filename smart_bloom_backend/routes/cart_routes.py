from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_db_connection
cart_bp = Blueprint("cart", __name__)

#get or create cart
@cart_bp.route("/cart/get-or-create", methods=["POST"])
def get_or_create_cart():
    data = request.json
    user_id = data["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CartID 
        FROM Cart 
        WHERE UserID = ? AND IsActive = 1
    """, (user_id,))
    cart = cursor.fetchone()
    #cart already exisist 
    if cart:
        conn.close()
        return jsonify({
            "message": "Active cart found",
            "cart_id": cart[0]
        })
    #creat new one
    cursor.execute("""
        INSERT INTO Cart (UserID)
        VALUES (?)
    """, (user_id,))
    conn.commit()
    cursor.execute("SELECT SCOPE_IDENTITY()")
    new_cart_id = cursor.fetchone()[0]
    conn.close()
    return jsonify({
        "message": "New cart created",
        "cart_id": new_cart_id
    })
#add to cart
@cart_bp.route("/cart/add", methods=["POST"])
@jwt_required()
def add_to_cart():
    user_id = int(get_jwt_identity()) 
    data = request.json
    flower_id = data.get("flower_id")
    quantity = data.get("quantity")
    if not flower_id or not quantity:
        return jsonify({"error": "Missing data"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
	    #lookıng for an actıve cart 
        cursor.execute("""
            SELECT CartID FROM Cart 
            WHERE UserID = ? AND IsActive = 1
        """, (user_id,))
        cart = cursor.fetchone()
         # creat one if there is not
        if not cart:
            cursor.execute("""
                INSERT INTO Cart (UserID, IsActive)
                OUTPUT INSERTED.CartID
                VALUES (?, 1)
            """, (user_id,))
            cart_id = cursor.fetchone()[0]
        else:
            cart_id = cart[0]

        cursor.execute("""
            SELECT Quantity FROM CartItems 
            WHERE CartID = ? AND FlowerID = ?
        """, (cart_id, flower_id))
        existing_item = cursor.fetchone()
         # updating the amount
        if existing_item:
            new_quantity = existing_item[0] + int(quantity)
            cursor.execute("""
                UPDATE CartItems SET Quantity = ? 
                WHERE CartID = ? AND FlowerID = ?
            """, (new_quantity, cart_id, flower_id))
            message = "Quantity updated"
        else:
		    #new prodect is added
            cursor.execute("""
                INSERT INTO CartItems (CartID, FlowerID, Quantity) 
                VALUES (?, ?, ?)
            """, (cart_id, flower_id, quantity))
            message = "Item added to cart"
        conn.commit()
        return jsonify({"message": message, "cart_id": cart_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
# view cart
@cart_bp.route("/cart", methods=["GET"])
@jwt_required()
def view_cart():
    user_id = get_jwt_identity()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT CartID
            FROM Cart
            WHERE UserID = ? AND IsActive = 1
        """, (user_id,))
        cart = cursor.fetchone()
        if not cart:
            return jsonify({
                "items": [],
                "total_price": 0,
                "message": "No active cart found"
            }), 200
        cart_id = cart[0]
        cursor.execute("""
            SELECT f.FlowerID, f.FlowerName, f.Price, ci.Quantity, f.ImageURL
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        rows = cursor.fetchall()
        cart_items = []
        total_price = 0
        for row in rows:
            price = float(row[2]) 
            quantity = row[3]
            item_total = price * quantity
            total_price += item_total
            cart_items.append({
                "flower_id": row[0],
                "flower_name": row[1],
                "price": price,
                "quantity": quantity,
                "item_total": float(item_total),
                "image_url": row[4] 
            })
        return jsonify({
            "cart_id": cart_id,
            "items": cart_items,
            "total_price": float(total_price)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Payment Method
@cart_bp.route("/cart/payment-method", methods=["POST"])
@jwt_required()
def set_payment_method():
    current_user_id = int(get_jwt_identity())
    data = request.json
    cart_id = data.get("cart_id")
    method = data.get("method") 
    if method not in ['Visa', 'PayPal', 'Cash']:
        return jsonify({"error": "Invalid payment method"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Cart SET PaymentMethod = ? WHERE CartID = ? AND UserID = ?", (method, cart_id, current_user_id))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Payment method set to {method}"})

# 5. Final Checkout (تم دمج المنطق وتصحيحه)
@cart_bp.route("/cart/checkout", methods=["POST"])
@jwt_required()
def final_checkout():
    current_user_id = int(get_jwt_identity())
    data = request.json
    cart_id = data.get("cart_id")
    if not cart_id:
        return jsonify({"error": "Missing cart_id"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
	    #get payment method
        cursor.execute(
            "SELECT PaymentMethod FROM Cart WHERE CartID = ? AND IsActive = 1 AND UserID = ? ",
            (cart_id, current_user_id)
        )
        res = cursor.fetchone()
        if not res:
            return jsonify({"error": "Cart not found"}), 404
        
        payment_method = res[0]
        # validate payment-method
        if payment_method == "Visa":
            if not data.get("card_number") or not data.get("cvv"):
                return jsonify({"error": "Visa details missing"}), 400
        elif payment_method == "PayPal":
            if not data.get("paypal_email"):
                return jsonify({"error": "PayPal email missing"}), 400
        # calculate total price 
        cursor.execute("""
            SELECT SUM(f.Price * ci.Quantity)
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        total = cursor.fetchone()[0]
        if not total:
            return jsonify({"error": "Cart is empty"}), 400
        # create order
        cursor.execute("""
            INSERT INTO Orders (UserID, TotalPrice, OrderDate, PaymentMethod)
            OUTPUT INSERTED.OrderID
            VALUES (?, ?, GETDATE(), ?)
        """, (current_user_id, total, payment_method))
        order_id = cursor.fetchone()[0]
        # move cart items -> order details
        cursor.execute("""
            INSERT INTO Order_Details (OrderID, FlowerID, Quantity, Price)
            SELECT ?, ci.FlowerID, ci.Quantity, f.Price
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (order_id, cart_id))
        # clear cart items
        cursor.execute("DELETE FROM CartItems WHERE CartID = ?", (cart_id,))
        cursor.execute("UPDATE Cart SET IsActive = 0 WHERE CartID = ?", (cart_id,))
        conn.commit()
        return jsonify({
            "message": "Order completed successfully!",
            "order_id": order_id,
            "total_price": float(total),
            "payment_method": payment_method
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()