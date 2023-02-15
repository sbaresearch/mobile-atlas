from moatt_types.connect import ApduOp
from moatt_server import db

class Token(db.Model): # type: ignore
    __tablename__ = "tokens"

    value = db.Column(db.String(36), nullable=False, primary_key=True)
    created = db.Column(db.DateTime, nullable=False)
    expires = db.Column(db.DateTime)
    last_access = db.Column(db.DateTime)
    active = db.Column(db.Boolean, nullable=False)

class Imsi(db.Model): # type: ignore
    __tablename__ = "imsis"

    id = db.Column(db.Integer, primary_key=True)
    imsi = db.Column(db.String, nullable=False)
    # TODO: introduce another field to order history entries
    # using the timestamp is acceptable for now but not very
    # future proof
    registered = db.Column(db.DateTime, nullable=False)
    sim_iccid = db.Column(db.String, db.ForeignKey("sims.iccid"), nullable=False)
    sim = db.relationship("Sim", back_populates="imsi")


class Sim(db.Model): # type: ignore
    __tablename__ = "sims"

    iccid = db.Column(db.String, primary_key=True)
    imsi = db.relationship("Imsi", back_populates="sim")
    available = db.Column(db.Boolean, nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey("providers.id"))
    provider = db.relationship("Provider", back_populates="sims")

class Provider(db.Model): # type: ignore
    __tablename__ = "providers"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.Integer, db.ForeignKey("tokens.value"))
    session_token = db.Column(db.String, unique=True)

    sims = db.relationship("Sim", back_populates="provider")

class Probe(db.Model): # type: ignore
    __tablename__ = "probes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True)
    mac = db.Column(db.Text, index=True, unique=True)
    token = db.Column(db.Integer, db.ForeignKey("tokens.value"))

class ApduLog(db.Model): # type: ignore
    __tablename__ = "apdu_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    iccid = db.Column(db.String, db.ForeignKey("sims.iccid"))
    command = db.Column(db.Enum(ApduOp), nullable=False)
    payload = db.Column(db.LargeBinary)
