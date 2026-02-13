import sqlite3
import os
import sys

def migrate_data(db_path, target_email, source_email='admin@local.host'):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get source user id
        cursor.execute("SELECT id FROM users WHERE email = ?", (source_email,))
        source_user = cursor.fetchone()
        if not source_user:
            print(f"Error: Source user {source_email} not found.")
            return
        source_id = source_user[0]

        # Get target user id
        cursor.execute("SELECT id FROM users WHERE email = ?", (target_email,))
        target_user = cursor.fetchone()
        if not target_user:
            print(f"Error: Target user {target_email} not found.")
            return
        target_id = target_user[0]

        print(f"Migrating data from {source_email} (ID: {source_id}) to {target_email} (ID: {target_id})...")

        # Update Tables
        tables = ['blocks', 'lectures', 'previous_exams', 'questions']
        for table in tables:
            cursor.execute(f"UPDATE {table} SET user_id = ? WHERE user_id = ?", (target_id, source_id))
            print(f"Updated {cursor.rowcount} rows in {table}.")

        conn.commit()
        print("Migration completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    db_file = 'data/exam.db'
    # Target email from user input (handling potential typo in prompt vs DB)
    target = 'hisukgyu@gmail.com' 
    migrate_data(db_file, target)
