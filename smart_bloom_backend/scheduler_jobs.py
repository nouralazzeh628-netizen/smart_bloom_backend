from db import get_db_connection
from datetime import datetime

NOTIFICATION_TEMPLATE = "Reminder: Your occasion '{name}' is coming up on {date}. Order a bouquet now!"

def check_reminders_and_notify_job():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT r.ReminderID, r.UserID, r.OccasionName, r.OccasionDate
            FROM Occasion_Reminders r
            WHERE r.IsActive = 1
              AND r.IsNotified = 0
              AND CAST(DATEADD(day, -r.DaysBefore, r.OccasionDate) AS DATE) = CAST(GETDATE() AS DATE)
        """)
        pending = cursor.fetchall()

        sent_count = 0

        for row in pending:
            reminder_id, user_id, occ_name, occ_date = row

            message = NOTIFICATION_TEMPLATE.format(
                name=occ_name,
                date=occ_date.strftime("%Y-%m-%d")
            )

            cursor.execute("""
                INSERT INTO Notifications (UserID, Message, IsRead)
                VALUES (?, ?, 0)
            """, (user_id, message))

            cursor.execute("""
                UPDATE Occasion_Reminders
                SET IsNotified = 1
                WHERE ReminderID = ?
            """, (reminder_id,))

            sent_count += 1

        conn.commit()
        print(f"[{datetime.now()}] Notifications sent: {sent_count}")

    except Exception as e:
        conn.rollback()
        print("Scheduler job failed:", str(e))

    finally:
        cursor.close()
        conn.close()