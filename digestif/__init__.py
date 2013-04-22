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

import digestif.views
