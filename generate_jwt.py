"""
Utility script to generate JWT tokens for testing and development.
"""
from datetime import datetime, timedelta

import jwt


def generate_jwt(data, priv_key, headers=None):
    """
    Generate a JWT using the given data and private key.
    """
    # Set the expiration time for the JWT
    if "exp" not in data:
        # Set the expiration time for the JWT
        expiration_time = datetime.utcnow() + timedelta(seconds=5 * 60)
        expiration_timestamp = int(expiration_time.timestamp())
        data["exp"] = int(expiration_timestamp)

    # Use the default header if none is provided
    if headers is None:
        headers = {"alg": "RS256", "typ": "JWT", "app_id": "testapp1"}

    jwt_token = jwt.encode(data, priv_key, algorithm="RS256", headers=headers)
    return jwt_token


if __name__ == "__main__":
    # Load the private key
    with open("tests/client_private_keys/testapp1_private_key.pem", "rb") as f:
        private_key_content = f.read()

    # Sample data with a redirect_url and app_id
    sample_data = {
        "app_id": "testapp1",  # specify the app_id here
        "redirect_url": "https://www.google.com/",
    }

    # Generate the JWT
    GENERATED_JWT = generate_jwt(sample_data, private_key_content)
    print(f"Generated JWT: {GENERATED_JWT}")
