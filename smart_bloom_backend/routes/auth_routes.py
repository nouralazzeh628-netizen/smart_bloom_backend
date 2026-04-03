from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from db import get_db_connection

auth_bp = Blueprint("auth", __name__)

#login
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    if not data or "email" not in data or "password" not in data:
        return jsonify({"error": "Email and password are required"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT UserID, Role
            FROM Users
            WHERE Email = ? AND Password = ?
        """, (data["email"], data["password"]))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        user_id = user[0]
        role = user[1]
        access_token = create_access_token(
            identity=str(user_id), 
            additional_claims={"role": role}
        )
        return jsonify({
            "message": "Login successful",
            "access_token": access_token
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()