import secrets
from configparser import ConfigParser

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

alembic_config = ConfigParser()
alembic_config.read("alembic.ini")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///../app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"isolation_level": "SERIALIZABLE"}
app.config["SECRET_KEY"] = secrets.token_hex()

db = SQLAlchemy(app)

from . import routes
