from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from db import get_db_connection
flower_bp = Blueprint("flower", __name__)
# Flowers route 
@flower_bp.route("/flowers", methods=["GET"])
def get_Flower():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT FlowerID, FlowerName, Price, ImageURL
    FROM Flower
    WHERE IsActive = 1
""")
    rows = cursor.fetchall()
    Flower = []
    for row in rows:
        Flower.append({
            "id": row[0],    # FlowerID
            "name": row[1],  # Name
            "price": float(row[2]),  # Price
            "image_url": row[3] #pic
        })
    conn.close()
    return jsonify(Flower)

# search for a flower 
@flower_bp.route("/flowers/search", methods=["GET"])
def search_flowers():
    search_query = request.args.get('name', '')
    if not search_query:
        return jsonify({"message": "Please provide a flower name to search"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT FlowerID, FlowerName, Price, Stock, ImageURL 
        FROM Flower 
        WHERE FlowerName LIKE ? AND IsActive = 1
    """, ('%' + search_query + '%',))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        results.append({
            "flower_id": row[0],
            "flower_name": row[1],
            "price": float(row[2]),
            "stock": row[3],
            "image_url": row[4] 
        })
    return jsonify(results), 200
# Best selling flowers
@flower_bp.route("/flowers/best-sellers", methods=["GET"])
@jwt_required()
def best_selling_flowers():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT f.FlowerName,
               SUM(od.Quantity) AS TotalSold,
               SUM(od.Quantity * od.Price) AS TotalRevenue,
               MAX(f.ImageURL) AS ImageURL
        FROM Order_Details od
        JOIN Flower f ON od.FlowerID = f.FlowerID
        GROUP BY f.FlowerName
        ORDER BY TotalSold DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            "flower": row[0],
            "total_sold": row[1],
            "revenue": float(row[2]) if row[2] else 0.0,
            "image_url": row[3] 
        })
    return jsonify(result)

# Search for Flowers and Bouquets (Smart Search)
@flower_bp.route("/flowers/search", methods=["GET"])
def search_flowers_and_bouquets():
    search_query = request.args.get('name', '')
    if not search_query:
        return jsonify({"message": "Please provide a name to search"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    # Flowers search
    cursor.execute("""
        SELECT FlowerID, FlowerName, Price, Stock, ImageURL 
        FROM Flower 
        WHERE FlowerName LIKE ? AND IsActive = 1
    """, ('%' + search_query + '%',))
    flower_rows = cursor.fetchall()
    
    # Bouquets search by name or items 
    cursor.execute("""
        SELECT DISTINCT b.BouquetID, b.Name, b.Price, b.ImageURL, b.Description
        FROM Bouquet b
        LEFT JOIN BouquetFlowers bf ON b.BouquetID = bf.BouquetID
        LEFT JOIN Flower f ON bf.FlowerID = f.FlowerID
        WHERE b.Name LIKE ? 
           OR f.FlowerName LIKE ?
    """, ('%' + search_query + '%', '%' + search_query + '%'))
    bouquet_rows = cursor.fetchall()
    conn.close()
    # result handaling 
    results = {
        "individual_flowers": [],
        "bouquets": []
    }
    for row in flower_rows:
        results["individual_flowers"].append({
            "id": row[0],
            "name": row[1],
            "price": float(row[2]),
            "stock": row[3],
            "image": row[4]
        })
    for row in bouquet_rows:
        results["bouquets"].append({
            "id": row[0],
            "name": row[1],
            "price": float(row[2]),
            "image": row[3],
            "description": row[4]
        })
    return jsonify(results), 200