from flask_sqlalchemy import SQLAlchemy
from app import app

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.Text)


class Movement(db.Model):
    __tablename__ = 'movement'

    movement_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    start_location_lat = db.Column(db.REAL)
    start_location_lng = db.Column(db.REAL)
    end_location_lat = db.Column(db.REAL)
    end_location_lng = db.Column(db.REAL)
    start_timestamp = db.Column(db.TEXT)
    end_timestamp = db.Column(db.TEXT)
    user = db.relationship('User', backref=db.backref('movement_user', lazy=True))


class Waypoint(db.Model):
    __tablename__ = 'waypoint'

    waypoint_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    movement_id = db.Column(db.Integer, db.ForeignKey('movement.movement_id'))
    waypoint_order = db.Column(db.Integer)
    location_lat = db.Column(db.REAL)
    location_lng = db.Column(db.REAL)
    user = db.relationship('User', backref=db.backref('waypoint_user', lazy=True))
    movement = db.relationship('Movement', backref=db.backref('waypoint_movement', lazy=True))


class Visit(db.Model):
    __tablename__ = 'visit'

    visit_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    location_lat = db.Column(db.REAL)
    location_lng = db.Column(db.REAL)
    start_timestamp = db.Column(db.TEXT)
    end_timestamp = db.Column(db.TEXT)
    user = db.relationship('User', backref=db.backref('visit_user', lazy=True))


class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transaction'

    transaction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    transaction_type = db.Column(db.TEXT)
    amount = db.Column(db.REAL)
    location_lat = db.Column(db.REAL)
    location_lng = db.Column(db.REAL)
    transaction_timestamp = db.Column(db.TEXT)
    user = db.relationship('User', backref=db.backref('transaction_user', lazy=True))


with app.app_context():
    db.create_all()
