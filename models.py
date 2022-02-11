from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, PrimaryKeyConstraint
import datetime

db = SQLAlchemy()
db_name = 'team_db.db'


class Users(db.Model):
    __tablename__ = 'users'

    user_id = db.Column('user_id', db.Integer, primary_key=True)
    email = db.Column('email', db.Text)
    tel = db.Column('tel', db.Text)
    password = db.Column('password', db.Text)
    last_name = db.Column('last_name', db.Text)
    first_name = db.Column('first_name', db.Text)
    patronymic = db.Column('patronymic', db.Text)
    user_type = db.Column('type', db.Text)
    approved = db.Column('approved', db.Boolean)
    created_on = db.Column(db.DateTime, index=False, unique=False, nullable=True, default=datetime.datetime.now)
    last_login = db.Column(db.DateTime, index=False, unique=False, nullable=True)

    def __init__(self, email, tel, password, last_name, first_name, patronymic, user_type, approved, last_login):
        self.email = email
        self.tel = tel
        self.password = password
        self.last_name = last_name
        self.first_name = first_name
        self.patronymic = patronymic
        self.user_type = user_type
        self.approved = approved
        self.last_login = last_login


class Profile(db.Model):
    __tablename__ = 'profile'
    __table_args__ = (PrimaryKeyConstraint('user_id'),)

    user_id = db.Column('user_id', db.Integer, ForeignKey('supervisors.supervisor_id'), primary_key=True)
    occupation = db.Column('occupation', db.Text)
    place_of_work = db.Column('place_of_work', db.Text)
    involved = db.Column('involved', db.Text)
    grade = db.Column('grade', db.Integer)
    year = db.Column('year', db.Integer)
    vk = db.Column('vk', db.Text)
    telegram = db.Column('telegram', db.Text)
    vernadsky_username = db.Column('vernadsky_username', db.Text)
    born = db.Column('born', db.Date)

    def __init__(self, user_id, occupation, place_of_work, involved, grade, year, vk, telegram,
                 vernadsky_username, born):
        self.user_id = user_id
        self.occupation = occupation
        self.place_of_work = place_of_work
        self.involved = involved
        self.grade = grade
        self.year = year
        self.vk = vk
        self.telegram = telegram
        self.vernadsky_username = vernadsky_username
        self.born = born


class Supervisors(db.Model):
    __tablename__ = 'supervisors'

    supervisor_id = db.Column('supervisor_id', db.Integer, primary_key=True)
    last_name = db.Column('last_name', db.Text)
    first_name = db.Column('first_name', db.Text)
    patronymic = db.Column('patronymic', db.Text)
    email = db.Column('email', db.Text)
    tel = db.Column('tel', db.Text)
    supervisor_info = db.Column('supervisor_info', db.Text)

    def __init__(self, last_name, first_name, patronymic, email, tel, supervisor_info):
        self.last_name = last_name
        self.first_name = first_name
        self.patronymic = patronymic
        self.email = email
        self.tel = tel
        self.supervisor_info = supervisor_info


class SupervisorUser(db.Model):
    __tablename__ = 'supervisor_user'
    __table_args__ = (PrimaryKeyConstraint('user_id', 'supervisor_id'),)

    user_id = db.Column('user_id', db.Integer, ForeignKey('users.user_id'))
    supervisor_id = db.Column('supervisor_id', db.Integer, ForeignKey('supervisors.supervisor_id'))

    def __init__(self, user_id, supervisor_id):
        self.user_id = user_id
        self.supervisor_id = supervisor_id


class Directions(db.Model):
    __tablename__ = 'directions'

    direction_id = db.Column('direction_id', db.Integer, primary_key=True, autoincrement=True)
    dir_name = db.Column('dir_name', db.Text)

    def __init__(self, dir_name):
        self.dir_name = dir_name


class Contests(db.Model):
    __tablename__ = 'contests'

    contest_id = db.Column('contest_id', db.Integer, primary_key=True, autoincrement=True)
    contest_name = db.Column('contest_name', db.Text)

    def __init__(self, contest_name):
        self.contest_name = contest_name


class Categories(db.Model):
    __tablename__ = 'categories'

    cat_id = db.Column('cat_id', db.Integer, primary_key=True)
    year = db.Column('year', db.Integer)
    cat_name = db.Column('cat_name', db.Text)
    short_name = db.Column('short_name', db.Text)
    tg_channel = db.Column('tg_channel', db.Text)

    def __init__(self, year, cat_name, short_name, tg_channel):
        self.year = year
        self.cat_name = cat_name
        self.short_name = short_name
        self.tg_channel = tg_channel


class CatDirs(db.Model):
    __tablename__ = 'cat_dir_contest'
    __table_args__ = (PrimaryKeyConstraint('cat_id', 'direction_id', 'contest_id'),)

    cat_id = db.Column('cat_id', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    dir_id = db.Column('direction_id', db.Integer, ForeignKey('directions.direction_id'), unique=False)
    contest_id = db.Column('contest_id', db.Integer, ForeignKey('contests.contest_id'), unique=False)

    def __init__(self, cat_id, dir_id, contest_id):
        self.cat_id = cat_id
        self.dir_id = dir_id
        self.contest_id = contest_id


class Application(db.Model):
    __tablename__ = 'team_application'
    __table_args__ = (PrimaryKeyConstraint('user_id', 'category_1', 'category_2', 'category_3'),)

    user_id = db.Column('user_id', db.Integer, ForeignKey('users.user_id'), unique=True)
    year = db.Column('year', db.Integer)
    role = db.Column('role', db.Text)
    category_1 = db.Column('category_1', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    category_2 = db.Column('category_2', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    category_3 = db.Column('category_3', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    any_category = db.Column('any_category', db.Boolean)
    taken_part = db.Column('taken_part', db.Text)
    considered = db.Column('considered', db.Text)

    def __init__(self, user_id, year, role, category_1, category_2, category_3, any_category, taken_part, considered):
        self.user_id = user_id
        self.year = year
        self.role = role
        self.category_1 = category_1
        self.category_2 = category_2
        self.category_3 = category_3
        self.any_category = any_category
        self.taken_part = taken_part
        self.considered = considered


class CatSupervisors(db.Model):
    __tablename__ = 'cats_supervisors'
    __table_args__ = (PrimaryKeyConstraint('category_id', 'supervisor_id'),)

    cat_id = db.Column('category_id', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    supervisor_id = db.Column('supervisor_id', db.Integer, ForeignKey('supervisors.supervisor_id'), unique=False)

    def __init__(self, cat_id, supervisor_id):
        self.cat_id = cat_id
        self.supervisor_id = supervisor_id


class CatSecretaries(db.Model):
    __tablename__ = 'cats_secretaries'
    __table_args__ = (PrimaryKeyConstraint('category_id', 'secretary_id'),)

    cat_id = db.Column('category_id', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    secretary_id = db.Column('secretary_id', db.Integer, ForeignKey('users.user_id'), unique=False)

    def __init__(self, cat_id, secretary_id):
        self.cat_id = cat_id
        self.secretary_id = secretary_id


class Works(db.Model):
    __tablename__ = 'works'
    __table_args__ = (PrimaryKeyConstraint('cat_id'),)

    work_id = db.Column('work_id', db.Integer, primary_key=True)
    work_name = db.Column('work_name', db.Integer)
    cat_id = db.Column('cat_id', db.Integer, ForeignKey('categories.cat_id'), unique=False)

    def __init__(self, work_id, work_name, cat_id):
        self.work_id = work_id
        self.work_name = work_name
        self.cat_id = cat_id


class News(db.Model):
    __tablename__ = 'news'

    news_id = db.Column('news_id', db.Integer, primary_key=True)
    date_time = db.Column('date', db.DateTime, default=datetime.datetime.now())
    title = db.Column('title', db.Text)
    content = db.Column('content', db.Text)
    access = db.Column('access', db.Text)
    publish = db.Column('publish', db.Boolean)

    def __init__(self, title, content, access, publish):
        self.title = title
        self.content = content
        self.access = access
        self.publish = publish


# class RevCriteria(db.Model):
#     __tableneme__ = 'rev_criteria'
#
#     criterion_id = db.Column('criterion_id', db.Integer, primary_key=True)
#     criterion_name = db.Column('criterion_name', db.Text)
#
#     def __init__(self, criterion_name):
#         self.criterion_name = criterion_name
#
#
# class RevCritValues(db.Model):
#     __tableneme__ = 'rev_crit_values'
#     # __table_args__ = (PrimaryKeyConstraint('criterion_id'),)
#
#     value_id = db.Column('value_id', db.Integer, primary_key=True)
#     value_name = db.Column('value_name', db.Text)
#     criterion_id = db.Column('criterion_id', db.Integer, ForeignKey('rev_criteria.criterion_id'), unique=False)
#
#     def __init__(self, value_name, criterion_id):
#         self.value_name = value_name
#         self.criterion_id = criterion_id
#
#
# class RevAnalysis(db.Model):
#     __tablename__ = 'rev_analysis'
#     __table_args__ = (PrimaryKeyConstraint('work_id', 'criterion_id', 'value_id'),)
#
#     work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
#     criterion_id = db.Column('criterion_id', db.Integer, ForeignKey('rev_criteria.criterion_id'))
#     value_id = db.Column('value_id', db.Integer, ForeignKey('rev_crit_values.value_id'))
#
#     def __init__(self, work_id, criterion_id, value_id):
#         self.work_id = work_id
#         self.criterion_id = criterion_id
#         self.value_id = value_id
