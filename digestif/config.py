import keys

class Config(object):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:////Users/Jclarke/tmp/test.db'
    SECRET_KEY = keys.FLASK_SECRET
    FB_APP_ID = keys.FB_APP_ID

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = "mysql://{}:{}@localhost/digestif".format(keys.DB_USERNAME, keys.DB_PASSWORD)
    SERVER_NAME = "digestif.me"

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
