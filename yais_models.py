from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
import datetime

db = SQLAlchemy()
db_name = 'yais_db.db'
