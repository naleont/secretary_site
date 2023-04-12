from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
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
    cat_site_id = db.Column('cat_site_id', db.Integer)
    year = db.Column('year', db.Integer)
    cat_name = db.Column('cat_name', db.Text)
    short_name = db.Column('short_name', db.Text)
    tg_channel = db.Column('tg_channel', db.Text)
    drive_link = db.Column('drive_link', db.Text)

    def __init__(self, year, cat_name, short_name, tg_channel, cat_site_id, drive_link):
        self.year = year
        self.cat_name = cat_name
        self.short_name = short_name
        self.tg_channel = tg_channel
        self.id_from_site = cat_site_id
        self.drive_link = drive_link


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
    __table_args__ = (PrimaryKeyConstraint('appl_id', 'user_id', 'category_1', 'category_2', 'category_3'),)

    appl_id = db.Column('appl_id', db.Integer, primary_key=True)
    user_id = db.Column('user_id', db.Integer, ForeignKey('users.user_id'), unique=False)
    year = db.Column('year', db.Integer)
    role = db.Column('role', db.Text)
    category_1 = db.Column('category_1', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    category_2 = db.Column('category_2', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    category_3 = db.Column('category_3', db.Integer, ForeignKey('categories.cat_id'), unique=False)
    any_category = db.Column('any_category', db.Boolean)
    taken_part = db.Column('taken_part', db.Text)
    considered = db.Column('considered', db.Text)

    def __init__(self, appl_id, user_id, year, role, category_1, category_2, category_3, any_category, taken_part, considered):
        self.appl_id = appl_id
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

    work_id = db.Column('work_id', db.Integer, primary_key=True)
    work_name = db.Column('work_name', db.Text)
    work_site_id = db.Column('work_site_id', db.Integer)
    email = db.Column('email', db.Text)
    tel = db.Column('tel', db.Text)
    author_1_name = db.Column('author_1_name', db.Text)
    author_1_age = db.Column('author_1_age', db.Integer)
    author_1_class = db.Column('author_1_class', db.Integer)
    author_2_name = db.Column('author_2_name', db.Text)
    author_2_age = db.Column('author_2_age', db.Integer)
    author_2_class = db.Column('author_2_class', db.Integer)
    author_3_name = db.Column('author_3_name', db.Text)
    author_3_age = db.Column('author_3_age', db.Integer)
    author_3_class = db.Column('author_3_class', db.Integer)
    teacher_name = db.Column('teacher_name', db.Text)
    reg_tour = db.Column('reg_tour', db.Text)
    msk_time_shift = db.Column('msk_time_shift', db.Integer)
    reported = db.Column('reported', db.Boolean)

    def __init__(self, work_id, work_name, work_site_id, email, tel, author_1_name, author_1_age, author_1_class,
                 author_2_name, author_2_age, author_2_class, author_3_name, author_3_age, author_3_class, teacher_name,
                 reg_tour, msk_time_shift, reported):
        self.work_id = work_id
        self.work_name = work_name
        self.work_site_id = work_site_id
        self.email = email
        self.tel = tel
        self.author_1_name = author_1_name
        self.author_1_age = author_1_age
        self.author_1_class = author_1_class
        self.author_2_name = author_2_name
        self.author_2_age = author_2_age
        self.author_2_class = author_2_class
        self.author_3_name = author_3_name
        self.author_3_age = author_3_age
        self.author_3_class = author_3_class
        self.teacher_name = teacher_name
        self.reg_tour = reg_tour
        self.msk_time_shift = msk_time_shift
        self.reported = reported


class WorkCategories(db.Model):
    __tablename__ = 'work_cats'
    __table_args__ = (PrimaryKeyConstraint('cat_id', 'work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('categories.cat_id'))
    cat_id = db.Column('cat_id', db.Integer, ForeignKey('categories.cat_id'), unique=False)

    def __init__(self, work_id, cat_id):
        self.work_id = work_id
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


class RevCriteria(db.Model):
    __tableneme__ = 'rev_criteria'

    criterion_id = db.Column('criterion_id', db.Integer, primary_key=True)
    criterion_name = db.Column('criterion_name', db.Text)
    criterion_description = db.Column('criterion_description', db.Text)
    year = db.Column('year', db.Date)
    weight = db.Column('weight', db.Integer)

    def __init__(self, criterion_name, criterion_description, year, weight):
        self.criterion_name = criterion_name
        self.criterion_description = criterion_description
        self.year = year
        self.weight = weight


class RevCritValues(db.Model):
    __tableneme__ = 'rev_crit_values'

    value_id = db.Column('value_id', db.Integer, primary_key=True)
    value_name = db.Column('value_name', db.Text)
    comment = db.Column('comment', db.Text)
    weight = db.Column('weight', db.Integer)

    def __init__(self, value_name, comment, weight):
        self.value_name = value_name
        self.comment = comment
        self.weight = weight


class CriteriaValues(db.Model):
    __tablename__ = 'crit_values'
    __table_args__ = (PrimaryKeyConstraint('criterion_id', 'value_id'),)

    criterion_id = db.Column('criterion_id', db.Integer, ForeignKey('rev_criteria.criterion_id'), unique=False)
    value_id = db.Column('value_id', db.Integer, ForeignKey('rev_criteria.criterion_id'))

    def __init__(self, criterion_id, value_id):
        self.criterion_id = criterion_id
        self.value_id = value_id


class PreAnalysis(db.Model):
    __tablename__ = 'pre_analysis'
    __table_args__ = (PrimaryKeyConstraint('work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    good_work = db.Column('good_work', db.Boolean)
    research = db.Column('research', db.Text)
    has_review = db.Column('has_review', db.Boolean)
    rev_type = db.Column('rev_type', db.Text)
    pushed = db.Column('pushed', db.Boolean)
    work_comment = db.Column('work_comment', db.Text)
    rev_comment = db.Column('rev_comment', db.Text)

    def __init__(self, work_id, good_work, research, has_review, rev_type, pushed, work_comment, rev_comment):
        self.work_id = work_id
        self.good_work = good_work
        self.research = research
        self.has_review = has_review
        self.rev_type = rev_type
        self.pushed = pushed
        self.work_comment = work_comment
        self.rev_comment = rev_comment


class RevAnalysis(db.Model):
    __tablename__ = 'rev_analysis'
    __table_args__ = (PrimaryKeyConstraint('work_id', 'criterion_id', 'value_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    criterion_id = db.Column('criterion_id', db.Integer, ForeignKey('rev_criteria.criterion_id'), unique=False)
    value_id = db.Column('value_id', db.Integer, ForeignKey('rev_crit_values.value_id'), unique=False)

    def __init__(self, work_id, criterion_id, value_id):
        self.work_id = work_id
        self.criterion_id = criterion_id
        self.value_id = value_id


class RevComment(db.Model):
    __tablename__ = 'review_comment'
    __table_args__ = (PrimaryKeyConstraint('work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    work_comment = db.Column('work_comment', db.Text)
    rev_comment = db.Column('rev_comment', db.Text)

    def __init__(self, work_id, work_comment, rev_comment):
        self.work_id = work_id
        self.work_comment = work_comment
        self.rev_comment = rev_comment


class ParticipationStatuses(db.Model):
    __tablename__ = 'participation_statuses'

    status_id = db.Column('status_id', db.Integer, primary_key=True)
    status_name = db.Column('status_name', db.Text)

    def __init__(self, status_id, status_name):
        self.status_id = status_id
        self.status_name = status_name


class WorkStatuses(db.Model):
    __tablename__ = 'work_statuses'
    __table_args__ = (PrimaryKeyConstraint('work_id', 'status_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    status_id = db.Column('status_id', db.Integer, primary_key=True)

    def __init__(self, work_id, status_id):
        self.work_id = work_id
        self.status_id = status_id


class WorksNoFee(db.Model):
    __tablename__ = 'works_no_fee'
    __table_args__ = (PrimaryKeyConstraint('work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))

    def __init__(self, work_id):
        self.work_id = work_id


class ReportDates(db.Model):
    __tablename__ = 'report_dates'
    __table_args__ = (PrimaryKeyConstraint('cat_id'),)

    cat_id = db.Column('cat_id', db.Integer, ForeignKey('categories.cat_id'))
    day_1 = db.Column('day_1', db.Date)
    day_2 = db.Column('day_2', db.Date)
    day_3 = db.Column('day_3', db.Date)

    def __init__(self, cat_id, day_1, day_2, day_3):
        self.cat_id = cat_id
        self.day_1 = day_1
        self.day_2 = day_2
        self.day_3 = day_3


class Applications2Tour(db.Model):
    __tablename__ = 'applications_2_tour'
    __table_args__ = (PrimaryKeyConstraint('work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    appl_no = db.Column('appl_no', db.Integer)
    arrived = db.Column('arrived', db.Boolean)

    def __init__(self, work_id, appl_no, arrived):
        self.work_id = work_id
        self.appl_no = appl_no
        self.arrived = arrived


class ParticipantsApplied(db.Model):
    __tablename__ = 'participants_applied'

    participant_id = db.Column('participant_id', db.Integer, primary_key=True)
    appl_id = db.Column('appl_id', db.Integer)
    last_name = db.Column('last_name', db.Text)
    first_name = db.Column('first_name', db.Text)
    patronymic_name = db.Column('patronymic_name', db.Text)
    participant_class = db.Column('participant_class', db.Text)
    role = db.Column('role', db.Text)
    work_id = db.Column('work_id', db.Integer)

    def __init__(self, participant_id, appl_id, last_name, first_name, patronymic_name, participant_class, role, work_id):
        self.participant_id = participant_id
        self.appl_id = appl_id
        self.last_name = last_name
        self.first_name = first_name
        self.patronymic_name = patronymic_name
        self.participant_class = participant_class
        self.role = role
        self.work_id = work_id


class ReportOrder(db.Model):
    __tablename__ = 'report_order'
    __table_args__ = (PrimaryKeyConstraint('work_id'),)

    work_id = db.Column('work_id', db.Integer, ForeignKey('works.work_id'))
    report_day = db.Column('report_day', db.Text)
    order = db.Column('order', db.Integer)

    def __init__(self, work_id, report_day, order):
        self.work_id = work_id
        self.report_day = report_day
        self.order = order


class Cities(db.Model):
    __tablename__ = 'cities'

    city_id = db.Column('city_id', db.Integer, primary_key=True)
    country = db.Column('country', db.Text)
    region = db.Column('region', db.Text)
    area = db.Column('area', db.Text)
    city = db.Column('city', db.Text)
    msk_time_shift = db.Column('msk_time_shift', db.Integer)

    def __init__(self, country, region, area, city, msk_time_shift):
        self.country = country
        self.region = region
        self.area = area
        self.city = city
        self.msk_time_shift = msk_time_shift


class ParticipationFormat(db.Model):
    __tablename__ = 'participation_format'

    format_id = db.Column('format_id', db.Integer, primary_key=True)
    participant_id = db.Column('participant_id', db.Integer)
    work_id = db.Column('work_id', db.Integer)
    format = db.Column('format', db.Text)

    def __init__(self, participant_id, work_id, format):
        self.participant_id = participant_id
        self.work_id = work_id
        self.format = format


class Discounts(db.Model):
    __tablename__ = 'discounts'

    discount_id = db.Column('discount_id', db.Integer, primary_key=True)
    participant_id = db.Column('participant_id', db.Integer)
    work_id = db.Column('work_id', db.Integer)
    payment = db.Column('payment', db.Integer)
    participation_format = db.Column('participation_format', db.Text)

    def __init__(self, participant_id, work_id, payment, participation_format):
        self.participant_id = participant_id
        self.work_id = work_id
        self.payment = payment
        self.participation_format = participation_format


class BankStatement(db.Model):
    __tablename__ = 'bank_statement'

    payment_id = db.Column('payment_id', db.Integer, primary_key=True)
    date = db.Column('date', db.Date)
    order_id = db.Column('order_id', db.Integer)
    debit = db.Column('debit', db.Float)
    credit = db.Column('credit', db.Float)
    organisation = db.Column('organisation', db.Text)
    tin = db.Column('tin', db.Text)
    bic = db.Column('bic', db.Text)
    bank_name = db.Column('bank_name', db.Text)
    account = db.Column('account', db.Text)
    payment_comment = db.Column('payment_comment', db.Text)

    def __init__(self, date, order_id, debit, credit, organisation, tin, bic, bank_name, account, payment_comment):
        self.date = date
        self.order_id = order_id
        self.debit = debit
        self.credit = credit
        self.organisation = organisation
        self.tin = tin
        self.bic = bic
        self.bank_name = bank_name
        self.account = account
        self.payment_comment = payment_comment


class PaymentRegistration(db.Model):
    __tablename__ = 'payment_registration'

    payment_reg_id = db.Column('payment_reg_id', db.Integer, primary_key=True)
    payment_id = db.Column('payment_id', db.Integer)
    participant = db.Column('participant', db.Integer)
    for_work = db.Column('for_work', db.Boolean)

    def __init__(self, payment_id, participant, for_work):
        self.payment_id = payment_id
        self.participant = participant
        self.for_work = for_work
