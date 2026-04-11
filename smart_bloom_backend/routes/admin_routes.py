from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from functools import wraps
from db import get_db_connection
from datetime import datetime

def safe_format_date(val):
    if val is None:
        return None
    if isinstance(val, str):
        # parse if it's already a string
        try:
            val = datetime.fromisoformat(val)
        except ValueError:
            return val  # return as-is if unparseable
    return val.strftime("%Y-%m-%d %H:%M:%S")

admin_bp = Blueprint("admin", __name__)


#HELPERS 
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
        if claims.get("role", "").lower() != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function


# ADMIN: GET ALL FLOWERS 
@admin_bp.route("/admin/flowers", methods=["GET"])
@admin_required
def admin_get_flowers():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset   = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT FlowerID, FlowerName, Price, Stock, ImageURL, IsActive
            FROM Flower
            ORDER BY FlowerID DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, per_page))
        rows = cursor.fetchall()

        return jsonify({
            "page": page,
            "per_page": per_page,
            "flowers": [
                {
                    "flower_id":   row[0],
                    "flower_name": row[1],
                    "price":       float(row[2]),
                    "stock":       row[3],
                    "image_url":   row[4],
                    "is_active":   bool(row[5])   
                } for row in rows
            ]
        }), 200

    except Exception:
        return jsonify({"error": "Could not retrieve flowers"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: ADD FLOWER 
@admin_bp.route("/admin/flowers", methods=["POST"])
@admin_required
def add_flower():
    data = request.json
    error = validate_json(["name", "price", "stock"], data)
    if error:
        return jsonify({"error": error}), 400

    name   = data.get("name", "").strip()
    image  = data.get("image_url")
    occasion = data.get("occasion", "")       

    try:
        price = float(data["price"])
        stock = int(data["stock"])
    except (ValueError, TypeError):
        return jsonify({"error": "Price must be a number and stock must be an integer"}), 400

    if not name:
        return jsonify({"error": "name cannot be empty"}), 400
    if price < 0 or stock < 0:
        return jsonify({"error": "Price and stock must be non-negative"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Flower (FlowerName, Price, Stock, ImageURL, Occasion, IsActive)
            OUTPUT INSERTED.FlowerID
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, price, stock, image, occasion))   
        flower_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "message": "Flower added successfully",
            "flower_id": flower_id
        }), 201

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not add flower"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: EDIT FLOWER 
@admin_bp.route("/admin/flowers/<int:flower_id>", methods=["PUT"])
@admin_required
def edit_flower(flower_id):
    data = request.json                      
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name     = data.get("name")
    price    = data.get("price")
    image    = data.get("image_url")
    occasion = data.get("occasion")

    if price is not None:
        try:
            price = float(price)
            if price < 0:
                return jsonify({"error": "Price must be non-negative"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Price must be a number"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Flower
            SET FlowerName = ISNULL(?, FlowerName),
                Price      = ISNULL(?, Price),
                ImageURL   = ISNULL(?, ImageURL),
                Occasion   = ISNULL(?, Occasion)
            WHERE FlowerID = ?
        """, (name, price, image, occasion, flower_id))

        if cursor.rowcount == 0:              
            return jsonify({"error": "Flower not found"}), 404

        conn.commit()
        return jsonify({"message": "Flower updated successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not update flower"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: SOFT DELETE FLOWER 
@admin_bp.route("/admin/flowers/<int:flower_id>", methods=["DELETE"])
@admin_required
def soft_delete_flower(flower_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Flower SET IsActive = 0 WHERE FlowerID = ?", (flower_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Flower not found"}), 404
        conn.commit()
        return jsonify({"message": "Flower deactivated successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not deactivate flower"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: RESTORE FLOWER
@admin_bp.route("/admin/flowers/<int:flower_id>/restore", methods=["PUT"])
@admin_required
def restore_flower(flower_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Flower SET IsActive = 1 WHERE FlowerID = ?", (flower_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Flower not found"}), 404
        conn.commit()
        return jsonify({"message": "Flower restored successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not restore flower"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: UPDATE STOCK (set absolute value)
@admin_bp.route("/admin/flowers/<int:flower_id>/stock", methods=["PUT"])
@admin_required
def update_stock(flower_id):
    data  = request.json
    error = validate_json(["stock"], data)
    if error:
        return jsonify({"error": error}), 400

    try:
        new_stock = int(data["stock"])
    except (ValueError, TypeError):
        return jsonify({"error": "Stock must be an integer"}), 400

    if new_stock < 0:
        return jsonify({"error": "Stock cannot be negative"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Flower SET Stock = ? WHERE FlowerID = ?", (new_stock, flower_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Flower not found"}), 404
        conn.commit()
        return jsonify({"message": "Stock updated successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not update stock"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: INCREASE STOCK
@admin_bp.route("/admin/flowers/<int:flower_id>/increase-stock", methods=["PUT"])
@admin_required
def increase_stock(flower_id):
    data  = request.json
    error = validate_json(["amount"], data)
    if error:
        return jsonify({"error": error}), 400

    try:
        amount = int(data["amount"])
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be an integer"}), 400

    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Flower SET Stock = Stock + ? WHERE FlowerID = ?
        """, (amount, flower_id))
        if cursor.rowcount == 0:
            return jsonify({"error": "Flower not found"}), 404
        conn.commit()
        return jsonify({"message": "Stock increased successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not increase stock"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: DASHBOARD STATS
@admin_bp.route("/admin/dashboard/stats", methods=["GET"])
@admin_required
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(OrderID), SUM(TotalPrice) FROM Orders")
        order_data = cursor.fetchone()

        cursor.execute("SELECT COUNT(UserID) FROM Users WHERE Role = 'User'")
        user_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT TOP 1 f.FlowerName, SUM(od.Quantity) AS total_sold
            FROM Order_Details od
            JOIN Flower f ON od.FlowerID = f.FlowerID
            GROUP BY f.FlowerName
            ORDER BY total_sold DESC
        """)
        top_flower = cursor.fetchone()

        #Low stock alert (below 5 units)
        cursor.execute("""
            SELECT COUNT(*) FROM Flower WHERE Stock < 5 AND IsActive = 1
        """)
        low_stock_count = cursor.fetchone()[0]

    #     Orders by status breakdown
    #    cursor.execute("""
    #        SELECT Status, COUNT(*) FROM Orders GROUP BY Status """)
    #     status_rows = cursor.fetchall()
    #     orders_by_status = {row[0]: row[1] for row in status_rows}

        return jsonify({
            "total_orders":      order_data[0] or 0,
            "total_revenue":     round(float(order_data[1] or 0), 2),
            "total_customers":   user_count,
            "best_seller":       top_flower[0] if top_flower else None,
            "low_stock_count":   low_stock_count    
            #"orders_by_status":  orders_by_status      
        }), 200

    except Exception:
        return jsonify({"error": "Could not retrieve stats"}), 500
    finally:
        cursor.close()
        conn.close()

#ADMIN:GET ALL ORDERS
@admin_bp.route("/admin/orders", methods=["GET"])
@admin_required
def get_dashboard_statss():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset   = (page - 1) * per_page
    status   = request.args.get("status")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if status:
            cursor.execute("""
                SELECT o.OrderID, u.Email, o.TotalPrice, o.OrderDate,
                     o.PaymentMethod
                FROM Orders o
                JOIN Users u ON o.UserID = u.UserID
                WHERE o.Status = ?
                ORDER BY o.OrderDate DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """, (status, offset, per_page))
        else:
            cursor.execute("""
                SELECT o.OrderID, u.Email, o.TotalPrice, o.OrderDate,
                        o.PaymentMethod
                FROM Orders o
                JOIN Users u ON o.UserID = u.UserID
                ORDER BY o.OrderDate DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """, (offset, per_page))

        rows = cursor.fetchall()
        return jsonify({
            "page": page,
            "per_page": per_page,
            "orders": [
                {
                    "order_id":       row[0],
                    "customer_email": row[1],
                    "total":          round(float(row[2] or 0), 2),
                    "date":           safe_format_date(row[3]),  # ← fixed
                    # "status":         row[4],
                    "payment_method": row[4]
                } for row in rows
            ]
        }), 200

    except Exception as e:
        print(f"Dashboard orders error: {e}")  # ← now you'll see the real error
        return jsonify({"error": "Could not retrieve orders", "detail": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
        

       
# ADMIN: GET SINGLE ORDER DETAILS 
@admin_bp.route("/admin/orders/<int:order_id>", methods=["GET"])
@admin_required
def admin_get_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT o.OrderID, u.Email, o.TotalPrice, o.OrderDate,
                    o.PaymentMethod,
                   od.FlowerID, f.FlowerName, od.Quantity, od.Price
            FROM Orders o
            JOIN Users u ON o.UserID = u.UserID
            JOIN Order_Details od ON o.OrderID = od.OrderID
            JOIN Flower f ON od.FlowerID = f.FlowerID
            WHERE o.OrderID = ?
        """, (order_id,))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"error": "Order not found"}), 404

        order = {
            "order_id":       rows[0][0],
            "customer_email": rows[0][1],
            "total_price":    round(float(rows[0][2] or 0), 2),
            "date":           rows[0][3].strftime("%Y-%m-%d %H:%M:%S") if rows[0][3] else None,
            "payment_method": rows[0][4],
            "items": [
                {
                    "flower_id":   row[5],
                    "flower_name": row[6],
                    "quantity":    row[7],
                    "price":       round(float(row[8]), 2),
                    "item_total":  round(float(row[8] * row[7]), 2)
                } for row in rows
            ]
        }
        return jsonify(order), 200

    except Exception:
        return jsonify({"error": "Could not retrieve order"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: ADD BOUQUET
@admin_bp.route("/admin/bouquets", methods=["POST"])
@admin_required
def add_bouquet():
    data  = request.json
    error = validate_json(["name", "price", "flowers"], data)
    if error:
        return jsonify({"error": error}), 400

    name         = data.get("name", "").strip()
    description  = data.get("description", "")
    image        = data.get("image_url")
    occasion_id  = data.get("occasion_id")
    flowers_list = data.get("flowers")

    if not name:
        return jsonify({"error": "name cannot be empty"}), 400

    try:
        price = float(data["price"])
        if price < 0:
            return jsonify({"error": "Price must be non-negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Price must be a number"}), 400

    if not isinstance(flowers_list, list) or len(flowers_list) == 0:
        return jsonify({"error": "flowers must be a non-empty list"}), 400

    # validate all flowers BEFORE opening DB connection
    for item in flowers_list:
        if "flower_id" not in item or "quantity" not in item:
            return jsonify({"error": "Each flower must have flower_id and quantity"}), 400
        if not isinstance(item["quantity"], int) or item["quantity"] <= 0:
            return jsonify({"error": "Each flower quantity must be a positive integer"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Bouquet (Name, Description, Price, ImageURL, OccasionID)
            OUTPUT INSERTED.BouquetID
            VALUES (?, ?, ?, ?, ?)
        """, (name, description, price, image, occasion_id))
        bouquet_id = cursor.fetchone()[0]

        for item in flowers_list:
            cursor.execute("""
                INSERT INTO BouquetFlowers (BouquetID, FlowerID, Quantity)
                VALUES (?, ?, ?)
            """, (bouquet_id, item["flower_id"], item["quantity"]))

        conn.commit()
        return jsonify({
            "message": "Bouquet created successfully",
            "bouquet_id": bouquet_id
        }), 201

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not create bouquet"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: GET ALL BOUQUETS 
@admin_bp.route("/admin/bouquets", methods=["GET"])
@admin_required
def get_bouquets():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT BouquetID, Name, Price, ImageURL, Description
            FROM Bouquet
            ORDER BY BouquetID DESC
        """)
        rows = cursor.fetchall()
        return jsonify([
            {
                "bouquet_id":  row[0],
                "name":        row[1],
                "price":       round(float(row[2]), 2),
                "image_url":   row[3],
                "description": row[4]
            } for row in rows
        ]), 200

    except Exception:
        return jsonify({"error": "Could not retrieve bouquets"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: DELETE BOUQUET
@admin_bp.route("/admin/bouquets/<int:bouquet_id>", methods=["DELETE"])
@admin_required
def delete_bouquet(bouquet_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM BouquetFlowers WHERE BouquetID = ?", (bouquet_id,))
        cursor.execute("DELETE FROM Bouquet WHERE BouquetID = ?", (bouquet_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Bouquet not found"}), 404
        conn.commit()
        return jsonify({"message": "Bouquet deleted successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not delete bouquet"}), 500
    finally:
        cursor.close()
        conn.close()