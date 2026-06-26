from flask import jsonify

def json_response(success, message, data=None, status_code=200):
    """Generates a standardized JSON response matching the project requirements."""
    response_payload = {
        "success": success,
        "message": message,
        "data": data if data is not None else {}
    }
    return jsonify(response_payload), status_code
