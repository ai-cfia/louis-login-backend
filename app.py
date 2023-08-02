"""
CFIA Louis Backend Flask Application
"""
import logging
from datetime import timedelta
from jwt.exceptions import InvalidTokenError
from flask_jwt_extended import JWTManager, create_access_token, decode_token
from flask import Flask, request, jsonify, session, make_response, redirect, url_for
from flask_session import Session
from utils import is_valid_email

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'super-secret'  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=60)  # Set token expiry time
jwt = JWTManager(app)

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

@app.route('/login', methods=['POST'])
def login():
    """
    This endpoint handles user login. It receives an email and a redirect URL via a POST request.
    If the email is valid and if the user is not already authenticated, a JWT token is created 
    and a verification URL, which includes the token as a query parameter, is sent to the user's 
    email.
    
    Parameters:
    None, but expects a JSON object in the request body with 'email' and 'redirect_url' keys.

    Returns:
    A JSON response object and an HTTP status code. The response object contains a 'message' or 
    'error' key depending on the result of the request.

    The possible outcomes are:
    - Returns a 200 HTTP status code and a message that the user is already authenticated if the 
      user
      is already authenticated.
    - Returns a 200 HTTP status code and a message that the email is valid and the JWT link has 
      been sent if
      the email is valid and the user is not authenticated.
    - Returns a 400 HTTP status code and an error message if the email is invalid.
    - Returns a 400 HTTP status code and an error message if the email or the redirect URL are not 
      provided.
    """
    data = request.get_json()
    email = data.get('email')
    redirect_url = data.get('redirect_url')

    if email is None or redirect_url is None:
        return jsonify({'error': 'Missing email or redirect URL.'}), 400

    if is_valid_email(email):
        if 'authenticated' in session and session['authenticated']:
            return jsonify({'message': 'Already authenticated.'}), 200

        additional_claims = {"redirect_url": redirect_url}
        access_token = create_access_token(identity=email, additional_claims=additional_claims)
        verification_url = url_for('verify_token', token=access_token, _external=True)

        print(verification_url)
        return jsonify({'message': 'Valid email address. Email sent with JWT link.'}), 200

    # Note: No 'else' block here
    return jsonify({'error': 'Invalid email address.'}), 400

@app.route('/verify_token', methods=['GET'])
def verify_token():
    """
    Handle the verification of the JWT token received via the link.

    Returns:
        - If the token is valid and not expired, set the session variables
          'authenticated' and 'user_email' and redirect the user to the dashboard.
        - If the token is expired or invalid, return a JSON response with an error message.
    """
    token = request.args.get('token')  # Extract token from URL parameters

    if token is None:
        return jsonify({'error': 'No token provided.'}), 400

    try:
        print("Received token:", token)  # Print the received token
        # Decode and verify the JWT token using the app's secret key
        decoded_token = decode_token(token)
        print("Decoded token:", decoded_token)  # Print the decoded token
        email = decoded_token['sub']
        redirect_url = decoded_token['redirect_url']  # Extract the redirect URL from the token

        # Set the 'authenticated' key in the session dictionary to indicate that the user is authenticated
        session['authenticated'] = True
        session['user_email'] = email

        # Redirect to the extracted URL
        response = make_response(redirect(redirect_url, code=302))
        return response

    except InvalidTokenError as invalid_token_error:
        # Log the exception message to inspect the reason for the decoding failure
        logging.error('JWT Token decoding error: %s', invalid_token_error)
        return jsonify({'error': 'Invalid token.'}), 400

if __name__ == '__main__':
    app.run(debug=True)
