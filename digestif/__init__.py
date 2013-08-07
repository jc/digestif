import os

from flask import Flask

from flask_oauth import OAuth

from flask.ext.sqlalchemy import SQLAlchemy

from hashids import hashids

# configuration

app = Flask(__name__)

if os.environ.get("DIGESTIF_DEV"):
    app.config.from_object('digestif.config.DevelopmentConfig')
else:
    app.config.from_object('digestif.config.ProductionConfig')


if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    from logging import Formatter
    file_handler = RotatingFileHandler("/home/jclarke/webapps/digestifweb/logs/digestifweb.log")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    app.logger.setLevel(logging.INFO)
    for logger in [app.logger, logging.getLogger('sqlalchemy')]:
        logger.addHandler(file_handler)

db = SQLAlchemy(app)


hash_gen = hashids("twenty five people ate in holland")


oauth = OAuth()
flickr_oauth = oauth.remote_app('flickr',
    base_url='http://api.flickr.com/services/rest',
    request_token_url='http://www.flickr.com/services/oauth/request_token',
    access_token_url='http://www.flickr.com/services/oauth/access_token',
    authorize_url='http://www.flickr.com/services/oauth/authenticate',
    consumer_key='2e5cac297c49277e40b8f518713ae9c0',
    consumer_secret='8f5a126939b68737',
    request_token_params={"perms" : "read"})
instagram_oauth = oauth.remote_app('instagram',
                                   base_url='https://api.instagram.com/v1/',
                                   request_token_url=None,
                                   access_token_url='https://api.instagram.com/oauth/access_token',
                                   access_token_params={"grant_type":"authorization_code"},
                                   access_token_method="POST",
                                   authorize_url='https://api.instagram.com/oauth/authorize',
                                   consumer_key='33cd59cf6ddb47db97b21c5b6da8f109',
                                   consumer_secret='2372e400711a43acad00fe852eafcab0'
)

import digestif.views
