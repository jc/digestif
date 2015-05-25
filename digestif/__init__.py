import os

from flask import Flask
from flask_oauthlib.client import OAuth
from flask.ext.sqlalchemy import SQLAlchemy

from hashids import hashids

import keys

import ssl

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context

# configuration

app = Flask(__name__)

if os.environ.get("DIGESTIF_DEV"):
    app.config.from_object("digestif.config.DevelopmentConfig")
else:
    app.config.from_object("digestif.config.ProductionConfig")

ADMINS = ['james@jamesclarke.net']
mail_format = '''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
'''
if not app.debug:
    import logging
    from logging.handlers import TimedRotatingFileHandler
    from logging import Formatter
    from logging.handlers import SMTPHandler
    mail_handler = SMTPHandler(keys.SMTP_SERVER, 'server@digestif.me', ADMINS, 'Digestif has ERRORS', credentials=(keys.SMTP_USER, keys.SMTP_PASSWORD))
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(Formatter(mail_format))
    file_handler = TimedRotatingFileHandler("/home/jclarke/webapps/digestifweb/logs/digestifweb.log", when="W0", backupCount=10)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
    app.logger.setLevel(logging.INFO)
    for logger in [app.logger, logging.getLogger("sqlalchemy"), logging.getLogger('flask_oauthlib')]:
        logger.addHandler(file_handler)
        logger.addHandler(mail_handler)

db = SQLAlchemy(app)


hash_gen = hashids(keys.HASH_GEN)


oauth = OAuth()
flickr_oauth = oauth.remote_app("flickr",
    base_url="https://api.flickr.com/services/rest",
    request_token_url="https://www.flickr.com/services/oauth/request_token",
    access_token_url="https://www.flickr.com/services/oauth/access_token",
    authorize_url="https://www.flickr.com/services/oauth/authenticate",
    consumer_key=keys.FLICKR,
    consumer_secret=keys.FLICKR_SECRET)

instagram_oauth = oauth.remote_app("instagram",
                                   base_url="https://api.instagram.com/v1/",
                                   request_token_url=None,
                                   access_token_url="https://api.instagram.com/oauth/access_token",
                                   access_token_method="POST",
                                   authorize_url="https://api.instagram.com/oauth/authorize",
                                   consumer_key=keys.INSTAGRAM,
                                   consumer_secret=keys.INSTAGRAM_SECRET)

import digestif.views
