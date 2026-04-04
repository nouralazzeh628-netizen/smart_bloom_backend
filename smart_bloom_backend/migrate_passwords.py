# migrate_passwords.py
from werkzeug.security import generate_password_hash
from db import get_db_connection

def migrate():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT UserID, Password FROM Users")
    users = cursor.fetchall()

    migrated = 0
    skipped  = 0

    for user in users:
        user_id, password = user

        if password and password.startswith("pbkdf2"):
            print(f"  Skipping UserID {user_id} — already hashed")
            skipped += 1
            continue

        hashed = generate_password_hash(password)
        cursor.execute("UPDATE Users SET Password = ? WHERE UserID = ?", (hashed, user_id))
        print(f"  Migrated UserID {user_id}")
        migrated += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nDone! Migrated: {migrated} | Skipped: {skipped}")

if __name__ == "__main__":
    migrate()