class Config(object):
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:////Users/Jclarke/tmp/test.db'
    SECRET_KEY = "there are many many eyes to this world"

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = "mysql://jclarke:pepper@localhost/digestif"
    SERVER_NAME = "digestif.me"

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
