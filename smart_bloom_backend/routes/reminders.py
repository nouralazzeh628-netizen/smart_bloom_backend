from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime
from db import get_db_connection

reminders_bp = Blueprint("reminders", __name__)

NOTIFICATION_TEMPLATE = "Reminder: Your occasion '{name}' is coming up on {date}. Order a bouquet now!"

FIELD_MAP = {
    "occasion_name": "OccasionName",
    "occasion_date": "OccasionDate",
    "days_before":   "DaysBefore"
}

OCCASION_KEYWORDS = {
    "birthday":    "Birthday",
    "birth":       "Birthday",
    "wedding":     "Wedding",
    "marry":       "Wedding",
    "marriage":    "Wedding",
    "bride":       "Wedding",
    "baby":        "New Baby",
    "newborn":     "New Baby",
    "born":        "New Baby",
    "shower":      "New Baby",
    "graduation":  "Graduation",
    "graduate":    "Graduation",
    "grad":        "Graduation",
    "mother":      "Mother Day",
    "mom":         "Mother Day",
    "mum":         "Mother Day",
    "love":        "Love",
    "valentine":   "Love",
    "anniversary": "Love",
    "romance":     "Love",
}


# HELPER: admin guard
def require_admin():
    claims = get_jwt()
    if claims.get("role", "").lower() != "admin":
        return False, (jsonify({"error": "Admin access required"}), 403)
    return True, None


# ADD REMINDER

@reminders_bp.route("/reminders", methods=["POST"])
@jwt_required()
def add_reminder():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    occ_name    = data.get("occasion_name", "").strip()
    occ_date    = data.get("occasion_date")
    days_before = data.get("days_before", 1)

    if not occ_name or not occ_date:
        return jsonify({"error": "occasion_name and occasion_date are required"}), 400

    # Validate date format
    try:
        parsed_date = datetime.strptime(occ_date, "%Y-%m-%d").date()
        if parsed_date < datetime.today().date():
            return jsonify({"error": "occasion_date must be in the future"}), 400
    except ValueError:
        return jsonify({"error": "occasion_date must be in YYYY-MM-DD format"}), 400

    # Validate days_before
    if not isinstance(days_before, int) or not (1 <= days_before <= 365):
        return jsonify({"error": "days_before must be a positive integer between 1 and 365"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Duplicate check
        cursor.execute("""
            SELECT ReminderID FROM Occasion_Reminders
            WHERE UserID = ? AND OccasionName = ? AND OccasionDate = ? AND IsActive = 1
        """, (user_id, occ_name, occ_date))
        if cursor.fetchone():
            return jsonify({"error": "A reminder for this occasion already exists"}), 409

        cursor.execute("""
            INSERT INTO Occasion_Reminders (UserID, OccasionName, OccasionDate, DaysBefore)
            OUTPUT INSERTED.ReminderID
            VALUES (?, ?, ?, ?)
        """, (user_id, occ_name, occ_date, days_before))
        reminder_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "message": "Reminder created successfully",
            "reminder_id": reminder_id
        }), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not create reminder"}), 500
    finally:
        cursor.close()
        conn.close()


# GET MY REMINDERS (with smart suggestions)
@reminders_bp.route("/reminders", methods=["GET"])
@jwt_required()
def get_my_reminders():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor  = conn.cursor()
    cursor2 = conn.cursor()  # separate cursor for inner queries
    try:
        cursor.execute("""
            SELECT ReminderID, OccasionName, OccasionDate, DaysBefore
            FROM Occasion_Reminders
            WHERE UserID = ? AND IsActive = 1
            ORDER BY OccasionDate ASC
        """, (user_id,))
        rows = cursor.fetchall()

        result = []
        for row in rows:
            reminder_id, occ_name, occ_date, days_before = row

            # Match user's occasion name to a DB Occasion value via keywords
            occ_lower = occ_name.lower()
            matched_occasion = next(
                (db_val for keyword, db_val in OCCASION_KEYWORDS.items() if keyword in occ_lower),
                None
            )

            if matched_occasion:
                cursor2.execute("""
                    SELECT TOP 3 FlowerID, FlowerName, Price, ImageURL
                    FROM Flower
                    WHERE Occasion LIKE ? AND IsActive = 1 AND Stock > 0
                    ORDER BY NEWID()
                """, (f"%{matched_occasion}%",))
                suggestions = cursor2.fetchall()
            else:
                suggestions = []

            # Fallback: return random flowers if no keyword matched or no results
            if not suggestions:
                cursor2.execute("""
                    SELECT TOP 3 FlowerID, FlowerName, Price, ImageURL
                    FROM Flower
                    WHERE IsActive = 1 AND Stock > 0
                    ORDER BY NEWID()
                """)
                suggestions = cursor2.fetchall()

            result.append({
                "reminder_id": reminder_id,
                "occasion":    occ_name,
                "date":        occ_date.strftime("%Y-%m-%d") if occ_date else None,
                "days_before": days_before,
                "smart_suggestions": [
                    {
                        "flower_id":   s[0],
                        "flower_name": s[1],
                        "price":       float(s[2]),
                        "image_url":   s[3]
                    } for s in suggestions
                ]
            })

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve reminders"}), 500
    finally:
        cursor2.close()
        cursor.close()
        conn.close()


# UPDATE REMINDER
@reminders_bp.route("/reminders/<int:reminder_id>", methods=["PUT"])
@jwt_required()
def update_reminder(reminder_id):
    user_id = int(get_jwt_identity())
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    allowed = {"occasion_name", "occasion_date", "days_before"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": f"Updatable fields: {list(allowed)}"}), 400

    # Validate fields if present
    if "occasion_date" in updates:
        try:
            parsed = datetime.strptime(updates["occasion_date"], "%Y-%m-%d").date()
            if parsed < datetime.today().date():
                return jsonify({"error": "occasion_date must be in the future"}), 400
        except ValueError:
            return jsonify({"error": "occasion_date must be YYYY-MM-DD"}), 400

    if "days_before" in updates:
        if not isinstance(updates["days_before"], int) or not (1 <= updates["days_before"] <= 365):
            return jsonify({"error": "days_before must be a positive integer between 1 and 365"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Verify ownership
        cursor.execute("""
            SELECT ReminderID FROM Occasion_Reminders
            WHERE ReminderID = ? AND UserID = ? AND IsActive = 1
        """, (reminder_id, user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Reminder not found"}), 404

        # Map request keys to actual DB column names
        set_clause = ", ".join(f"{FIELD_MAP[k]} = ?" for k in updates)

        if "occasion_date" in updates or "days_before" in updates:
         set_clause += ", IsNotified = 0"

         values = list(updates.values()) + [reminder_id]

         cursor.execute(f"""
                        UPDATE Occasion_Reminders
                        SET {set_clause}
                        WHERE ReminderID = ?
                        """, values)

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update reminder"}), 500
    finally:
        cursor.close()
        conn.close()


# DELETE (DEACTIVATE) REMINDER

@reminders_bp.route("/reminders/<int:reminder_id>", methods=["DELETE"])
@jwt_required()
def delete_reminder(reminder_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ReminderID FROM Occasion_Reminders
            WHERE ReminderID = ? AND UserID = ? AND IsActive = 1
        """, (reminder_id, user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Reminder not found"}), 404

        cursor.execute("""
            UPDATE Occasion_Reminders SET IsActive = 0
            WHERE ReminderID = ?
        """, (reminder_id,))
        conn.commit()
        return jsonify({"message": "Reminder deleted"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not delete reminder"}), 500
    finally:
        cursor.close()
        conn.close()

# CHECK & SEND NOTIFICATIONS (admin/cron only)
@reminders_bp.route("/reminders/check-notifications", methods=["POST"])
@jwt_required()
def check_reminders_and_notify():
    is_admin, err = require_admin()
    if not is_admin:
        return err

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT r.ReminderID, r.UserID, r.OccasionName, r.OccasionDate, u.Email
            FROM Occasion_Reminders r
            JOIN Users u ON r.UserID = u.UserID
            WHERE r.IsActive = 1
            AND r.IsNotified = 0
            AND CAST(DATEADD(day, -r.DaysBefore, r.OccasionDate) AS DATE) = CAST(GETDATE() AS DATE)
        """)
        pending = cursor.fetchall()

        sent_count = 0
        for row in pending:
            reminder_id, user_id, occ_name, occ_date, email = row

            message = NOTIFICATION_TEMPLATE.format(
                name=occ_name,
                date=occ_date.strftime("%Y-%m-%d")
            )
            cursor.execute("""
                INSERT INTO Notifications (UserID, Message, IsRead)
                VALUES (?, ?, 0)
            """, (user_id, message))

            # Mark as notified so it doesn't fire again today
            cursor.execute("""
                UPDATE Occasion_Reminders SET IsNotified = 1
                WHERE ReminderID = ?
            """, (reminder_id,))

            sent_count += 1

        conn.commit()
        return jsonify({
            "status": "success",
            "notifications_sent": sent_count
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Notification check failed"}), 500
    finally:
        cursor.close()
        conn.close()

# GET USER NOTIFICATIONS

@reminders_bp.route("/notifications", methods=["GET"])
@jwt_required()
def get_user_notifications():
    user_id  = int(get_jwt_identity())
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    offset   = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT NotificationID, Message, IsRead, CreatedAt
            FROM Notifications
            WHERE UserID = ?
            ORDER BY CreatedAt DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, (user_id, offset, per_page))
        rows = cursor.fetchall()

        return jsonify({
            "page": page,
            "per_page": per_page,
            "notifications": [
                {
                    "id":      row[0],
                    "message": row[1],
                    "is_read": bool(row[2]),
                    "date":    row[3].strftime("%Y-%m-%d %H:%M") if row[3] else None
                } for row in rows
            ]
        }), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve notifications"}), 500
    finally:
        cursor.close()
        conn.close()

# MARK NOTIFICATION AS READ

@reminders_bp.route("/notifications/<int:notification_id>/read", methods=["PUT"])
@jwt_required()
def mark_notification_read(notification_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT NotificationID FROM Notifications
            WHERE NotificationID = ? AND UserID = ?
        """, (notification_id, user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Notification not found"}), 404

        cursor.execute("""
            UPDATE Notifications SET IsRead = 1
            WHERE NotificationID = ?
        """, (notification_id,))
        conn.commit()
        return jsonify({"message": "Notification marked as read"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not update notification"}), 500
    finally:
        cursor.close()
        conn.close()


# UNREAD NOTIFICATION COUNT

@reminders_bp.route("/notifications/unread-count", methods=["GET"])
@jwt_required()
def unread_count():
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM Notifications
            WHERE UserID = ? AND IsRead = 0
        """, (user_id,))
        count = cursor.fetchone()[0]
        return jsonify({"unread_count": count}), 200

    except Exception as e:
        return jsonify({"error": "Could not retrieve count"}), 500
    finally:
        cursor.close()
        conn.close()


# DELETE NOTIFICATION

@reminders_bp.route("/notifications/<int:notification_id>", methods=["DELETE"])
@jwt_required()
def delete_notification(notification_id):
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT NotificationID FROM Notifications
            WHERE NotificationID = ? AND UserID = ?
        """, (notification_id, user_id))
        if not cursor.fetchone():
            return jsonify({"error": "Notification not found"}), 404

        cursor.execute("""
            DELETE FROM Notifications WHERE NotificationID = ?
        """, (notification_id,))
        conn.commit()
        return jsonify({"message": "Notification deleted"}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"error": "Could not delete notification"}), 500
    finally:
        cursor.close()
        conn.close()