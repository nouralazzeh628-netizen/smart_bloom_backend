from flask import Flask, jsonify, request
from db import get_db_connection
import db
print(db.__file__)

app = Flask(__name__)

# Main page
@app.route("/")
def home():
    return "Smart Bloom Store Backend is running 🌸"

#users 
@app.route("/users", methods=["GET", "POST"])
def users():
    if request.method == "GET":
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT UserID, UserName, Email FROM Users")
        rows = cursor.fetchall()
        users = []
        for row in rows:
            users.append({
                "id": row[0],
                "username": row[1],
                "email": row[2]
            })
        conn.close()
        return jsonify(users)

    elif request.method == "POST":
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Users (UserName, Password, Email, Address)
            VALUES (?, ?, ?, ?)
        """, (data["username"], data["password"], data["email"], data["address"]))
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        user_id = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            "message": "User created successfully",
            "user_id": user_id
        })
        
#login
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT UserID, UserName 
        FROM Users 
        WHERE UserName = ? AND Password = ?
    """, (data["username"], data["password"]))

    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({
            "message": "Login successful",
            "user_id": user[0],
            "username": user[1]
        })
    else:
        return jsonify({
            "message": "Invalid username or password"
        }), 401
        

# Flowers route
@app.route("/Flower")
def get_Flower():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT FlowerID, FlowerName, Price FROM Flower")
    rows = cursor.fetchall()
    Flower = []
    for row in rows:
        Flower.append({
            "id": row[0],    # FlowerID
            "name": row[1],  # Name
            "price": row[2]  # Price
        })
    conn.close()
    return jsonify(Flower)

#cart
@app.route("/cart/get-or-create", methods=["POST"])
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
    
#@app.route("/test")
#def test():
#   return "working"
#cart items 
@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json
    cart_id = data["cart_id"]
    flower_id = data["flower_id"]
    quantity = data["quantity"]
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # if it is  exisist 
    cursor.execute("""
        SELECT Quantity
        FROM CartItems
        WHERE CartID = ? AND FlowerID = ?
    """, (cart_id, flower_id))
    existing_item = cursor.fetchone()
    
    #add if it is allready there 
    if existing_item:
        new_quantity = existing_item[0] + quantity
        cursor.execute("""
            UPDATE CartItems
            SET Quantity = ?
            WHERE CartID = ? AND FlowerID = ?
        """, (new_quantity, cart_id, flower_id))
        message = "Quantity updated"

    # add it as a new 
    else:
        cursor.execute("""
            INSERT INTO CartItems (CartID, FlowerID, Quantity)
            VALUES (?, ?, ?)
        """, (cart_id, flower_id, quantity))
        message = "Item added to cart"
    conn.commit()
    conn.close()
    return jsonify({"message": message})

#cart view 
@app.route("/cart/<int:cart_id>", methods=["GET"])
def view_cart(cart_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.FlowerID,
               f.FlowerName,
               f.Price,
               ci.Quantity
        FROM CartItems ci
        JOIN Flower f ON ci.FlowerID = f.FlowerID
        WHERE ci.CartID = ?
    """, (cart_id,))
    rows = cursor.fetchall()
    conn.close()
    cart_items = []
    total_price = 0
    for row in rows:
        flower_id = row[0]
        flower_name = row[1]
        price = row[2]
        quantity = row[3]
        item_total = price * quantity
        total_price += item_total
        cart_items.append({
            "flower_id": flower_id,
            "flower_name": flower_name,
            "price": price,
            "quantity": quantity,
            "item_total": item_total
        })
    return jsonify({
        "cart_id": cart_id,
        "items": cart_items,
        "total_price": total_price
    })
    
#checkout  
@app.route("/cart/checkout", methods=["POST"])
def checkout():
    data = request.json
    cart_id = data.get("cart_id")
    if not cart_id:
        return jsonify({"error": "Missing cart_id"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT UserID
            FROM Cart
            WHERE CartID = ? AND IsActive = 1
        """, (cart_id,))
        cart = cursor.fetchone()
        if not cart:
            return jsonify({"error": "Cart not found or already checked out"}), 404
        user_id = cart[0]
        cursor.execute("""
            SELECT SUM(f.Price * ci.Quantity)
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (cart_id,))
        total = cursor.fetchone()[0]
        if total is None:
            return jsonify({"error": "Cart is empty"}), 400
        cursor.execute("""
           INSERT INTO Orders (UserID, TotalPrice)
           OUTPUT INSERTED.OrderID
           VALUES (?, ?)
        """, (user_id, total))
        order_id = cursor.fetchone()[0]
        cursor.execute("""
            INSERT INTO Order_Details (OrderID, FlowerID, Quantity, Price)
            SELECT ?, ci.FlowerID, ci.Quantity, f.Price
            FROM CartItems ci
            JOIN Flower f ON ci.FlowerID = f.FlowerID
            WHERE ci.CartID = ?
        """, (order_id, cart_id))
        cursor.execute("DELETE FROM CartItems WHERE CartID = ?", (cart_id,))
        cursor.execute("UPDATE Cart SET IsActive = 0 WHERE CartID = ?", (cart_id,))
        conn.commit()
        return jsonify({
            "message": "Checkout successful",
            "order_id": int(order_id),
            "total_amount": float(total)
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
#view order
@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            o.OrderID,
            o.OrderDate,
            o.TotalPrice,
            od.FlowerID,
            f.FlowerName,
            od.Quantity,
            od.Price
        FROM Orders o
        JOIN Order_Details od ON o.OrderID = od.OrderID
        JOIN Flower f ON od.FlowerID = f.FlowerID
        WHERE o.OrderID = ?
    """, (order_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return jsonify({"message": "Order not found"}), 404
    order_data = {
        "order_id": rows[0][0],
        "order_date": rows[0][1],
        "total_price": rows[0][2],
        "items": []
    }
    for row in rows:
        order_data["items"].append({
            "flower_id": row[3],
            "flower_name": row[4],
            "quantity": row[5],
            "price": row[6],
            "item_total": row[5] * row[6]
        })
    return jsonify(order_data)
        
        
if __name__ == "__main__":
    app.run(debug=True)


