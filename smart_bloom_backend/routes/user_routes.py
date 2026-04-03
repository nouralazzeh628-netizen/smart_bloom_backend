from flask import Blueprint, request, jsonify
from db import get_db_connection
from flask_jwt_extended import jwt_required, get_jwt
import re
#re= regular exprission 
user_bp = Blueprint("user", __name__)
#users 
@user_bp.route("/users", methods=["GET", "POST"])
@jwt_required() 
def users():
    claims = get_jwt()
    if request.method == "GET":

        if claims["role"] != "admin":
            return jsonify({"message": "Admins only!"}), 403
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
        # field check
        required_fields = ["username", "password", "email", "address"]
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"message": f"{field} is required"}), 400
        #Email validation
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_pattern, data["email"]):
            return jsonify({"message": "Invalid email format"}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        # not repited email 
        cursor.execute("SELECT * FROM Users WHERE Email = ?", (data["email"],))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return jsonify({"message": "Email already exists"}), 400
        cursor.execute("""
            INSERT INTO Users (UserName, Password, Email, Address, Role)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data["username"],
            data["password"],
            data["email"],
            data["address"],
            "user"
        ))
        # Password validation
        password = data["password"]
        if len(password) < 8:
         return jsonify({"message": "Password must be at least 8 characters long"}), 400
        if not re.search(r'[A-Z]', password):
         return jsonify({"message": "Password must contain at least one uppercase letter"}), 400
        if not re.search(r'[a-z]', password):
         return jsonify({"message": "Password must contain at least one lowercase letter"}), 400
        if not re.search(r'[0-9]', password):
         return jsonify({"message": "Password must contain at least one number"}), 400
        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', password):
         return jsonify({"message": "Password must contain at least one special character"}), 400
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        user_id = cursor.fetchone()[0]
        conn.close()
        return jsonify({
            "message": "User created successfully",
            "user_id": user_id
        }), 201
        
#get users 
@user_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE UserID = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify({
             "UserID": user[0],
             "Name": user[1],
            "Email": user[2]
                        })
    else:
        return jsonify({"message": "User not found"}), 404