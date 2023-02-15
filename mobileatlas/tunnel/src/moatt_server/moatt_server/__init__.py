from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from moatt_server.flask_http_auth import HttpAuth

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
#http_auth = HttpAuth(app)

from moatt_server import models, routes
