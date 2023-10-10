import unittest
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import asymmetric, serialization
from flask import Flask

from membrane.client.flask import (
    User,
    configure_membrane,
    login_user,
    membrane_current_user,
    membrane_login_required,
)


def generate_key_pair():
    private_key = asymmetric.rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem.decode("utf-8"), public_pem.decode("utf-8")


class Config:
    """Custom flask config with Membrane activated for tests."""

    MEMBRANE_SERVER = "http://test_server"
    SECRET_KEY = "test"
    ALGORITHM = "RS256"
    CLIENT_PRIVATE_KEY, CLIENT_PUBLIC_KEY = generate_key_pair()
    SERVER_PRIVATE_KEY, SERVER_PUBLIC_KEY = generate_key_pair()
    PERMANENT_SESSION_LIFETIME = 300
    TOKEN_EXPIRES_IN_SECONDS = 300
    APP_ID = "test_app"
    REDIRECT_PATH = "/"
    TESTING = True


def create_test_app(config: Config):
    app = Flask(__name__)
    app.config.from_object(config)

    # Register Membrane's auth blueprint
    from membrane.client.flask import blueprint as membrane_blueprint

    app.register_blueprint(membrane_blueprint)

    # Configure Membrane login.
    certificate_data = {
        "app_id": config.APP_ID,
        "server_public_key": config.SERVER_PUBLIC_KEY,
        "client_private_key": config.CLIENT_PRIVATE_KEY,
        "auth_url": config.MEMBRANE_SERVER,
    }
    configure_membrane(
        active=bool(config.MEMBRANE_SERVER),
        app=app,
        certificate=certificate_data,
        token_expiration=config.TOKEN_EXPIRES_IN_SECONDS,
        custom_claims=None,
        redirect_path=config.REDIRECT_PATH,
    )

    @app.route("/")
    @membrane_login_required
    def protected_endpoint():
        user = (
            membrane_current_user.id
            if hasattr(membrane_current_user, "id")
            else "world"
        )
        return f"Hello, {user}!"

    return app


class TestMembranePackage(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.app = create_test_app(self.config)
        self.client = self.app.test_client(True)

    def test_no_user_redirect(self):
        """Test that a user is redirected to the Membrane server when not logged in."""
        with self.app.test_request_context():
            # Vars
            exp = datetime.utcnow()
            exp += timedelta(seconds=self.config.TOKEN_EXPIRES_IN_SECONDS)
            exp = int(exp.timestamp())
            alg = self.config.ALGORITHM
            app_id = self.config.APP_ID
            key = self.config.CLIENT_PUBLIC_KEY
            redirect_url = "http://localhost" + self.config.REDIRECT_PATH
            # Request
            response = self.client.get("/")
            # Check redirect and redirect url
            self.assertEqual(response.status_code, 302)
            location = response.headers["Location"]
            self.assertTrue(location.startswith(self.config.MEMBRANE_SERVER))
            parsed_url = urlparse(location)
            query_params = parse_qs(parsed_url.query)
            self.assertTrue("token" in query_params)
            # Check JWT headers
            token = query_params["token"][0]
            try:
                jwt_header = jwt.get_unverified_header(token)
            except Exception as e:
                self.fail(f"Failed to get JWT header: {e}")
            self.assertTrue("alg" in jwt_header)
            self.assertEqual(jwt_header["alg"], alg)
            self.assertEqual(jwt_header["app_id"], app_id)
            # Check JWT payload
            try:
                decoded_token = jwt.decode(token, key, algorithms=[alg])
                self.assertIsNotNone(decoded_token)
            except jwt.InvalidTokenError:
                self.fail("Token could not be decoded")
            self.assertEqual(decoded_token["app_id"], app_id)
            self.assertEqual(decoded_token["redirect_url"], redirect_url)
            self.assertLessEqual(decoded_token["exp"], exp + 1)

    def test_user_logged_in(self):
        """Test that a logged-in user can access the protected endpoint."""
        with self.app.test_request_context():
            # Vars
            test_email = "user@example.com"
            test_user = User(test_email)
            login_user(test_user)
            # Request
            response = self.client.get("/")
            # Checks
            self.assertEqual(response.status_code, 200)
            response_data = response.data.decode("utf-8")
            self.assertEqual(response_data, f"Hello, {test_email}!")

    def test_no_user_with_valid_token(self):
        """Test that a user with a valid token is authenticated and can access the
        protected endpoint."""
        with self.app.test_request_context():
            # Vars
            test_email = "test@example.com"
            redirect_url = "http://localhost/some_redirect"
            exp = datetime.utcnow()
            exp += timedelta(seconds=self.config.TOKEN_EXPIRES_IN_SECONDS)
            exp = int(exp.timestamp())
            payload = {
                "sub": test_email,
                "exp": exp,
                self.config.REDIRECT_PATH: redirect_url,
            }
            token = jwt.encode(
                payload, self.config.SERVER_PRIVATE_KEY, algorithm=self.config.ALGORITHM
            )
            with self.client as c:
                # Request the protected endpoint with a valid token
                response = c.get(f"/?token={token}")
                self.assertEqual(response.status_code, 302)
                self.assertTrue("Set-Cookie" in response.headers)
                self.assertTrue(hasattr(membrane_current_user, "id"))
                self.assertEqual(membrane_current_user.id, test_email)
                # Request the protected endpoint with the session cookie
                redirected_response = c.get("/")
                self.assertEqual(redirected_response.status_code, 200)
                response_data = redirected_response.data.decode("utf-8")
                self.assertEqual(response_data, f"Hello, {test_email}!")

    # TODO: test membrane blueprint routes


if __name__ == "__main__":
    unittest.main()
