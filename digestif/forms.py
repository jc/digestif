from flask.ext.wtf import Form
from wtforms import TextField, validators, HiddenField, SelectField

class RegisterStream(Form):
    email = TextField("Email", [validators.Email()])
    ot = HiddenField("ot")
    ots = HiddenField("ots")
    remote = HiddenField("remote")

class SubscribeForm(Form):
    email = TextField("Email", [validators.Email()])
    frequency = SelectField("Frequency", choices=[("1", "upto once a day"),
                                                  ("3", "every three days"),
                                                  ("7", "every week"),
                                                  ("14", "every two weeks"),
                                                  ("0", "unsubscribe")])
    stream = HiddenField("stream")
