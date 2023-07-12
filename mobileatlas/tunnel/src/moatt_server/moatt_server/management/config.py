import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'REDACTED'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.environ.get('REDIS_URL') or "redis://localhost:REDACTED/0"

    LONG_POLLING_INTERVAL = os.environ.get('LONG_POLLING_INTERVAL') or 60

    BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME') or 'REDACTED'
    BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD') or 'REDACTED'

    # current config on mobileatlas legacy
    WIREGUARD_DIR = os.environ.get('WIREGUARD_DIR') or '/tmp/wireguard'
    WIREGUARD_ENDPOINT = os.environ.get('WIREGUARD_ENDPOINT') or 'REDACTED:REDACTED'
    WIREGUARD_PUBLIC_KEY = os.environ.get('WIREGUARD_PUBLIC_KEY') or 'REDACTED'
    WIREGUARD_ALLOWED_IPS = os.environ.get('WIREGUARD_ALLOWED_IPS') or '0.0.0.0/0'
    WIREGUARD_DNS = os.environ.get('WIREGUARD_DNS') or 'REDACTED'
