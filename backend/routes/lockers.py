from flask import Blueprint
from models.locker import LockerModel
from utils.helpers import json_response

lockers_bp = Blueprint("lockers", __name__)

@lockers_bp.route("/api/lockers", methods=["GET"])
def get_lockers():
    """Retrieve all lockers in the system."""
    lockers = LockerModel.get_all()
    return json_response(
        success=True,
        message="Lockers retrieved successfully",
        data=lockers
    )

@lockers_bp.route("/api/lockers/available", methods=["GET"])
def get_available_lockers():
    """Retrieve all available lockers."""
    lockers = LockerModel.get_available()
    return json_response(
        success=True,
        message="Available lockers retrieved successfully",
        data=lockers
    )

@lockers_bp.route("/api/lockers/<locker_id>", methods=["GET"])
def get_locker(locker_id):
    """Retrieve details of a specific locker by ID."""
    locker = LockerModel.get_by_id(locker_id)
    if not locker:
        return json_response(
            success=False,
            message=f"Locker with ID '{locker_id}' not found",
            status_code=404
        )
    return json_response(
        success=True,
        message="Locker details retrieved successfully",
        data=locker
    )
