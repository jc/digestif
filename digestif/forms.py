from flask.ext.wtf import Form
from wtforms import TextField, validators, HiddenField, SelectField

class SignUpStream(Form):
    email = TextField("Email address", [validators.Email()])
    stream = HiddenField("stream", [validators.AnyOf(["flickr", "instagram"])])

class SubscribeForm(Form):
    email = TextField("Email", [validators.Email()])
    frequency = HiddenField("frequency", [validators.AnyOf(["0", "1", "2", "3", "7", "14"])]) 

