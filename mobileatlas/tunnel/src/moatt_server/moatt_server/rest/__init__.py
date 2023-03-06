import secrets

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from configparser import ConfigParser

alembic_config = ConfigParser()
alembic_config.read("alembic.ini")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///../app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = secrets.token_hex()

db = SQLAlchemy(app)
#http_auth = HttpAuth(app)

from moatt_server.rest import routes
