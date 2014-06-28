import os

from flask import Flask
from flask_oauth import OAuth
from flask.ext.sqlalchemy import SQLAlchemy

from hashids import hashids

import keys

# configuration

app = Flask(__name__)

if os.environ.get("DIGESTIF_DEV"):
    app.config.from_object("digestif.config.DevelopmentConfig")
else:
    app.config.from_object("digestif.config.ProductionConfig")


if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    from logging import Formatter
    file_handler = RotatingFileHandler("/home/jclarke/webapps/digestifweb/logs/digestifweb.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"))
    app.logger.setLevel(logging.INFO)
    for logger in [app.logger, logging.getLogger("sqlalchemy")]:
        logger.addHandler(file_handler)

db = SQLAlchemy(app)


hash_gen = hashids(keys.HASH_GEN)


oauth = OAuth()
flickr_oauth = oauth.remote_app("flickr",
    base_url="https://api.flickr.com/services/rest",
    request_token_url="https://www.flickr.com/services/oauth/request_token",
    access_token_url="https://www.flickr.com/services/oauth/access_token",
    authorize_url="https://www.flickr.com/services/oauth/authenticate",
    consumer_key=keys.FLICKR,
    consumer_secret=keys.FLICKR_SECRET,
    request_token_params={"perms" : "read"})

instagram_oauth = oauth.remote_app("instagram",
                                   base_url="https://api.instagram.com/v1/",
                                   request_token_url=None,
                                   access_token_url="https://api.instagram.com/oauth/access_token",
                                   access_token_params={"grant_type":"authorization_code"},
                                   access_token_method="POST",
                                   authorize_url="https://api.instagram.com/oauth/authorize",
                                   consumer_key=keys.INSTAGRAM,
                                   consumer_secret=keys.INSTAGRAM_SECRET)

import digestif.views
