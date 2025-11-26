from flask import redirect, request, url_for, session
from requests_oauthlib import OAuth2Session
from flask.views import MethodView
from oauth_config import client_id, client_secret, token_url, redirect_callback
import logging

logging.basicConfig(level=logging.INFO)

class Callback(MethodView):
    def get(self):
        oauth_state = session.get('oauth_state')
        if not oauth_state:
            logging.warning("Missing OAuth state. Redirecting to login.")
            return redirect(url_for('login'))

        google = OAuth2Session(client_id, redirect_uri=redirect_callback, state=oauth_state)

        if request.url.startswith('http:'):
            request.url = request.url.replace('http:', 'https:')

        try:
            token = google.fetch_token(
                token_url,
                client_secret=client_secret,
                authorization_response=request.url
            )
            session['oauth_token'] = token

            userinfo = google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()
            session['user_email'] = userinfo.get('email', 'Unknown')
            session['user_name'] = userinfo.get('name', 'Unknown')
            session['userinfo'] = userinfo

            logging.info(f"User {session['user_email']} logged in successfully.")

        except Exception as e:
            logging.error(f"Error during OAuth callback: {e}")
            return redirect(url_for('login'))

        return redirect(url_for('index'))
