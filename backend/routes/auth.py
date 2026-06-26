import jwt
import datetime
from flask import Blueprint, request
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models.user import UserModel
from utils.helpers import json_response

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    """Endpoint for user registration."""
    data = request.get_json() or {}
    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email")
    password = data.get("password")

    if not all([full_name, phone, email, password]):
        return json_response(
            success=False,
            message="Please provide all required fields: full_name, phone, email, password",
            status_code=400
        )

    # Hash the user's password
    password_hash = generate_password_hash(password)
    
    # Try to create user
    new_user = UserModel.create(full_name, phone, email, password_hash)
    if not new_user:
        return json_response(
            success=False,
            message="User registration failed. Email or Phone number might already be registered.",
            status_code=409
        )

    # Return registered user without sensitive info
    user_data = {
        "id": new_user["id"],
        "full_name": new_user["full_name"],
        "phone": new_user["phone"],
        "email": new_user["email"],
        "created_at": new_user["created_at"]
    }
    
    return json_response(
        success=True,
        message="User registered successfully",
        data=user_data,
        status_code=201
    )

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    """Endpoint for user login. Returns JWT token on success."""
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return json_response(
            success=False,
            message="Please provide email and password",
            status_code=400
        )

    user = UserModel.get_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return json_response(
            success=False,
            message="Invalid email or password",
            status_code=401
        )

    # Generate JWT Token
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=Config.JWT_ACCESS_TOKEN_EXPIRES)
    token_payload = {
        "user_id": user["id"],
        "email": user["email"],
        "exp": expiration
    }
    
    token = jwt.encode(token_payload, Config.JWT_SECRET_KEY, algorithm="HS256")
    
    return json_response(
        success=True,
        message="Login successful",
        data={
            "token": token,
            "user": {
                "id": user["id"],
                "full_name": user["full_name"],
                "phone": user["phone"],
                "email": user["email"]
            }
        }
    )
