from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_redis import FlaskRedis
from flask_basicauth import BasicAuth
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)
redis_client = FlaskRedis(app)
migrate = Migrate(app, db)
basic_auth = BasicAuth(app)

from app import wireguard_routes, probe_routes, routes, models
