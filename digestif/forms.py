from flask.ext.wtf import Form
from wtforms import TextField, validators, HiddenField, SelectField

class SignUpStream(Form):
    email = TextField("Email address", [validators.Email()])
    stream = HiddenField("stream", [validators.AnyOf(["flickr", "instagram"])])

class SubscribeForm(Form):
    email = TextField("Email", [validators.Email()])
    frequency = SelectField("Frequency", choices=[("1", "once a day"),
                                                  ("3", "every three days"),
                                                  ("7", "every week"),
                                                  ("14", "every two weeks"),
                                                  ("0", "never. I'd like to unsubscribe")])
    stream = HiddenField("stream")

