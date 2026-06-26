from flask import Flask
from flask_cors import CORS
from config import Config
from database.db import init_db

# Import blueprints
from routes.auth import auth_bp
from routes.user import user_bp
from routes.lockers import lockers_bp
from routes.bookings import bookings_bp
from routes.payment import payment_bp
from routes.esp32 import esp32_bp
from routes.rental import rental_bp
from routes.admin import admin_bp
from routes.web import web_bp

def create_app():
    """Application factory for the Smart Locker Backend."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Enable CORS for cross-origin mobile app calls
    CORS(app)
    
    # Initialize database
    init_db()
    
    # Initialize Firebase Admin and MQTT services
    from services.firebase_service import init_firebase
    from services.mqtt_service import init_mqtt
    init_firebase()
    init_mqtt()
    
    # Sync lockers from SQLite to Firestore on startup
    try:
        from models.locker import LockerModel
        from services.firebase_service import sync_locker_status
        lockers = LockerModel.get_all()
        for locker in lockers:
            sync_locker_status(locker['locker_id'], locker['status'])
        print(f">>> Synced {len(lockers)} lockers to Firestore on startup.")
    except Exception as e:
        print(f">>> Failed to sync lockers on startup: {e}")
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(lockers_bp)
    app.register_blueprint(bookings_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(esp32_bp)
    app.register_blueprint(rental_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(web_bp)
    
    @app.route("/health", methods=["GET"])
    def health_check():
        return {"status": "healthy", "service": "smart-locker-backend"}, 200

    return app

if __name__ == "__main__":
    app = create_app()
    print("=" * 60)
    print("  Smart Locker Backend Modular Server Running")
    print("  Host: 0.0.0.0 | Port: 5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
