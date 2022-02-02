import sqlalchemy
from flask import Flask
# from flask import render_template, request
from models import db, Users, Supervisors, Categories, Application, CatSupervisors, CatSecretaries, CatDirs
# from sqlalchemy.sql import func, select
import re
import datetime
from cryptography.fernet import Fernet
from numpy import genfromtxt
import csv
#

tel_unneeded = '-()'
curr_year = 2022
access_types = {'unauthorized': 0, 'user': 1, 'approved_user': 2, 'team': 3, 'secretary': 7, 'manager': 9, 'admin': 10}

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.app = app
db.init_app(app)
db.create_all()
#
# user = db.session.query(Users).filter(Users.email == 'naleont@gmail.com')
# print(user.first().password)


cat_sec = CatSecretaries.query.filter(CatSecretaries.secretary_id == 2 and CatSecretaries.cat_id == 1).first()
db.session.delete(cat_sec)
db.session.commit()

