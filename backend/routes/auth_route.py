from flask import Blueprint, request, jsonify
from extensions import db
from model.user import User
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

auth_bp = Blueprint("auth", __name__)

# Signup
@auth_bp.route("/signup", methods=["POST"], strict_slashes=False)
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "User already exists"}), 400

    user = User(email=email, name=name, is_verified=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Create token for immediate login
    token = create_access_token(identity=str(user.id))

    return jsonify({
        "message": "Signup successful! Redirecting to dashboard...",
        "token": token
    }), 201


# Login
@auth_bp.route("/login", methods=["POST"], strict_slashes=False)
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    # Correctly queries the DB using the updated model
    user = User.query.filter_by(email=email).first()

    # Uses the plain-text check we defined in model/user.py
    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    # Generates the real token for the logged-in user
    token = create_access_token(identity=str(user.id))
    
    return jsonify({
        "message": "Login successful",
        "token": token
    }), 200


# Google Login
@auth_bp.route("/google-login", methods=["POST"], strict_slashes=False)
def google_login():
    data = request.json
    token = data.get("token")
    
    try:
        # Verify the token
        client_id = os.getenv("GOOGLE_CLIENT_ID") 
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        
        email = id_info.get("email")
        google_id = id_info.get("sub")
        name = id_info.get("name")
        picture = id_info.get("picture")

        # Check if user exists
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if user exists with email but no google_id (linked via email)
            user = User.query.filter_by(email=email).first()
            if user:
                user.google_id = google_id
                user.name = name
                user.profile_picture = picture
            else:
                # Create new user
                print(f"Creating new user: {email}")
                user = User(
                    email=email,
                    google_id=google_id,
                    name=name,
                    profile_picture=picture,
                    is_verified=True # Google users are pre-verified
                )
                db.session.add(user)
                db.session.flush() # get id before commit if needed
                print(f"User added to session, assigned ID: {user.id}")
        else:
            # Update info
            user.name = name
            user.profile_picture = picture
            if not user.is_verified:
                user.is_verified = True # Verify if they login via Google
            
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            "token": access_token,
            "user": {
                "email": user.email,
                "name": user.name,
                "picture": user.profile_picture
            }
        }), 200
        
    except ValueError as e:
        print(f"Google Token Verification Error: {e}")
        return jsonify({"message": "Invalid Google token", "error": str(e)}), 401
    except Exception as e:
        print(f"Google Login Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": "Google login failed", "error": str(e)}), 500


# Protected Route
@auth_bp.route("/protected", methods=["GET"], strict_slashes=False)
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(message=f"Welcome {current_user}, you have accessed a protected route!"), 200