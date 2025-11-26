from dotenv import load_dotenv
import os

load_dotenv()

client_id = os.environ.get("CLIENT_ID")
client_secret = os.environ.get("CLIENT_SECRET")
redirect_callback = os.environ.get("REDIRECT_CALLBACK")
authorization_base_url = os.environ.get("AUTHORIZATION_BASE_URL", "https://accounts.google.com/o/oauth2/auth")
token_url = os.environ.get("TOKEN_URL", "https://accounts.google.com/o/oauth2/token")
