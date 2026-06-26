from database.db import get_db_connection

class UserModel:
    @staticmethod
    def create(full_name, phone, email, password_hash):
        """Creates a new user and returns the user dict or None if conflict."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (full_name, phone, email, password_hash) VALUES (?, ?, ?, ?)",
                (full_name, phone, email, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return UserModel.get_by_id(user_id)
        except Exception as e:
            print(f"Error creating user: {e}")
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        """Fetches a user by their email address."""
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def get_by_id(user_id):
        """Fetches a user by their internal database ID."""
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(user) if user else None

    @staticmethod
    def update(user_id, full_name, phone, email):
        """Updates user profile data."""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET full_name = ?, phone = ?, email = ? WHERE id = ?",
                (full_name, phone, email, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating user: {e}")
            return False
        finally:
            conn.close()
