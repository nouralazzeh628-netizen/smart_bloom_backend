from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from db import get_db_connection

order_bp = Blueprint("order", __name__)

VALID_STATUSES = {"Pending", "Processing", "Shipped", "Delivered", "Cancelled"}


#HELPER: admin guard
def require_admin():
    claims = get_jwt()
    if claims.get("role") != "Admin":
        return False, (jsonify({"error": "Admin access required"}), 403)
    return True, None


# GET SINGLE ORDER (user sees own only) 
@order_bp.route("/orders/<int:order_id>", methods=["GET"])
@jwt_required()
def get_order(order_id):
    current_user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                o.OrderID,
                o.OrderDate,
                o.TotalPrice,
                o.Status,           
                o.PaymentMethod,    
                od.FlowerID,
                f.FlowerName,
                od.Quantity,
                od.Price,
                f.ImageURL
            FROM Orders o
            JOIN Order_Details od ON o.OrderID = od.OrderID
            JOIN Flower f ON od.FlowerID = f.FlowerID
            WHERE o.OrderID = ? AND o.UserID = ?
        """, (order_id, current_user_id))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"error": "Order not found or access denied"}), 404

        order_data = {
            "order_id":      rows[0][0],
            "order_date":    rows[0][1].strftime("%Y-%m-%d %H:%M:%S") if rows[0][1] else None,
            "total_price":   round(float(rows[0][2]), 2),
            "status":        rows[0][3],       
            "payment_method": rows[0][4],      
            "items": []
        }
        for row in rows:
            order_data["items"].append({
                "flower_id":   row[5],
                "flower_name": row[6],
                "quantity":    row[7],
                "price":       round(float(row[8]), 2),
                "item_total":  round(float(row[7] * row[8]), 2),
                "image_url":   row[9]
            })
        return jsonify(order_data), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve order"}), 500
    finally:
        cursor.close()
        conn.close()


#GET USER ORDER HISTORY 
@order_bp.route("/my/orders", methods=["GET"])
@jwt_required()
def get_user_orders():
    current_user_id = int(get_jwt_identity())

    #Pagination
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    offset   = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT OrderID, OrderDate, TotalPrice, Status, PaymentMethod
            FROM Orders
            WHERE UserID = ?
            ORDER BY OrderDate DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (current_user_id, offset, per_page))
        rows = cursor.fetchall()

        orders = []
        for row in rows:
            orders.append({
                "order_id":       row[0],
                "order_date":     row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else None,
                "total_price":    round(float(row[2]), 2),
                "status":         row[3],       
                "payment_method": row[4]        
            })
        return jsonify({
            "page":    page,
            "per_page": per_page,
            "orders":  orders
        }), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve orders"}), 500
    finally:
        cursor.close()
        conn.close()


# CANCEL ORDER (user cancels own order)
@order_bp.route("/orders/<int:order_id>/cancel", methods=["PUT"])
@jwt_required()
def cancel_order(order_id):
    current_user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify ownership and check current status
        cursor.execute("""
            SELECT Status FROM Orders
            WHERE OrderID = ? AND UserID = ?
        """, (order_id, current_user_id))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "Order not found or access denied"}), 404

        if row[0] not in ("Pending", "Processing"):
            return jsonify({
                "error": f"Cannot cancel an order with status '{row[0]}'"
            }), 400

        # Restore stock for all items in the order
        cursor.execute("""
            UPDATE f
            SET f.Stock = f.Stock + od.Quantity
            FROM Flower f
            JOIN Order_Details od ON od.FlowerID = f.FlowerID
            WHERE od.OrderID = ?
        """, (order_id,))

        cursor.execute("""
            UPDATE Orders SET Status = 'Cancelled'
            WHERE OrderID = ?
        """, (order_id,))

        conn.commit()
        return jsonify({"message": "Order cancelled successfully"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not cancel order"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: VIEW ALL ORDERS 
@order_bp.route("/admin/orders", methods=["GET"])
@jwt_required()
def admin_get_all_orders():
    is_admin, err = require_admin()
    if not is_admin:
        return err

    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset   = (page - 1) * per_page
    status   = request.args.get("status")          # status filter

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if status:
            if status not in VALID_STATUSES:
                return jsonify({"error": f"Invalid status. Choose from {VALID_STATUSES}"}), 400
            cursor.execute("""
                SELECT OrderID, UserID, OrderDate, TotalPrice, Status, PaymentMethod
                FROM Orders
                WHERE Status = ?
                ORDER BY OrderDate DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """, (status, offset, per_page))
        else:
            cursor.execute("""
                SELECT OrderID, UserID, OrderDate, TotalPrice, Status, PaymentMethod
                FROM Orders
                ORDER BY OrderDate DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """, (offset, per_page))

        rows = cursor.fetchall()
        orders = []
        for row in rows:
            orders.append({
                "order_id":       row[0],
                "user_id":        row[1],
                "order_date":     row[2].strftime("%Y-%m-%d %H:%M:%S") if row[2] else None,
                "total_price":    round(float(row[3]), 2),
                "status":         row[4],
                "payment_method": row[5]
            })
        return jsonify({
            "page":     page,
            "per_page": per_page,
            "orders":   orders
        }), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve orders"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: UPDATE ORDER STATUS 
@order_bp.route("/admin/orders/<int:order_id>/status", methods=["PUT"])
@jwt_required()
def admin_update_order_status(order_id):
    is_admin, err = require_admin()
    if not is_admin:
        return err

    data   = request.json
    status = data.get("status") if data else None

    if not status or status not in VALID_STATUSES:
        return jsonify({"error": f"Valid statuses: {VALID_STATUSES}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT OrderID FROM Orders WHERE OrderID = ?
        """, (order_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Order not found"}), 404

        cursor.execute("""
            UPDATE Orders SET Status = ? WHERE OrderID = ?
        """, (status, order_id))
        conn.commit()
        return jsonify({
            "message": f"Order {order_id} status updated to '{status}'"
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update order status"}), 500
    finally:
        cursor.close()
        conn.close()