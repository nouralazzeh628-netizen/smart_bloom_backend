from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from db import get_db_connection

flower_bp = Blueprint("flower", __name__)


# HELPER: role guard
def require_admin():
    """Returns (True, None) if admin, else (False, error_response)."""
    claims = get_jwt()
    if claims.get("role") != "Admin":
        return False, (jsonify({"error": "Admin access required"}), 403)
    return True, None


#  GET ALL FLOWERS public
@flower_bp.route("/flowers", methods=["GET"])
def get_flowers():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT FlowerID, FlowerName, Price, Stock, ImageURL
            FROM Flower
            WHERE IsActive = 1
            ORDER BY FlowerID
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, per_page))
        rows = cursor.fetchall()

        flowers = []
        for row in rows:
            flowers.append({
                "flower_id": row[0],
                "flower_name": row[1],
                "price": float(row[2]),
                "stock": row[3],          
                "image_url": row[4]
            })
        return jsonify({"page": page, "per_page": per_page, "flowers": flowers}), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve flowers"}), 500
    finally:
        cursor.close()
        conn.close()


#GET SINGLE FLOWER BY ID public
@flower_bp.route("/flowers/<int:flower_id>", methods=["GET"])
def get_flower_by_id(flower_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT FlowerID, FlowerName, Price, Stock, ImageURL
            FROM Flower
            WHERE FlowerID = ? AND IsActive = 1
        """, (flower_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Flower not found"}), 404

        return jsonify({
            "flower_id": row[0],
            "flower_name": row[1],
            "price": float(row[2]),
            "stock": row[3],
            "image_url": row[4]
        }), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve flower"}), 500
    finally:
        cursor.close()
        conn.close()


#SMART SEARCH: flowers + bouquets public

@flower_bp.route("/flowers/search", methods=["GET"])
def search_flowers():
    query = request.args.get("name", "").strip()
    min_price = request.args.get("min_price", type=float)  
    max_price = request.args.get("max_price", type=float)

    if not query:
        return jsonify({"error": "Please provide a name to search"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Build dynamic flower query with optional price filter
        flower_sql = """
            SELECT FlowerID, FlowerName, Price, Stock, ImageURL
            FROM Flower
            WHERE FlowerName LIKE ? AND IsActive = 1
        """
        flower_params = ['%' + query + '%']

        if min_price is not None:
            flower_sql += " AND Price >= ?"
            flower_params.append(min_price)
        if max_price is not None:
            flower_sql += " AND Price <= ?"
            flower_params.append(max_price)

        cursor.execute(flower_sql, flower_params)
        flower_rows = cursor.fetchall()

        # Bouquet search by name or flower contents
        cursor.execute("""
            SELECT DISTINCT b.BouquetID, b.Name, b.Price, b.ImageURL, b.Description
            FROM Bouquet b
            LEFT JOIN BouquetFlowers bf ON b.BouquetID = bf.BouquetID
            LEFT JOIN Flower f ON bf.FlowerID = f.FlowerID
            WHERE b.Name LIKE ? OR f.FlowerName LIKE ?
        """, ('%' + query + '%', '%' + query + '%'))
        bouquet_rows = cursor.fetchall()

        return jsonify({
            "individual_flowers": [
                {
                    "flower_id": row[0],
                    "flower_name": row[1],
                    "price": float(row[2]),
                    "stock": row[3],
                    "image_url": row[4]
                } for row in flower_rows
            ],
            "bouquets": [
                {
                    "bouquet_id": row[0],
                    "name": row[1],
                    "price": float(row[2]),
                    "image_url": row[3],
                    "description": row[4]
                } for row in bouquet_rows
            ]
        }), 200

    except Exception as e:
        return jsonify({"error": "Search failed"}), 500
    finally:
        cursor.close()
        conn.close()


#  BEST SELLERS public
@flower_bp.route("/flowers/best-sellers", methods=["GET"])
def best_selling_flowers():                  
    limit = request.args.get("limit", 10, type=int)  #

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT TOP (?) 
                   f.FlowerID,
                   f.FlowerName,
                   SUM(od.Quantity)           AS TotalSold,
                   SUM(od.Quantity * od.Price) AS TotalRevenue,
                   MAX(f.ImageURL)            AS ImageURL
            FROM Order_Details od
            JOIN Flower f ON od.FlowerID = f.FlowerID
            GROUP BY f.FlowerID, f.FlowerName
            ORDER BY TotalSold DESC
        """, (limit,))
        rows = cursor.fetchall()

        return jsonify([
            {
                "flower_id": row[0],         
                "flower_name": row[1],
                "total_sold": row[2],
                "revenue": round(float(row[3]), 2) if row[3] else 0.0,
                "image_url": row[4]
            } for row in rows
        ]), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve best sellers"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: ADD FLOWER
@flower_bp.route("/flowers", methods=["POST"])
@jwt_required()
def add_flower():
    is_admin, err = require_admin()
    if not is_admin:
        return err

    data = request.json
    required = ["flower_name", "price", "stock", "image_url"]
    if not data or not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400
    if data["price"] <= 0 or data["stock"] < 0:
        return jsonify({"error": "Price must be > 0 and stock >= 0"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Flower (FlowerName, Price, Stock, ImageURL, IsActive)
            OUTPUT INSERTED.FlowerID
            VALUES (?, ?, ?, ?, 1)
        """, (data["flower_name"], data["price"], data["stock"], data["image_url"]))
        flower_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Flower added", "flower_id": flower_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not add flower"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: UPDATE FLOWER 
@flower_bp.route("/flowers/<int:flower_id>", methods=["PUT"])
@jwt_required()
def update_flower(flower_id):
    is_admin, err = require_admin()
    if not is_admin:
        return err

    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = {"flower_name", "price", "stock", "image_url"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": f"Updatable fields: {list(allowed)}"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        COLUMN_MAP = {
           "flower_name": "FlowerName",
           "price":       "Price",
           "stock":       "Stock",
           "image_url":   "ImageURL"
                }
        set_clause = ", ".join(f"{COLUMN_MAP[k]} = ?" for k in updates)
        values = list(updates.values()) + [flower_id]
        cursor.execute(f"""
            UPDATE Flower SET {set_clause}
            WHERE FlowerID = ?
        """, values)
        conn.commit()
        return jsonify({"message": "Flower updated"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update flower"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: DEACTIVATE FLOWER (soft delete) 
@flower_bp.route("/flowers/<int:flower_id>", methods=["DELETE"])
@jwt_required()
def delete_flower(flower_id):
    is_admin, err = require_admin()
    if not is_admin:
        return err

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE Flower SET IsActive = 0 WHERE FlowerID = ?
        """, (flower_id,))
        conn.commit()
        return jsonify({"message": "Flower deactivated"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not deactivate flower"}), 500
    finally:
        cursor.close()
        conn.close()