from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_redis import FlaskRedis
from flask_basicauth import BasicAuth
from moatt_server.config import MamConfig

app = Flask(__name__)
app.config.from_object(MamConfig)
db = SQLAlchemy(app)
redis_client = FlaskRedis(app)
basic_auth = BasicAuth(app)

from moatt_server.management import token_routes, wireguard_routes, probe_routes, routes # pyright: ignore
