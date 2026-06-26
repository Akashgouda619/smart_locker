import jwt
from functools import wraps
from flask import request, jsonify, g
from config import Config
from models.user import UserModel

def token_required(f):
    """Decorator to require valid JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({
                    "success": False,
                    "message": "Token format must be Bearer <token>",
                    "data": None
                }), 401
        
        if not token:
            return jsonify({
                "success": False,
                "message": "Token is missing",
                "data": None
            }), 401
            
        try:
            # Decode the token
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            current_user = UserModel.get_by_id(payload['user_id'])
            if not current_user:
                return jsonify({
                    "success": False,
                    "message": "User not found or disabled",
                    "data": None
                }), 401
            
            # Store in Flask global context
            g.current_user = current_user
            
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "message": "Token has expired",
                "data": None
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "message": "Token is invalid",
                "data": None
            }), 401
            
        return f(*args, **kwargs)
        
    return decorated
