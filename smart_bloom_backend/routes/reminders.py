from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from flask_jwt_extended import jwt_required, get_jwt_identity
from db import get_db_connection
reminders_bp = Blueprint("reminders", __name__)
# Occasion system - Add reminder
@reminders_bp.route("/reminders", methods=["POST"])
@jwt_required()
def add_reminder():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is empty"}), 400
    if isinstance(data, list):
        data = data[0] if len(data) > 0 else {}
    occ_name = data.get("occasion_name")
    occ_date = data.get("occasion_date")
    days_before = data.get("days_before", 1)
    if not occ_name or not occ_date:
        return jsonify({
            "error": "Missing required fields: occasion_name and occasion_date"
        }), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO Occasion_Reminders
            (UserID, OccasionName, OccasionDate, DaysBefore)
            VALUES (?, ?, ?, ?)
        """, (user_id, occ_name, occ_date, days_before))
        conn.commit()
        return jsonify({
            "message": "Reminder created successfully"
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

#user all riminders view 
# View reminders with smart suggestions
@reminders_bp.route("/reminders", methods=["GET"])
@jwt_required()
def get_my_reminders():
    user_id = int(get_jwt_identity())
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ReminderID, OccasionName, OccasionDate, DaysBefore
        FROM Occasion_Reminders
        WHERE UserID = ? AND IsActive = 1
    """, (user_id,))
    rows = cursor.fetchall()
    result = []
    for row in rows:
        reminder_id = row[0]
        occ_name = row[1]
        occ_date = row[2]
        days_before = row[3]
        # smart keyword mapping
        search_term = f"%{occ_name}%" 
        # get random suggestion
        cursor.execute("""
            SELECT TOP 3 FlowerID, FlowerName, Price, ImageURL
            FROM Flower
            WHERE (Occasion LIKE ? OR FlowerName LIKE ?)
            AND IsActive = 1
            AND Stock > 0
            ORDER BY NEWID() -- اختيار عشوائي لضمان التجديد للمستخدم
        """, (search_term, search_term))
        
        suggestions_rows = cursor.fetchall()
        suggestions_list = []
        for sug in suggestions_rows:
            suggestions_list.append({
                "flower_id": sug[0],
                "flower_name": sug[1],
                "price": float(sug[2]),
                "image_url": sug[3]
            })
        result.append({
            "reminder_id": reminder_id,
            "occasion": occ_name,
            "date": occ_date.strftime("%Y-%m-%d") if occ_date else None,
            "days_before": days_before,
            "smart_suggestions": suggestions_list if suggestions_list else "Check our new arrivals for this event!"
        })
    conn.close()
    return jsonify(result)
#notification 
@reminders_bp.route("/reminders/check-notifications", methods=["GET"])
def check_reminders_and_notify():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.UserID, r.OccasionName, r.OccasionDate, u.Email
            FROM Occasion_Reminders r
            JOIN Users u ON r.UserID = u.UserID
            WHERE r.IsActive = 1 
            AND CAST(DATEADD(day, -r.DaysBefore, r.OccasionDate) AS DATE) = CAST(GETDATE() AS DATE)
        """)
        
        pending_notifications = cursor.fetchall()
        sent_count = 0
        for row in pending_notifications:
            user_id, occ_name, occ_date, email = row
            message = f"تذكير: مناسبة {occ_name} اقتربت! موعدها في {occ_date.strftime('%Y-%m-%d')}. اطلب باقة ورد الآن!"
            cursor.execute("""
                INSERT INTO Notifications (UserID, Message)
                VALUES (?, ?)
            """, (user_id, message))
            sent_count += 1
            conn.commit()
        return jsonify({
            "status": "success",
            "notifications_sent": sent_count,
            "message": f"تم إرسال {sent_count} تنبيه بنجاح"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
#showing  notifications
@reminders_bp.route("/notifications", methods=["GET"])
@jwt_required()
def get_user_notifications():
    user_id = int(get_jwt_identity())
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT NotificationID, Message, IsRead, CreatedAt 
        FROM Notifications 
        WHERE UserID = ? 
        ORDER BY CreatedAt DESC
    """, (user_id,))
    rows = cursor.fetchall()
    notifications = []
    for row in rows:
        notifications.append({
            "id": row[0],
            "message": row[1],
            "is_read": row[2],
            "date": row[3].strftime("%Y-%m-%d %H:%M")
        })
    
    conn.close()
    return jsonify(notifications) 

        