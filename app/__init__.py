import os
from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+ os.path.join(base_dir, 'database.db')
CORS(app)

from app import views
from app import models
