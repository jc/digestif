from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash, _app_ctx_stack

import json
from datetime import datetime, timedelta
from flask_oauth import OAuth

from flask.ext.sqlalchemy import SQLAlchemy

# configuration
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////Users/Jclarke/tmp/test.db'
db = SQLAlchemy(app)

database = []

oauth = OAuth()
flickr_oauth = oauth.remote_app('flickr',
    base_url='http://www.flickr.com/services/oauth/',
    request_token_url='http://www.flickr.com/services/oauth/request_token',
    access_token_url='http://www.flickr.com/services/oauth/access_token',
    authorize_url='http://www.flickr.com/services/oauth/authenticate',
    consumer_key='2e5cac297c49277e40b8f518713ae9c0',
    consumer_secret='8f5a126939b68737',
    request_token_params={"perms" : "read"})

from digestif.models import Entry

# subscriber, email address, secret
# subscription, subscriber, publisher, max frequency, last mail out
# publisher, account, secret
# flickr account, publisher, blah blah blah
# photo, account, date published, img_mail, img_web, title, caption, permalink


import digestif.views 


def load_json(filename):
    data = json.load(open(filename, "r"))
    for photo in data["photos"]["photo"]:
        database.append(Entry({"main_src" : photo["url_c"], \
                                   "caption" : photo["title"], \
                                   "date" : datetime.fromtimestamp(int(photo["dateupload"]))}))
    
