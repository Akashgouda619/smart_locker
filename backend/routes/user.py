from flask import Blueprint, request, g
from middleware.auth import token_required
from models.user import UserModel
from models.booking import BookingModel
from utils.helpers import json_response

user_bp = Blueprint("user", __name__)

@user_bp.route("/api/user/profile", methods=["GET"])
@token_required
def get_profile():
    """Retrieve the current user's profile information."""
    user = g.current_user
    profile_data = {
        "id": user["id"],
        "full_name": user["full_name"],
        "phone": user["phone"],
        "email": user["email"],
        "created_at": user["created_at"]
    }
    return json_response(
        success=True,
        message="Profile retrieved successfully",
        data=profile_data
    )

@user_bp.route("/api/user/profile", methods=["PUT"])
@token_required
def update_profile():
    """Update the current user's profile information."""
    user = g.current_user
    data = request.get_json() or {}
    
    full_name = data.get("full_name", user["full_name"])
    phone = data.get("phone", user["phone"])
    email = data.get("email", user["email"])

    if not full_name or not phone or not email:
        return json_response(
            success=False,
            message="Fields full_name, phone, and email cannot be empty",
            status_code=400
        )

    success = UserModel.update(user["id"], full_name, phone, email)
    if not success:
        return json_response(
            success=False,
            message="Failed to update profile. Email or Phone number might be taken.",
            status_code=400
        )
        
    updated_user = UserModel.get_by_id(user["id"])
    profile_data = {
        "id": updated_user["id"],
        "full_name": updated_user["full_name"],
        "phone": updated_user["phone"],
        "email": updated_user["email"],
        "created_at": updated_user["created_at"]
    }
    
    return json_response(
        success=True,
        message="Profile updated successfully",
        data=profile_data
    )

@user_bp.route("/api/user/bookings", methods=["GET"])
@token_required
def get_user_bookings():
    """Retrieve booking history for the current user."""
    user_id = g.current_user["id"]
    bookings = BookingModel.get_by_user(user_id)
    return json_response(
        success=True,
        message="User bookings retrieved successfully",
        data=bookings
    )
