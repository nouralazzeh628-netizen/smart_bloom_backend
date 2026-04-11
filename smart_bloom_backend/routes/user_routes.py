from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
import re
from routes.utils import EMAIL_PATTERN, validate_password, is_valid_email

user_bp = Blueprint("user", __name__)


# HELPERS 
def require_admin():
    claims = get_jwt()
    if claims.get("role") != "Admin":          
        return False, (jsonify({"error": "Admin access required"}), 403)
    return True, None

# ADMIN: GET ALL USERS
@user_bp.route("/users", methods=["GET"])
@jwt_required()
def get_all_users():
    is_admin, err = require_admin()
    if not is_admin:
        return err

    page     = request.args.get("page", 1, type=int)     # pagination
    per_page = request.args.get("per_page", 20, type=int)
    offset   = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT UserID, UserName, Email, Address, Role
            FROM Users
            ORDER BY UserID
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (offset, per_page))
        rows = cursor.fetchall()

        return jsonify({
            "page": page,
            "per_page": per_page,
            "users": [
                {
                    "user_id":  row[0],
                    "username": row[1],
                    "email":    row[2],
                    "address":  row[3],
                    "role":     row[4]
                } for row in rows
            ]
        }), 200

    except Exception:
        return jsonify({"error": "Could not retrieve users"}), 500
    finally:
        cursor.close()
        conn.close()

# GET CURRENT USER PROFILE
@user_bp.route("/me", methods=["GET"])
@jwt_required()
def get_my_profile():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT UserID, UserName, Email, Address, Role
            FROM Users WHERE UserID = ?
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "user_id":  user[0],
            "username": user[1],
            "email":    user[2],
            "address":  user[3],
            "role":     user[4]
        }), 200

    except Exception:
        return jsonify({"error": "Could not retrieve profile"}), 500
    finally:
        cursor.close()
        conn.close()


#ADMIN: GET SINGLE USER
@user_bp.route("/users/<int:user_id>", methods=["GET"])
@jwt_required()                                 
def get_user(user_id):
    is_admin, err = require_admin()
    if not is_admin:
        return err

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT UserID, UserName, Email, Address, Role
            FROM Users WHERE UserID = ?
        """, (user_id,))                        
        user = cursor.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "user_id":  user[0],               
            "username": user[1],
            "email":    user[2],
            "address":  user[3],
            "role":     user[4]
        }), 200

    except Exception:
        return jsonify({"error": "Could not retrieve user"}), 500
    finally:
        cursor.close()
        conn.close()


#UPDATE PROFILE (own account)
@user_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_my_profile():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = {"username", "email", "address"}
    updates = {k: v.strip() for k, v in data.items() if k in allowed and v}
    if not updates:
        return jsonify({"error": f"Updatable fields: {list(allowed)}"}), 400

    if "email" in updates and not re.match(EMAIL_PATTERN, updates["email"]):
        return jsonify({"error": "Invalid email format"}), 400
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [user_id]
    cursor.execute(f"""
    UPDATE Users SET {set_clause} WHERE UserID = ?
                    """, values)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if "email" in updates:
            cursor.execute("""
                SELECT UserID FROM Users WHERE Email = ? AND UserID != ?
            """, (updates["email"], user_id))
            if cursor.fetchone():
                return jsonify({"error": "Email already in use"}), 409

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        cursor.execute(f"""
            UPDATE Users SET {set_clause} WHERE UserID = ?
        """, values)
        conn.commit()
        return jsonify({"message": "Profile updated successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not update profile"}), 500
    finally:
        cursor.close()
        conn.close()


# CHANGE PASSWORD
@user_bp.route("/me/password", methods=["PUT"])
@jwt_required()
def change_password():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    old_password = data.get("old_password") if data else None
    new_password = data.get("new_password") if data else None

    if not old_password or not new_password:
        return jsonify({"error": "old_password and new_password are required"}), 400

    valid, msg = validate_password(new_password)
    if not valid:
        return jsonify({"error": msg}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Password FROM Users WHERE UserID = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not check_password_hash(row[0], old_password):
            return jsonify({"error": "Current password is incorrect"}), 401

        cursor.execute("""
            UPDATE Users SET Password = ? WHERE UserID = ?
        """, (generate_password_hash(new_password), user_id))
        conn.commit()
        return jsonify({"message": "Password changed successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not change password"}), 500
    finally:
        cursor.close()
        conn.close()


# ADMIN: DELETE USER
@user_bp.route("/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
    
def delete_user(user_id):
    is_admin, err = require_admin()
    if not is_admin:
        return err

    if user_id == int(get_jwt_identity()):
        return jsonify({"error": "You cannot delete your own account"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT UserID FROM Users WHERE UserID = ?", (user_id,))
        if not cursor.fetchone():
            return jsonify({"error": "User not found"}), 404

        cursor.execute("DELETE FROM Users WHERE UserID = ?", (user_id,))
        conn.commit()
        return jsonify({"message": "User deleted successfully"}), 200

    except Exception:
        conn.rollback()
        return jsonify({"error": "Could not delete user"}), 500
    finally:
        cursor.close()
        conn.close()