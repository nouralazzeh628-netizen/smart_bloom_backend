from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from functools import wraps
from db import get_db_connection
admin_bp = Blueprint("admin", __name__)

def validate_json(required_fields, data):
    if not data:
        return "Request body is missing"
    for field in required_fields:
        if field not in data:
            return f"{field} is required"
    return None

def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function
#admin view 
@admin_bp.route("/admin/flowers", methods=["GET"])
@admin_required
def admin_get_flowers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT FlowerID, FlowerName, Price, Stock, ImageURL
        FROM Flower
        ORDER BY FlowerID DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    flowers = []
    for row in rows:
        flowers.append({
            "flower_id": row[0],
            "flower_name": row[1],
            "price": float(row[2]),
            "stock": row[3],
            "image_url": row[4] 
        })
    return jsonify(flowers)
#update stock 
@admin_bp.route("/admin/flowers/<int:flower_id>/stock", methods=["PUT"])
@admin_required
def update_stock(flower_id):
    data = request.json
    error = validate_json(["stock"], data)
    if error:
        return jsonify({"error": error}), 400
    try:
        new_stock = int(data["stock"])
    except:
        return jsonify({"error": "Stock must be a number"}), 400
    if new_stock < 0:
        return jsonify({"error": "Stock cannot be negative"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Flower
        SET Stock = ?
        WHERE FlowerID = ?
    """, (new_stock, flower_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Flower not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Stock updated successfully"})

#increment stock 
@admin_bp.route("/admin/flowers/<int:flower_id>/increase-stock", methods=["PUT"])
@admin_required
def increase_stock(flower_id):
    data = request.json
    error = validate_json(["amount"], data)
    if error:
        return jsonify({"error": error}), 400

    try:
        amount = int(data["amount"])
    except:
        return jsonify({"error": "Amount must be a number"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Flower
        SET Stock = Stock + ?
        WHERE FlowerID = ?
    """, (amount, flower_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Flower not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Stock increased successfully"})
#Admin API 
@admin_bp.route("/admin/flowers", methods=["POST"])
@admin_required
def add_flower():
    data = request.json
    name = data.get("name")
    price = data.get("price")
    stock = data.get("stock")
    image = data.get("image_url")
    error = validate_json(["name", "price", "stock"], data)
    if error:
       return jsonify({"error": error}), 400

    try:
       price = float(price)
       stock = int(stock)
    except:
        return jsonify({"error": "Invalid price or stock"}), 400 
    if not name or price is None or stock is None:
        return jsonify({"error": "Missing required fields"}), 400
    if price < 0 or stock < 0:
        return jsonify({"error": "Price and stock must be positive"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Flower (FlowerName, Price, Stock, ImageURL, IsActive)
        VALUES (?, ?, ?, ?, 1)
    """, (name, price, stock, image))
    cursor.execute("SELECT SCOPE_IDENTITY()")
    flower_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({
        "message": "Flower added successfully",
        "flower_id": flower_id
    })
#admin delete 
@admin_bp.route("/admin/flowers/<int:flower_id>", methods=["DELETE"])
@admin_required
def soft_delete_flower(flower_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Flower SET IsActive = 0 WHERE FlowerID = ?", (flower_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Flower not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Flower soft deleted successfully"})
#flower re_adding 
@admin_bp.route("/admin/flowers/<int:flower_id>/restore", methods=["PUT"])
@admin_required
def restore_flower(flower_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Flower
        SET IsActive = 1
        WHERE FlowerID = ?
    """, (flower_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Flower not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Flower restored successfully"})
#Dashboard Overview Stats
@admin_bp.route("/admin/dashboard/stats", methods=["GET"])
@admin_required
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(OrderID), SUM(TotalPrice) FROM Orders")
    order_data = cursor.fetchone()
    cursor.execute("SELECT COUNT(UserID) FROM Users WHERE Role = 'user'")
    user_count = cursor.fetchone()[0]
    cursor.execute("""
        SELECT TOP 1 f.FlowerName, SUM(od.Quantity) as total_sold
        FROM Order_Details od
        JOIN Flower f ON od.FlowerID = f.FlowerID
        GROUP BY f.FlowerName
        ORDER BY total_sold DESC
    """)
    top_flower = cursor.fetchone()
    conn.close()
    return jsonify({
        "total_orders": order_data[0],
        "total_revenue": float(order_data[1] or 0),
        "total_customers": user_count,
        "best_seller": top_flower[0] if top_flower else "None"
    })
#view all customer orders
@admin_bp.route("/admin/orders", methods=["GET"])
@admin_required
def admin_view_all_orders():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.OrderID, u.Email, o.TotalPrice, o.OrderDate
        FROM Orders o
        JOIN Users u ON o.UserID = u.UserID
        ORDER BY o.OrderDate DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    all_orders = []
    for row in rows:
        order_date_raw = row[3]
        formatted_date = order_date_raw.strftime("%Y-%m-%d %H:%M:%S") if order_date_raw else "No Date recorded"
        all_orders.append({
            "order_id": row[0],
            "customer_email": row[1],
            "total": float(row[2]) if row[2] else 0.0,
            "date": formatted_date
        })
    return jsonify(all_orders)
#(Update Flower Profile)
@admin_bp.route("/admin/flowers/<int:flower_id>/edit", methods=["PUT"])
@admin_required
def edit_flower_full(flower_id):
    if not data:
       return jsonify({"error": "Request body is required"}), 400
    
    data = request.json
    name = data.get("name")
    price = data.get("price")
    image = data.get("image_url")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Flower 
        SET FlowerName = ISNULL(?, FlowerName), 
            Price = ISNULL(?, Price), 
            ImageURL = ISNULL(?, ImageURL)
        WHERE FlowerID = ?
    """, (name, price, image, flower_id))
    conn.commit()
    conn.close()
    return jsonify({"message": "Flower profile updated successfully"})

#bouquets 
@admin_bp.route("/admin/bouquets", methods=["POST"])
@admin_required
def add_bouquet():
    data = request.json
    name = data.get("name")
    description = data.get("description")
    price = data.get("price")
    image = data.get("image_url")
    occasion_id = data.get("occasion_id") 
    flowers_list = data.get("flowers") # list 
    error = validate_json(["name", "price", "flowers"], data)
    if error:
       return jsonify({"error": error}), 400

    try:
       price = float(price)
    except:
       return jsonify({"error": "Price must be a number"}), 400

    if not isinstance(flowers_list, list) or len(flowers_list) == 0:
       return jsonify({"error": "Flowers list must be a non-empty list"}), 400

    for item in flowers_list:
       if "flower_id" not in item or "quantity" not in item:
           return jsonify({"error": "Each flower must have flower_id and quantity"}), 400
       if not name or not price or not flowers_list:
           return jsonify({"error": "Missing required fields"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # adding a bouquet
        cursor.execute("""
            INSERT INTO Bouquet (Name, Description, Price, ImageURL, OccasionID)
            OUTPUT INSERTED.BouquetID
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, price, image, occasion_id))
        
        bouquet_id = cursor.fetchone()[0]

        # adding bouquet items 
        for item in flowers_list:
            cursor.execute("""
                INSERT INTO BouquetFlowers (BouquetID, FlowerID, Quantity)
                VALUES (?, ?, ?)
            """, (bouquet_id, item['flower_id'], item['quantity']))

        conn.commit()
        return jsonify({"message": "Bouquet created with its flowers!", "bouquet_id": bouquet_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        