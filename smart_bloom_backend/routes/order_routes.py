from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_db_connection
order_bp = Blueprint("order", __name__)
# view order
@order_bp.route("/orders/<int:order_id>", methods=["GET"])
@jwt_required()
def get_order(order_id):
    current_user_id = int(get_jwt_identity())
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
            od.Price,
            o.UserID,
            f.ImageURL
        FROM Orders o
        JOIN Order_Details od ON o.OrderID = od.OrderID
        JOIN Flower f ON od.FlowerID = f.FlowerID
        WHERE o.OrderID = ? AND o.UserID = ?
    """, (order_id, current_user_id))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return jsonify({"message": "Order not found or access denied"}), 404
    order_data = {
        "order_id": rows[0][0],
        "order_date": rows[0][1].strftime("%Y-%m-%d %H:%M:%S") if rows[0][1] else "N/A",
        "total_price": float(rows[0][2]),
        "items": []
    }
    for row in rows:
        order_data["items"].append({
            "flower_id": row[3],
            "flower_name": row[4],
            "quantity": row[5],
            "price": float(row[6]),
            "item_total": float(row[5] * row[6]),
            "image_url": row[8] 
        })
    return jsonify(order_data)
# user history 
@order_bp.route("/my/orders", methods=["GET"])
@jwt_required()
def get_user_orders():
    current_user_id = int(get_jwt_identity())
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT OrderID, OrderDate, TotalPrice
        FROM Orders
        WHERE UserID = ?
        ORDER BY OrderDate DESC
    """, (current_user_id,))
    rows = cursor.fetchall()
    conn.close()
    orders = []
    for row in rows:
        orders.append({
            "order_id": row[0],
            "order_date": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else "N/A",
            "total_price": float(row[2])
        })
    return jsonify(orders)