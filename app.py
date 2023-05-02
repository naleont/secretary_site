import datetime
import json
import os
import re

import dateutil.rrule
import requests
from cryptography.fernet import Fernet
from flask import Flask
from flask import render_template, request, redirect, url_for, session
from flask import send_file
from flask_mail import Mail, Message

import mail_data
from models import *

from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

import pandas as pd

app = Flask(__name__, instance_relative_config=False)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///team_db.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.app_context().push()
db.app = app
db.init_app(app)
db.create_all()

app.config['SECRET_KEY'] = mail_data.mail['SECRET_KEY']

app.config['MAIL_SERVER'] = mail_data.mail['MAIL_SERVER']
app.config['MAIL_PORT'] = mail_data.mail['MAIL_PORT']
app.config['MAIL_USERNAME'] = mail_data.mail['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = mail_data.mail['MAIL_PASSWORD']
app.config['MAIL_USE_TLS'] = mail_data.mail['MAIL_USE_TLS']
app.config['MAIL_USE_SSL'] = mail_data.mail['MAIL_USE_SSL']

mail = Mail(app)

tel_unneeded = '-() '
curr_year = 2023
fee = 4800
tour_fee = 3900

days = {'1': 'Пн', '2': 'Вт', '3': 'Ср', '4': 'Чт', '5': 'Пт', '6': 'Сб', '0': 'Вс'}
days_full = {'1': 'Понедельник',
             '2': 'Вторник',
             '3': 'Среда',
             '4': 'Четверг',
             '5': 'Пятница',
             '6': 'Суббота',
             '0': 'Воскресенье'}
months = {'01': 'Янв',
          '02': 'Фев',
          '03': 'Мар',
          '04': 'Апр',
          '05': 'Май',
          '06': 'Июн',
          '07': 'Июл',
          '08': 'Авг',
          '09': 'Сен',
          '10': 'Окт',
          '11': 'Ноя',
          '12': 'Дек'}
months_full = {'01': 'Января',
               '02': 'Февраля',
               '03': 'Марта',
               '04': 'Апреля',
               '05': 'Мая',
               '06': 'Июня',
               '07': 'Июля',
               '08': 'Августа',
               '09': 'Сентября',
               '10': 'Октября',
               '11': 'Ноября',
               '12': 'Декабря'}

access_types = {'guest': 0,
                'user': 1,
                'approved_user': 2,
                'team': 3,
                'secretary': 5,
                'supervisor': 6,
                'org': 8,
                'manager': 9,
                'admin': 10}


def renew_session():
    if 'user_id' in session.keys():
        user_db = db.session.query(Users).filter(Users.user_id == session['user_id']).first()
        if user_db is not None:
            cat_sec = db.session.query(CatSecretaries).filter(CatSecretaries.secretary_id == session['user_id']).all()
            user = session['user_id']
            session['type'] = user_db.user_type
            session['approved'] = user_db.approved
            if user in [u.secretary_id for u in CatSecretaries.query.all()]:
                session['secretary'] = True
                session['cat_id'] = [c.cat_id for c in cat_sec]
            if user in [u.user_id for u in SupervisorUser.query.all()]:
                session['supervisor'] = True
                supervisor = SupervisorUser.query.filter(SupervisorUser.user_id == user).first()
                if supervisor.supervisor_id in [s.supervisor_id for s in CatSupervisors.query.all()]:
                    cat_sup = CatSupervisors.query.filter(CatSupervisors.supervisor_id == supervisor.supervisor_id
                                                          ).all()
                    session['cat_id'] = [c.cat_id for c in cat_sup]
            else:
                session['supervisor'] = False
            if user in [p.user_id for p in Profile.query.all()]:
                session['profile'] = True
            if user in [a.user_id for a in Application.query.filter(Application.year == curr_year)]:
                session['application'] = True
            else:
                session['application'] = False
    return session


def check_access(url):
    renew_session()
    if 'type' in session.keys():
        if session['type'] == 'admin':
            session['access'] = 10
            return 10
        elif session['type'] == 'manager':
            session['access'] = 9
            return 9
        elif session['type'] == 'org':
            session['access'] = 8
            return 8
        elif 'supervisor' in session.keys() and session['supervisor'] is True:
            session['access'] = 6
            return 6
        elif 'secretary' in session.keys() and session['secretary'] is True:
            session['access'] = 5
            return 5
        elif session['type'] == 'team':
            session['access'] = 3
            return 3
        elif session['approved'] is True:
            session['access'] = 2
            return 2
        elif 'user_id' in session.keys():
            session['access'] = 1
            return 1
    else:
        session['url'] = url
        session['access'] = 0
        return 0


def create_key():
    key = Fernet.generate_key()
    file = open('secret.key', 'wb')
    file.write(key)
    file.close()
    return key


# Загрузка ключа шифрования
def load_key():
    if not os.path.isfile('secret.key'):
        create_key()
    return open("secret.key", "rb").read()


# Шифрование текста в переменной message
def encrypt(message):
    key = load_key()
    encoded_message = message.encode()
    f = Fernet(key)
    encrypted = f.encrypt(encoded_message)
    return encrypted


# Расшифровка текста в переменной encrypted_message
def decrypt(encrypted_message):
    key = load_key()
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_message)
    return decrypted.decode()


# Отправка письма для подтверждения регистрации на адрес email
def send_email(email):
    user_id = db.session.query(Users).filter(Users.email == email).first().user_id
    link = 'http://org.vernadsky.info/approve/' + str(user_id)
    msg = Message(subject='Подтверждение e-mail',
                  body='Это подтверждение вашей регистрации на сайте для секретарей Конкурса им. В. И.'
                       'Вернадского. Перейдите по ссылке для подтверждения email: ' + link,
                  sender=('Команда Конкурса', 'team@vernadsky.info'),
                  recipients=[email])
    mail.send(msg)


def find_user(user_got):
    tel = re.sub(r'^8|^7|^(?=9)', '+7', ''.join([n for n in user_got if n not in tel_unneeded]))
    if user_got in [user.email for user in Users.query.all()]:
        user = db.session.query(Users).filter(Users.email == user_got).first()
    elif tel in [user.tel for user in Users.query.all()]:
        user = db.session.query(Users).filter(Users.tel == tel).first()
    else:
        return None
    return user


def personal_info_form():
    info = dict()
    info['email'] = request.form['email']
    tel_n = request.form['tel']
    info['tel'] = re.sub(r'^8|^7|^(?=9)', '+7', ''.join([n for n in tel_n if n not in tel_unneeded]))
    info['last_name'] = request.form['last_name']
    info['first_name'] = request.form['first_name']
    info['patronymic'] = request.form['patronymic']
    return info


# Загрузка информации пользователя из БД
def get_user_info(user):
    user = int(user)
    user_info = dict()
    user_db = db.session.query(Users).filter(Users.user_id == user).first()
    user_info['user_id'] = user
    user_info['email'] = user_db.email
    user_info['tel'] = user_db.tel
    user_info['last_name'] = user_db.last_name
    user_info['first_name'] = user_db.first_name
    user_info['patronymic'] = user_db.patronymic
    user_info['type'] = user_db.user_type
    user_info['approved'] = user_db.approved
    user_info['created_on'] = user_db.created_on.strftime('%d.%m.%Y %H:%M:%S')
    year_cats = [c.cat_id for c in Categories.query.filter(Categories.year == curr_year).all()]
    if user_db.last_login:
        user_info['last_login'] = user_db.last_login.strftime('%d.%m.%Y %H:%M:%S')
    if user in [u.secretary_id for u in CatSecretaries.query.all()]:
        user_info['secretary'] = True
        user_info['cat_id'] = [c.cat_id for c in db.session.query(CatSecretaries).filter(
            CatSecretaries.secretary_id == user).all() if c.cat_id in year_cats]
    else:
        user_info['cat_id'] = []
    if user in [s.user_id for s in SupervisorUser.query.all()]:
        user_info['supervisor_id'] = SupervisorUser.query.filter(SupervisorUser.user_id == user).first().supervisor_id
    return user_info


def get_org_info(user_id):
    org = get_user_info(user_id)
    resps = [r.responsibility_id for r
             in ResponsibilityAssignment.query.filter(ResponsibilityAssignment.user_id == org['user_id']).all()]
    responsibilities = []
    for resp in resps:
        resp_db = db.session.query(Responsibilities).filter(Responsibilities.responsibility_id == resp).first()
        responsibility = {'id': resp_db.responsibility_id, 'name': resp_db.name, 'description': resp_db.description}
        responsibilities.append(responsibility)
    responsibs = sorted(responsibilities, key=lambda u: u['name'])
    org['responsibilities'] = responsibs
    return org


def all_users():
    users = dict()
    for u in Users.query.order_by(Users.user_id.desc()).all():
        users[u.user_id] = get_user_info(u.user_id)
    return users


# Загрузка информации профиля из БД
def get_profile_info(user):
    profile = dict()
    if db.session.query(Profile).filter(Profile.user_id == user).first():
        prof_info = db.session.query(Profile).filter(Profile.user_id == user).first()
        profile['vk'] = prof_info.vk
        profile['tg'] = prof_info.telegram
        profile['username'] = prof_info.vernadsky_username
        profile['filled'] = True
        profile['occupation'] = prof_info.occupation
        profile['involved'] = prof_info.involved
        profile['place_of_work'] = prof_info.place_of_work
        profile['grade'] = prof_info.grade
        profile['year'] = prof_info.year
        profile['born'] = prof_info.born
    else:
        profile = {'filled': False, 'vk': None, 'tg': None, 'username': None, 'occupation': None, 'involved': None,
                   'place_of_work': None, 'grade': None, 'year': None, 'born': None}
    return profile


# Запись исправленной информации пользователя в БД
def write_user(user_info):
    if 'user_id' in session.keys():
        # Загрузка информации пользователя из БД
        user_db = db.session.query(Users).filter(Users.user_id == session['user_id']).first()
        # Проверка существования другого пользователя с новым введенным email
        same_email = [user.user_id for user in db.session.query(Users).filter(Users.email == user_info['email']).all()]
        if not same_email:
            user_db.email = user_info['email']
        elif session['user_id'] in same_email:
            if same_email.remove(session['user_id']) is None:
                user_db.email = user_info['email']
        else:
            return 'email'
        # Проверка существования другого пользователя с новым введенным телефоном
        same_tel = [user.user_id for user in db.session.query(Users).filter(Users.email == user_info['tel']).all()]
        if not same_tel:
            user_db.tel = user_info['tel']
        elif session['user_id'] in same_tel:
            if same_tel.remove(session['user_id']) is None:
                user_db.tel = user_info['tel']
            else:
                return 'tel'

        db.session.query(Users).filter(Users.user_id == session['user_id']).update(
            {Users.last_name: user_info['last_name'], Users.first_name: user_info['first_name'],
             Users.patronymic: user_info['patronymic']})
    else:
        user = Users(user_info['email'], user_info['tel'], user_info['password'], user_info['last_name'],
                     user_info['first_name'], user_info['patronymic'], user_info['user_type'],
                     user_info['approved'], None)
        db.session.add(user)
    db.session.commit()
    return 'ok'


def write_category(cat_info):
    if cat_info['cat_id'] is None:
        cat_info['cat_id'] = max([c.cat_id for c in Categories.query.all()]) + 1
    if cat_info['cat_id'] in [cat.cat_id for cat in Categories.query.all()]:
        db.session.query(Categories).filter(Categories.cat_id == cat_info['cat_id']).update(
            {Categories.year: curr_year, Categories.cat_name: cat_info['cat_name'],
             Categories.short_name: cat_info['short_name'], Categories.tg_channel: cat_info['tg_channel'],
             Categories.cat_site_id: cat_info['cat_site_id'], Categories.drive_link: cat_info['drive_link']})
        if cat_info['cat_id'] in [cat_dir.cat_id for cat_dir in CatDirs.query.all()]:
            db.session.query(CatDirs).filter(CatDirs.cat_id == cat_info['cat_id']).update(
                {CatDirs.cat_id: cat_info['cat_id'], CatDirs.dir_id: cat_info['direction'],
                 CatDirs.contest_id: cat_info['contest']})
        else:
            cat_dir = CatDirs(cat_info['cat_id'], cat_info['direction'], cat_info['contest'])
            db.session.add(cat_dir)
        if cat_info['supervisor'] is not None and cat_info['supervisor'] != '':
            if cat_info['cat_id'] in [sup.cat_id for sup in CatSupervisors.query.all()]:
                db.session.query(CatSupervisors).filter(CatSupervisors.cat_id == cat_info['cat_id']).update(
                    {CatSupervisors.supervisor_id: cat_info['supervisor']})
            else:
                sup = db.session.query(Supervisors).filter(Supervisors.supervisor_id == cat_info['supervisor']).first()
                db_cat = db.session.query(Categories).filter(Categories.cat_id == cat_info['cat_id']).first()
                cat = CatSupervisors(db_cat.cat_id, sup.supervisor_id)
                db.session.add(cat)
    else:
        cat = Categories(curr_year, cat_info['cat_name'], cat_info['short_name'], cat_info['tg_channel'],
                         cat_info['cat_site_id'], cat_info['drive_link'])
        db.session.add(cat)
        db.session.commit()
        categ = db.session.query(Categories).filter(Categories.cat_name == cat_info['cat_name']
                                                    ).filter(Categories.year == curr_year).first()
        if type(cat_info['direction']) is int:
            direct = db.session.query(Directions).filter(Directions.direction_id == cat_info['direction']).first()
        else:
            direct = db.session.query(Directions).filter(Directions.dir_name == cat_info['direction']).first()
        if type(cat_info['contest']) is int:
            cont = db.session.query(Contests).filter(Contests.contest_id == cat_info['contest']).first()
        else:
            cont = db.session.query(Contests).filter(Contests.contest_name == cat_info['contest']).first()
        if cat_info['cat_id'] not in [catdir.cat_id for catdir in CatDirs.query.all()]:
            cat_dir = CatDirs(categ.cat_id, direct.direction_id, cont.contest_id)
            db.session.add(cat_dir)
        cat_info['cat_id'] = db.session.query(Categories).filter(
            Categories.cat_name == cat_info['cat_name']).first().cat_id
    if cat_info['cat_id'] in [cat_sup.cat_id for cat_sup in CatSupervisors.query.all()]:
        cat = db.session.query(CatSupervisors).filter(CatSupervisors.cat_id == cat_info['cat_id']).first()
        sup = db.session.query(Supervisors).filter(Supervisors.supervisor_id == cat_info['supervisor']).first()
        if sup is not None:
            cat.supervisor_id = sup.supervisor_id
    else:
        if type(cat_info['supervisor']) is int:
            sup = db.session.query(Supervisors).filter(Supervisors.supervisor_id == cat_info['supervisor']).first()
        else:
            if cat_info['supervisor'] is not None:
                sup_name = cat_info['supervisor'].split(' ')
                sup = db.session.query(Supervisors).filter(Supervisors.last_name == sup_name[0]
                                                           ).filter(Supervisors.first_name == sup_name[1]
                                                                    ).filter(Supervisors.patronymic == sup_name[2]
                                                                             ).first()
                db_cat = db.session.query(Categories).filter(Categories.cat_id == cat_info['cat_id']).first()
            else:
                sup = None
        if sup is not None:
            cat = CatSupervisors(db_cat.cat_id, sup.supervisor_id)
            db.session.add(cat)
    db.session.commit()
    return True


def one_category(categ):
    cat = {}
    cat_id = categ.cat_id
    cat['id'] = categ.cat_id
    cat['year'] = categ.year
    cat['name'] = categ.cat_name
    cat['short_name'] = categ.short_name
    cat['tg_channel'] = categ.tg_channel
    cat_dir = db.session.query(CatDirs).filter(CatDirs.cat_id == cat_id).first()
    direction = db.session.query(Directions).filter(Directions.direction_id == cat_dir.dir_id).first()
    cat['direction'] = direction.dir_name
    cat['dir_id'] = direction.direction_id
    contest = db.session.query(Contests).filter(Contests.contest_id == cat_dir.contest_id).first()
    cat['contest'] = contest.contest_name
    cat['cont_id'] = contest.contest_id
    cat['drive_link'] = categ.drive_link
    cat['cat_site_id'] = categ.cat_site_id
    if cat_id in [c.cat_id for c in CatSupervisors.query.all()]:
        sup = db.session.query(Supervisors).join(CatSupervisors).filter(CatSupervisors.cat_id == cat_id).first()
        cat['supervisor_id'] = sup.supervisor_id
        cat['supervisor'] = sup.last_name + ' ' + sup.first_name + ' ' + sup.patronymic
        cat['supervisor_email'] = sup.email
        cat['supervisor_tel'] = sup.tel
    if cat_id in [c.cat_id for c in CatSecretaries.query.all()]:
        user = db.session.query(Users).join(CatSecretaries).filter(CatSecretaries.cat_id == cat_id).first()
        cat['secretary_id'] = user.user_id
        cat['secretary'] = user.last_name + ' ' + user.first_name
        cat['secretary_full'] = user.last_name + ' ' + user.first_name + ' ' + user.patronymic
        cat['secretary_email'] = user.email
        cat['secretary_tel'] = user.tel
    if cat_id in [cat.cat_id for cat in ReportDates.query.all()]:
        dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
        dates = []
        if dates_db.day_1:
            dates.append(days[dates_db.day_1.strftime('%w')] + ' ' + dates_db.day_1.strftime('%d') + ' ' +
                         months_full[dates_db.day_1.strftime('%m')])
        if dates_db.day_2:
            dates.append(days[dates_db.day_2.strftime('%w')] + ' ' + dates_db.day_2.strftime('%d') + ' ' +
                         months_full[dates_db.day_2.strftime('%m')])
        if dates_db.day_3:
            dates.append(days[dates_db.day_3.strftime('%w')] + ' ' + dates_db.day_3.strftime('%d') + ' ' +
                         months_full[dates_db.day_3.strftime('%m')])
        cat['dates'] = ', '.join(dates)
    return cat


def categories_info(cat_id='all'):
    cats_count = 0
    if cat_id == 'all':
        categories = db.session.query(Categories
                                      ).filter(Categories.year == curr_year
                                               ).join(CatDirs
                                                      ).join(Directions).join(Contests
                                                                              ).order_by(CatDirs.dir_id,
                                                                                         CatDirs.contest_id,
                                                                                         Categories.cat_name).all()
        cats = []
        for cat in categories:
            if cat.year == curr_year:
                cats_count += 1
                cats.append(one_category(cat))
    else:
        category = db.session.query(Categories).filter(Categories.cat_id == cat_id).first()
        cats = one_category(category)
    return cats_count, cats


def get_supervisors():
    supervisors_list = db.session.query(Supervisors).order_by(Supervisors.last_name).all()
    sups = dict()
    for sup in supervisors_list:
        sups[sup.supervisor_id] = dict()
        sups[sup.supervisor_id]['id'] = sup.supervisor_id
        sups[sup.supervisor_id]['name'] = sup.last_name + ' ' + sup.first_name + ' ' + sup.patronymic
        sups[sup.supervisor_id]['email'] = sup.email
        sups[sup.supervisor_id]['tel'] = sup.tel
    return sups


def supervisor_info(sup_id):
    sup = db.session.query(Supervisors).filter(Supervisors.supervisor_id == sup_id).first()
    sup_info = dict()
    sup_info['id'] = sup.supervisor_id
    sup_info['name'] = sup.last_name + ' ' + sup.first_name + ' ' + sup.patronymic
    sup_info['last_name'] = sup.last_name
    sup_info['first_name'] = sup.first_name
    sup_info['patronymic'] = sup.patronymic
    sup_info['email'] = sup.email
    sup_info['tel'] = sup.tel
    categories = db.session.query(CatSupervisors).filter(CatSupervisors.supervisor_id == sup_info['id']).all()
    sup_categories = []
    cats_db = db.session.query(Categories)
    for cat in categories:
        sup_categories.append(cats_db.filter(Categories.cat_id == cat.cat_id).first().cat_name)
    sup_info['categories'] = ', '.join(sup_categories)
    return sup_info


def one_application(application):
    one = dict()
    categories = db.session.query(Categories)
    users = db.session.query(Users)
    user = users.filter(Users.user_id == application.user_id).first()
    one['user_id'] = user.user_id
    one['user'] = user.last_name + ' ' + user.first_name
    one['year'] = application.year
    one['role'] = application.role
    if application.category_1 != 'None':
        cat_1 = categories.filter(Categories.cat_id == application.category_1).first()
        one['category_1_id'] = cat_1.cat_id
        one['category_1'] = cat_1.cat_name
        one['category_1_short'] = cat_1.short_name
    if application.category_2 != 'None':
        cat_2 = categories.filter(Categories.cat_id == application.category_2).first()
        one['category_2_id'] = cat_2.cat_id
        one['category_2'] = cat_2.cat_name
        one['category_2_short'] = cat_2.short_name
    if application.category_3 != 'None':
        cat_3 = categories.filter(Categories.cat_id == application.category_3).first()
        one['category_3_id'] = cat_3.cat_id
        one['category_3'] = cat_3.cat_name
        one['category_3_short'] = cat_3.short_name
    one['any_category'] = application.any_category
    one['taken_part'] = application.taken_part
    one['considered'] = application.considered
    return one


def application_info(info_type, user, year=curr_year):
    if info_type == 'user':
        applications = db.session.query(Application).filter(Application.user_id == user).order_by(
            Application.year.desc())
    elif info_type == 'year':
        applications = db.session.query(Application).join(Users).filter(Application.year == year).order_by(
            Users.last_name)
    elif info_type == 'user-year':
        applications = db.session.query(Application).filter(Application.user_id == user).filter(
            Application.year == year)
    else:
        applications = None
    appl = dict()
    if applications is not None:
        if info_type == 'user-year':
            appl = one_application(applications.first())
        else:
            for application in applications.all():
                if info_type == 'user':
                    key = application.year
                elif info_type == 'year':
                    key = application.user_id
                else:
                    key = application.user_id
                appl[key] = one_application(application)
    else:
        appl[curr_year] = dict()
        appl[curr_year]['role'], appl[curr_year]['category_1'], appl[curr_year]['category_2'], \
        appl[curr_year]['category_3'], appl[curr_year]['any_category'], appl[curr_year]['taken_part'], \
        appl[curr_year]['considered'] = None, None, None, None, None, None, None
    return appl


def one_news(news_id):
    n = db.session.query(News).filter(News.news_id == news_id).first()
    news = dict()
    news['news_id'] = news_id
    news['title'] = n.title
    news['content'] = n.content
    news['access'] = n.access
    news['publish'] = n.publish
    news['date'] = n.date_time.strftime('%d-%m-%Y')
    news['time'] = n.date_time.strftime('%H:%M')
    return news


def all_news():
    news_db = News.query.order_by(News.date_time.desc()).all()
    all_n = dict()
    for news in news_db:
        all_n[news.news_id] = one_news(news.news_id)
    return all_n


def work_info(work_id):
    work_id = int(work_id)
    work_db = db.session.query(Works).filter(Works.work_id == work_id).first()
    work = dict()
    work['work_id'] = work_id
    work['work_name'] = work_db.work_name
    work['timeshift'] = work_db.msk_time_shift
    work['reported'] = work_db.reported
    work['email'] = work_db.email
    work['tel'] = work_db.tel
    work['author_1_name'] = work_db.author_1_name
    work['author_1_age'] = work_db.author_1_age
    work['author_1_class'] = work_db.author_1_class
    work['author_2_name'] = work_db.author_2_name
    work['author_2_age'] = work_db.author_2_age
    work['author_2_class'] = work_db.author_2_class
    work['author_3_name'] = work_db.author_3_name
    work['author_3_age'] = work_db.author_3_age
    work['author_3_class'] = work_db.author_3_class
    work['authors'] = work['author_1_name']
    if work['author_2_name'] is not None:
        work['authors'] += ', ' + work['author_2_name']
    if work['author_3_name'] is not None:
        work['authors'] += ', ' + work['author_3_name']
    if work['timeshift']:
        if work['timeshift'] >= 0:
            work['timeshift'] = '+' + str(work['timeshift'])
        else:
            work['timeshift'] = str(work['timeshift'])
    if work_id in [w.work_id for w in RevAnalysis.query.all()]:
        if len(RevAnalysis.query.filter(RevAnalysis.work_id == work_id).all()
               ) == len(
            RevCriteria.query.filter(RevCriteria.year == datetime.datetime.strptime(str(curr_year), '%Y').date()
                                     ).all()):
            work['analysis'] = True
        else:
            work['analysis'] = 'part'
    elif work_id in [w.work_id for w in PreAnalysis.query.all()]:
        pre = db.session.query(PreAnalysis).filter(PreAnalysis.work_id == work_id).first()
        if pre.has_review is False:
            work['analysis'] = True
        else:
            work['analysis'] = False
    else:
        work['analysis'] = False
    work['cat_id'] = WorkCategories.query.filter(WorkCategories.work_id == work_id).first().cat_id
    work['reg_tour'] = work_db.reg_tour
    if work['work_id'] in [w.work_id for w in Discounts.query.all()]:
        disc = db.session.query(Discounts).filter(Discounts.work_id == work['work_id']).first()
        work['fee'] = disc.payment
        work['format'] = disc.participation_format
    elif work['work_id'] in [w.work_id for w in WorksNoFee.query.all()]:
        work['fee'] = 0
    elif work['reg_tour'] is not None:
        work['fee'] = tour_fee
    elif work['work_id'] in [w.work_id for w in WorksNoFee.query.all()]:
        work['fee'] = 0
    else:
        work['fee'] = fee
    if work['work_id'] in [w.work_id for w in AppliedForOnline.query.all()]:
        work['format'] = 'online'
    if work_id in [w.work_id for w in ParticipatedWorks.query.all()]:
        work['part_offline'] = True
        work['format'] = 'face-to-face'
    else:
        work['part_offline'] = False
    work['site_id'] = work_db.work_site_id
    if work_id in [w.work_id for w in Applications2Tour.query.all()]:
        appl_db = db.session.query(Applications2Tour).filter(Applications2Tour.work_id == work_id).first()
        work['appl_no'] = appl_db.appl_no
        work['arrived'] = appl_db.arrived
    else:
        work['appl_no'] = False
        work['arrived'] = False
    if work_id in [w.work_id for w in ReportOrder.query.all()]:
        report = db.session.query(ReportOrder).filter(ReportOrder.work_id == work_id).first()
        work['report_day'] = report.report_day
        work['report_order'] = report.order
    if work['work_id'] in [p.participant for p in PaymentRegistration.query.all()]:
        work['payed'] = True
        work['payment_id'] = PaymentRegistration.query.filter(PaymentRegistration.participant ==
                                                              work['work_id']).first().payment_id
    elif work['fee'] == 0:
        work['payed'] = True
        work['payment_id'] = 'Работа участвует без оргвзноса'
    else:
        work['payed'] = False
    return work


def get_works(cat_id, status, mode='all'):
    works = dict()
    works_cat = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat_id).all()]
    works_stat = [w.work_id for w in WorkStatuses.query.filter(WorkStatuses.status_id >= status).all() if w.work_id
                  in works_cat]
    if mode == 'online':
        works_searched = [w.work_id for w in AppliedForOnline.query.all() if w.work_id in works_stat]
    else:
        works_searched = works_stat
    for w in works_searched:
        works[w] = work_info(w)
    return works


def get_works_no_fee(cat_id):
    works_no_fee = {}
    cat_works = db.session.query(WorkCategories).filter(WorkCategories.cat_id == cat_id
                                                        ).order_by(WorkCategories.work_id).all()
    for work in cat_works:
        if work.work_id in [w.work_id for w in WorksNoFee.query.all()]:
            work_db = db.session.query(Works).filter(Works.work_id == work.work_id).first()
            w_no = work_db.work_id
            works_no_fee[w_no] = work_info(w_no)
    return works_no_fee


def get_criteria(year):
    criteria = dict()
    y = datetime.datetime.strptime(str(year), '%Y').date()
    crit_db = db.session.query(RevCriteria).filter(RevCriteria.year == y).all()
    crit_val_db = db.session.query(CriteriaValues)
    values_db = db.session.query(RevCritValues)
    for crit in crit_db:
        crit_info = dict()
        crit_id = crit.criterion_id
        crit_info['id'] = crit_id
        crit_info['name'] = crit.criterion_name
        crit_info['description'] = crit.criterion_description
        crit_info['year'] = datetime.datetime.strftime(crit.year, '%Y')
        crit_info['weight'] = crit.weight
        crit_values = crit_val_db.filter(CriteriaValues.criterion_id == crit_id).all()
        values = dict()
        for val in crit_values:
            v = dict()
            val_id = val.value_id
            value = values_db.filter(RevCritValues.value_id == val_id).first()
            v['value_id'] = val_id
            v['val_name'] = value.value_name
            v['comment'] = value.comment
            v['val_weight'] = value.weight
            values[val_id] = v
            if v['comment'] is not None and v['comment'] != '':
                crit_info['val_comment'] = True
            else:
                crit_info['val_comment'] = False
        crit_info['values'] = values
        crit_info['val_num'] = len(values)
        criteria[crit_id] = crit_info
    return criteria


def reg_works(cat_id='all', status=1):
    wks = []
    if status == 1:
        stat = ['Допущена до 1-го тура', 'Направлена на рецензирование', 'Отрецензирована',
                'Окончила 1-й тур. Не допущена до 2-го тура', 'Допущена до 2-го тура']
    elif status == 2:
        stat = ['Допущена до 2-го тура']
    if cat_id == 'all':
        categories = db.session.query(Categories
                                      ).filter(Categories.year == curr_year
                                               ).join(CatDirs
                                                      ).join(Directions
                                                             ).join(Contests
                                                                    ).order_by(CatDirs.dir_id, CatDirs.contest_id,
                                                                               Categories.cat_name).all()
        for cat in categories:
            cat_id = cat.cat_id
            works = {}
            cat_works = db.session.query(WorkCategories).filter(WorkCategories.cat_id == cat_id
                                                                ).order_by(WorkCategories.work_id).all()
            for work in cat_works:
                work_db = db.session.query(Works).filter(Works.work_id == work.work_id).first()
                w_no = work_db.work_id
                status_id = WorkStatuses.query.filter(WorkStatuses.work_id == w_no).first().status_id
                if ParticipationStatuses.query.filter(ParticipationStatuses.status_id == status_id).first().status_name \
                        in stat:
                    works[w_no] = work_info(w_no)
                    if works[w_no]['reg_tour'] is not None:
                        works[w_no]['pre_ana'] = get_pre_analysis(w_no)
                        works[w_no]['rk'], works[w_no]['ana_res'] = get_analysis(w_no)
                        wks.append(works[w_no])
    else:
        works = {}
        cat_works = db.session.query(WorkCategories).filter(WorkCategories.cat_id == int(cat_id)
                                                            ).order_by(WorkCategories.work_id).all()
        for work in cat_works:
            work_db = db.session.query(Works).filter(Works.work_id == work.work_id).first()
            w_no = work_db.work_id
            status_id = WorkStatuses.query.filter(WorkStatuses.work_id == w_no).first().status_id
            if ParticipationStatuses.query.filter(ParticipationStatuses.status_id == status_id).first().status_name \
                    in stat:
                works[w_no] = work_info(w_no)
                if works[w_no]['reg_tour'] is not None:
                    works[w_no]['pre_ana'] = get_pre_analysis(w_no)
                    works[w_no]['rk'], works[w_no]['ana_res'] = get_analysis(w_no)
                    wks.append(works[w_no])
    return wks


def get_pre_analysis(work_id):
    pre = dict()
    pre_ana = db.session.query(PreAnalysis).filter(PreAnalysis.work_id == int(work_id)).first()
    if pre_ana is not None:
        pre['good_work'] = pre_ana.good_work
        pre['research'] = pre_ana.research
        pre['has_review'] = pre_ana.has_review
        pre['rev_type'] = pre_ana.rev_type
        pre['pushed'] = pre_ana.pushed
        pre['work_comment'] = pre_ana.work_comment
        pre['rev_comment'] = pre_ana.rev_comment
    else:
        pre = None
    if pre == {}:
        pre = None
    return pre


def get_analysis(work_id, internal=None):
    rk = 0
    analysis = dict()
    if not internal:
        analysis_db = db.session.query(RevAnalysis).filter(RevAnalysis.work_id == work_id).all()
    else:
        analysis_db = db.session.query(InternalAnalysis).filter(InternalAnalysis.review_id == work_id).all()
    values_db = db.session.query(RevCritValues)
    criteria = db.session.query(RevCriteria)
    if analysis_db is not None:
        for criterion in analysis_db:
            crit = dict()
            crit['val_id'] = criterion.value_id
            crit['val_name'] = values_db.filter(RevCritValues.value_id == crit['val_id']).first().value_name
            analysis[criterion.criterion_id] = crit
            val_rk = values_db.filter(RevCritValues.value_id == crit['val_id']).first().weight
            cr_rk = criteria.filter(RevCriteria.criterion_id == criterion.criterion_id).first().weight
            c_v_rk = val_rk * cr_rk
            rk += c_v_rk
    else:
        analysis = None
    if analysis == {}:
        analysis = None
    return rk, analysis


def analysis_results():
    analysis_res = dict()
    criteria = db.session.query(RevCriteria).all()
    rev_ana = db.session.query(RevAnalysis)
    cats = db.session.query(Categories).all()
    for cat in cats:
        cat_works = get_works(cat.cat_id, 2)
        analysis_res.update(cat_works)
    for work in analysis_res.keys():
        if work in [w.work_id for w in RevAnalysis.query.all()]:
            for criterion in criteria:
                if criterion.criterion_id in \
                        [w.criterion_id for w in RevAnalysis.query.filter(RevAnalysis.work_id == work).all()]:
                    val = rev_ana.filter(RevAnalysis.work_id == work)
                    value = val.filter(RevAnalysis.criterion_id == criterion.criterion_id).first().value_id
                    analysis_res[work].update({criterion.criterion_id: value})
    crit_vals = get_criteria(curr_year)
    for work in analysis_res.keys():
        rk = 0
        if 'analysis' in analysis_res[work].keys() and analysis_res[work]['analysis'] is True:
            for key in analysis_res[work].keys():
                if key in crit_vals.keys():
                    rk += crit_vals[key]['weight'] * crit_vals[key]['values'][analysis_res[work][key]]['val_weight']
            analysis_res[work]['ana_rk'] = rk
    return analysis_res


def analysis_nums():
    c, cats = categories_info()
    ana_nums = []
    for cat in cats:
        cat_reg = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat['id'])
                   if Works.query.filter(Works.work_id == w.work_id).first().reg_tour is not None]
        works_passed = [w.work_id for w in WorkStatuses.query.all() if w.status_id >= 2]
        to_analyse = [w for w in cat_reg if w in works_passed]
        analysed = set(w.work_id for w in RevAnalysis.query.all() if w.work_id in to_analyse)
        analysed.update(w.work_id for w in PreAnalysis.query.filter(PreAnalysis.has_review == 0).all()
                        if w.work_id in to_analyse)
        cat_ana = {'cat_id': cat['id'], 'cat_name': cat['name'], 'analysed': len(analysed),
                   'regional_applied': len(to_analyse)}
        cat_ana['left'] = cat_ana['regional_applied'] - cat_ana['analysed']
        ana_nums.append(cat_ana)
    all_stats = {'regionals': sum([cat['regional_applied'] for cat in ana_nums]),
                 'analysed': sum([cat['analysed'] for cat in ana_nums]),
                 'regions': len(set(w.reg_tour for w in Works.query.all()))}
    all_stats['left'] = all_stats['regionals'] - all_stats['analysed']
    return ana_nums, all_stats


def check_analysis(cat_id):
    cat_works = [w.work_id for w in Works.query.select_from(WorkCategories
                                                            ).join(Works, Works.work_id == WorkCategories.work_id
                                                                   ).filter(WorkCategories.cat_id == cat_id).all()
                 if w.reg_tour is not None]
    for work in cat_works:
        if work not in [w.work_id for w in PreAnalysis.query.all()]:
            return True
        else:
            if PreAnalysis.query.filter(PreAnalysis.work_id == work).first().has_review is True:
                if len(RevAnalysis.query.filter(RevAnalysis.work_id == work).all()
                       ) != len(
                    RevCriteria.query.filter(RevCriteria.year == datetime.datetime.strptime(str(curr_year), '%Y').date()
                                             ).all()):
                    return True
    return False


def no_fee_nums():
    cats_no, cats = categories_info()
    total = 0
    for cat in cats:
        works = get_works_no_fee(cat['id'])
        cat['works'] = ', '.join([str(w) for w in works.keys()])
        cat['works_no'] = len(works)
        total += cat['works_no']
    return total, cats


def application_2_tour(appl):
    application = {'id': appl, 'works': [work_info(w.work_id) for w
                                         in Applications2Tour.query.filter(Applications2Tour.appl_no == appl).all()],
                   'participants': []}
    for part in ParticipantsApplied.query.filter(ParticipantsApplied.appl_id == appl).all():
        part_db = db.session.query(ParticipantsApplied).filter(ParticipantsApplied.participant_id == part.participant_id
                                                               ).first()
        participant = {'id': part_db.participant_id, 'last_name': part_db.last_name, 'first_name': part_db.first_name,
                       'patronymic_name': part_db.patronymic_name, 'class': part_db.participant_class,
                       'role': part_db.role}
        p_name = (participant['last_name'] + ' ' + participant['first_name'] + ' ' + participant[
            'patronymic_name']).strip()
        if participant['id'] in [p.participant_id for p in Discounts.query.all()]:
            disc = db.session.query(Discounts).filter(Discounts.participant_id == participant['id']).first()
            participant['fee'] = disc.payment
            participant['format'] = disc.participation_format
        else:
            participant['fee'] = fee
            participant['format'] = 'face-to-face'
        if participant['id'] in [p.participant for p in PaymentRegistration.query.all()]:
            participant['payed'] = True
            participant['payment_id'] = PaymentRegistration.query.filter(PaymentRegistration.participant ==
                                                                         participant['id']).first().payment_id
        else:
            participant['payed'] = False
        application['participants'].append(participant)
    return application


def payment_info(payment_id):
    payment = db.session.query(BankStatement).filter(BankStatement.payment_id == int(payment_id)).first()
    date = datetime.datetime.strftime(payment.date, '%d.%m.%Y')
    remainder = payment.debit
    if int(payment_id) in [p.payment_id for p in PaymentRegistration.query.filter(PaymentRegistration.for_work == 0
                                                                                  ).all()]:
        for participant in PaymentRegistration.query.filter(PaymentRegistration.payment_id == int(payment_id)).all():
            if participant.participant in [p.participant_id for p in ParticipantsApplied.query.all()]:
                participants = application_2_tour(ParticipantsApplied.query.filter(ParticipantsApplied.participant_id ==
                                                                                   participant.participant
                                                                                   ).first().appl_id)['participants']
                for part in participants:
                    if part['id'] == participant.participant:
                        remainder -= float(part['fee'])
            else:
                PaymentRegistration.query.filter(PaymentRegistration.participant == participant.participant).delete()
                db.session.commit()
    if remainder % 1 == 0:
        remainder = str(int(remainder)) + ' р.'
    else:
        remainder = str(remainder).replace('.', ',') + ' р.'
    if payment.debit % 1 == 0:
        debit = str(int(payment.debit)) + ' р.'
    else:
        debit = str(payment.debit).replace('.', ',') + ' р.'
    pay = {'payment_id': payment.payment_id, 'date': date, 'order_id': payment.order_id,
           'debit': debit, 'organisation': payment.organisation, 'tin': payment.tin, 'bic': payment.bic,
           'bank_name': payment.bank_name, 'account': payment.account, 'comment': payment.payment_comment,
           'remainder': remainder}
    return pay


def statement_info():
    statement = []
    stat_db = db.session.query(BankStatement).order_by(
        BankStatement.date.desc()).order_by(BankStatement.order_id.asc()).all()
    payment_reg = db.session.query(PaymentRegistration)
    for payment in stat_db:
        remainder = payment.debit
        if payment.payment_id in [p.payment_id for p in payment_reg.all()]:
            for participant in [p.participant for p
                                in payment_reg.filter(PaymentRegistration.payment_id == payment.payment_id).all()]:
                if participant in [p.participant_id for p in Discounts.query.all()]:
                    disc = db.session.query(Discounts).filter(Discounts.participant_id == participant).first()
                    payed = disc.payment
                else:
                    payed = fee
                remainder -= payed
        remainder = str(int(remainder))
        date = datetime.datetime.strftime(payment.date, '%d.%m.%Y')
        if payment.debit % 1 == 0:
            debit = str(int(payment.debit))
        else:
            debit = str(payment.debit).replace('.', ',')
        pay = {'payment_id': payment.payment_id, 'date': date, 'order_id': payment.order_id,
               'debit': debit, 'organisation': payment.organisation, 'tin': payment.tin, 'bic': payment.bic,
               'bank_name': payment.bank_name, 'account': payment.account, 'comment': payment.payment_comment,
               'remainder': remainder}
        statement.append(pay)
    return statement


def document_set():
    document = Document()

    style = document.styles['Header']
    style.font.name = 'Calibri Light'
    style.font.size = Pt(16)
    style.font.bold = True

    style = document.styles['Heading 1']
    style.font.name = 'Calibri Light'
    style.font.size = Pt(16)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_before = Pt(12)
    style.paragraph_format.space_after = Pt(12)
    style.paragraph_format.left_indent = Pt(0)

    style = document.styles['Normal']
    style.font.name = 'Calibri Light'
    style.font.size = Pt(14)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_before = Pt(6)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.left_indent = Pt(30)

    # style = document.styles['Normal']
    # style.font.name = 'Calibri Light'
    # style.font.size = Pt(14)
    # style.font.color.rgb = RGBColor(0, 0, 0)
    # style.paragraph_format.left_indent = Pt(36)

    return document


def write_work_date(cat_id, work_id, day):
    work_id = int(work_id)
    if int(cat_id) in [c.cat_id for c in ReportOrder.query.filter(ReportOrder.report_day == day).all()]:
        last_order = max([w.order for w in ReportOrder.query.filter(ReportOrder.cat_id == int(cat_id)
                                                                    ).filter(ReportOrder.report_day == day).all()]) + 1
    else:
        last_order = 1
    if work_id in [w.work_id for w in ReportOrder.query.all()]:
        db.session.query(ReportOrder).filter(ReportOrder.work_id == work_id
                                             ).update({ReportOrder.report_day: day,
                                                       ReportOrder.order: last_order,
                                                       ReportOrder.cat_id: cat_id})
        db.session.commit()
    else:
        o = ReportOrder(work_id, day, last_order, int(cat_id))
        db.session.add(o)
        db.session.commit()
    return 'done'


def get_responsibility(responsibility_id):
    responsibility_id = int(responsibility_id)
    resp_db = db.session.query(Responsibilities).filter(Responsibilities.responsibility_id == responsibility_id).first()
    assignees = [get_org_info(u.user_id) for u
                 in ResponsibilityAssignment.query
                 .filter(ResponsibilityAssignment.responsibility_id == responsibility_id).all()]
    assignees_ids = [u['user_id'] for u in assignees]
    responsibility = {'id': resp_db.responsibility_id, 'name': resp_db.name, 'description': resp_db.description,
                      'assignees': assignees, 'assignees_ids': assignees_ids}
    return responsibility


# САЙТ
# Главная страница
@app.route('/')
def main_page():
    renew_session()
    news = all_news()
    access = check_access('/')
    access_list = [i for i in access_types.keys() if access_types[i] <= access]
    return render_template('main.html', news=news, access_list=access_list)


@app.route('/no_access', defaults={'message': None})
@app.route('/no_access/<message>')
def no_access(message):
    return render_template('no_access.html', message=message)


@app.route('/secretary_reminder')
def secretary_reminder():
    if check_access(url='/secretary_reminder') < 5:
        return redirect(url_for('.no_access'))
    renew_session()
    return render_template('info_pages/secretaries_info/secretary_reminder.html')


@app.route('/secretary_job')
def secretary_job():
    return render_template('info_pages/secretaries_info/secretary_job.html')


# Страница авторизации
@app.route('/login', defaults={'wrong': None})
@app.route('/login/<wrong>')
def login(wrong):
    renew_session()
    return render_template('registration, logging and applications/login.html', wrong=wrong)


# Страница регистрации на сайте
@app.route('/register', defaults={'message': None})
@app.route('/register/<message>')
def register(message):
    return render_template('registration, logging and applications/registration_form.html', message=message)


# Обработка данных формы регистрации на сайте
@app.route('/registration_res', methods=['POST'])
def registration_res():
    # Извлечение данных формы
    user = personal_info_form()
    # Проверка существования email и номера телефона в уже зарегистрированных пользователях.
    # При наличии пользователя с такими данными выводится ошибка через переменную exists.
    if user['email'] in [user.email for user in Users.query.all()]:
        return redirect(url_for('.register', message='email'))
    elif user['tel'] in [user.tel for user in Users.query.all()]:
        return redirect(url_for('.register', message='tel'))
    # Извлечение из формы и шифрование пароля
    user['password'] = encrypt(request.form['password'])
    user['user_type'] = 'user'
    user['approved'] = False
    # Запись полученных данных пользователя в БД, таблица users
    write_user(user)
    # Отправка письма для подтверждения регистрации
    send_email(user['email'])
    # Запись сессии пользователя
    session['user_id'] = db.session.query(Users).filter(Users.email == user['email']).first().user_id
    # Вывод страницы с информацией профиля
    return redirect(url_for('.profile_info', message='first_time'))


# Обработка данных формы авторизации
@app.route('/logging')
def logging():
    # Извлечение данных формы
    user_got = request.values.get('user', str)
    pwd = request.values.get('password', str)
    password = pwd
    user = find_user(user_got)
    if user is None:
        return render_template('registration, logging and applications/login.html', wrong='user')
    # Проверка соответствия пароля записи в БД. Если совпал, записываем сессию пользователя
    else:
        if decrypt(user.password) == password:
            app.permanent_session_lifetime = datetime.timedelta(hours=1)
            session.permanent = True
            session['user_id'] = user.user_id
        else:
            # Если пароль не совпал, выводим страницу авторизации с описанием ошибки
            return redirect(url_for('.login', wrong='password'))
        user = db.session.query(Users).filter(Users.user_id == session['user_id']).first()
        user.last_login = datetime.datetime.now()
        db.session.commit()
        renew_session()
        if 'url' in session.keys():
            return redirect(session['url'])
        else:
            return redirect(url_for('.main_page'))


# Выход из учетной записи
@app.route('/logout')
def logout():
    # Удаление сессии пользователя
    session.pop('user_id', None)
    session.pop('type', None)
    session.pop('profile', None)
    session.pop('secretary', None)
    session.pop('supervisor', None)
    session.pop('cat_id', None)
    session.pop('approved', None)
    session.pop('application', None)
    session.pop('url', None)
    # Перенаправление на главную страницу
    return redirect(url_for('main_page'))


# @app.route('/reset_password')
# def reset_password():
#     return render_template('user_reminder.html')
#
#
# @app.route('/reset_pwd', methods=['GET'])
# def reset_pwd():
#     user_got = request.values.get('user', str)
#     user = find_user(user_got)
#     if user is None:
#         return render_template('user_reminder.html', wrong='user')
#     else:
#         link = '/new_password/' + str(user.user_id) + '/' + user.password
#         msg = Message(subject='Сброс пароля',
#                       body='Для сброса пароля перейдите по ссылке: ' + link + '\nЕсли вы не собирались сбрасывать '
#                                                                               'пароль, игрорируйте это письмо.',
#                       sender=('Конкурс им. В. И. Вернадского', 'info@vernadsky.info'),
#                       recipients=[user.email])
#         mail.send(msg)
#     return redirect()
#
#
# @app.route('/new_password/<user_id>/<password>')
# def new_password(user_id, password):
#     user = db.session.query(Users).filter(Users.user_id == user_id).first()
#     if user.password == password:
#         return render_template()


# Страница подтверждения регистрации (из email)
@app.route('/approve/<user_id>', defaults={'page': 'main'})
@app.route('/approve/<user_id>/<page>')
def approve(user_id, page):
    # Изменение статуса пользователя на "подтвержден"
    user = db.session.query(Users).filter(Users.user_id == int(user_id)).first()
    user.approved = True
    db.session.commit()
    if page == 'adm':
        return redirect(url_for('.user_page', user=user_id))
    else:
        renew_session()
        # Перенаправление на главную страницу
        return redirect(url_for('.main_page'))


# Страница с информацией профиля
@app.route('/profile_info', defaults={'message': None})
@app.route('/profile_info/<message>')
def profile_info(message):
    renew_session()
    access = check_access(url='/profile_info')
    if access < 1:
        return redirect(url_for('.no_access'))
    user = get_user_info(session['user_id'])
    profile = get_profile_info(session['user_id'])
    if profile['born'] is not None:
        profile['born'] = profile['born'].strftime('%d.%m.%Y')
    return render_template('registration, logging and applications/profile_info.html', profile=profile, user=user,
                           access=access, message=message)


# Форма изменения информации пользователя (email, телефон, ФИО, дата рождения)
@app.route('/edit_user', defaults={'message': None})
@app.route('/edit_user/<message>')
def edit_user(message):
    if check_access(url='/edit_user') < 2:
        return redirect(url_for('.no_access'))
    # Получение информации текущего пользователя из БД
    user = get_user_info(session['user_id'])
    renew_session()
    # Вывод формы изменения информации пользователя с предзаполненными из БД полями
    return render_template('registration, logging and applications/edit_user.html', user=user, message=message)


# Обработка информации из формы изменения информации пользователя
@app.route('/edited_user', methods=['POST'])
def edited_user():
    # Получение новых данных пользователя из формы и запись их в БД
    user_info = personal_info_form()
    message = write_user(user_info)
    if message == 'email' or message == 'tel':
        return redirect(url_for('.edit_user', message=message))
    return redirect(url_for('.profile_info'))


# Форма редактирования информации профиля
@app.route('/edit_profile')
def edit_profile():
    if check_access(url='/edit_profile') < 2:
        return redirect(url_for('.no_access'))
    # Извлечение информации профиля из БД (если она заполнен)
    profile = get_profile_info(session['user_id'])
    if profile['born'] is not None:
        profile['born'] = profile['born'].strftime('%Y-%m-%d')
    renew_session()
    # Вывод страницы профиля с информацией пользователя и профиля из БД
    return render_template('registration, logging and applications/edit_profile.html', profile=profile)


# Обработка данных формы редактирования профиля
@app.route('/write_profile', methods=['POST'])
def write_profile():
    if 'occupation' in request.form:
        occupation = request.form['occupation']
    else:
        occupation = None
    if 'place_of_w' in request.form:
        place_of_w = request.form['place_of_w']
        if place_of_w == 'None':
            place_of_w = None
    else:
        place_of_w = None
    if 'place_of_work' in request.form:
        place_of_work = request.form['place_of_work']
    else:
        place_of_work = place_of_w
    if 'involved' in request.form:
        inv = request.form['involved']
    else:
        inv = None
    if 'school' in request.form:
        involved = request.form['school']
        if involved == 'None':
            involved = None
    else:
        involved = inv
    if 'grade' in request.form:
        grade = request.form['grade']
    else:
        grade = None
    if 'year' in request.form:
        year = request.form['year']
    else:
        year = None
    vk = re.sub(r'^vk.com/|^https://vk.com/', '', request.form['vk'])
    if 'telegram' in request.form:
        tg = re.sub(r'https://t.me/|@', '', request.form['telegram'])
    else:
        tg = None
    if 'vernadsky_username' in request.form:
        username = request.form['vernadsky_username']
    else:
        username = None
    if 'born' in request.form.keys():
        born = datetime.datetime.strptime(request.form['born'], '%Y-%m-%d').date()

    if session['user_id'] not in [prof.user_id for prof in Profile.query.all()]:
        prof = Profile(session['user_id'], occupation, place_of_work, involved, grade, year, vk, tg, username, born)
        db.session.add(prof)
        db.session.commit()
        return redirect(url_for('.team_application'))
    else:
        db.session.query(Profile).filter(Profile.user_id == session['user_id']).update(
            {Profile.occupation: occupation, Profile.place_of_work: place_of_work, Profile.involved: involved,
             Profile.grade: grade, Profile.year: year, Profile.vk: vk, Profile.telegram: tg,
             Profile.vernadsky_username: username, Profile.born: born})
        db.session.commit()
        return redirect(url_for('.profile_info'))


@app.route('/change_pwd', defaults={'success': None})
@app.route('/change_pwd/<success>')
def change_pwd(success):
    if check_access(url='/change_pwd') < 2:
        return redirect(url_for('.no_access'))
    renew_session()
    return render_template('registration, logging and applications/change_pwd.html', success=success)


@app.route('/new_pwd', methods=['GET'])
def new_pwd():
    old = request.values.get('old_password', str)
    new = request.values.get('new_password', str)
    confirm = request.values.get('confirm_password', str)
    user = db.session.query(Users).filter(Users.user_id == session['user_id']).first()
    old_check = decrypt(user.password)
    if old == old_check:
        if new == confirm:
            user.password = encrypt(new)
            db.session.commit()
            success = True
        else:
            success = 'unmatched'
    else:
        success = 'wrong_old'
    renew_session()
    return redirect(url_for('.change_pwd', success=success))


@app.route('/change_user_password/<user_id>', defaults={'message': None})
@app.route('/change_user_password/<user_id>/<message>')
def change_user_password(user_id, message):
    if check_access(url='/change_user_password/' + user_id) < 8:
        return redirect(url_for('.no_access'))
    return render_template('user_management/change_user_password.html', user=user_id, message=message)


@app.route('/new_user_password')
def new_user_password():
    if check_access(url='/new_user_password') < 8:
        return redirect(url_for('.no_access'))
    new = request.values.get('new_password', str)
    confirm = request.values.get('confirm_password', str)
    user_id = int(request.values.get('user_id', str))
    user = db.session.query(Users).filter(Users.user_id == user_id).first()
    if new == confirm:
        user.password = encrypt(new)
        db.session.commit()
        message = 'password_changed'
    else:
        return redirect(url_for('.change_user_password', user_id=user_id, message='unmatched'))
    renew_session()
    return redirect(url_for('.user_page', user=user_id, message=message))


@app.route('/admin')
def admin():
    if check_access(url='/admin') < 8:
        return redirect(url_for('.no_access'))
    renew_session()
    return render_template('admin.html')


@app.route('/categories')
def categories_list():
    cats_count, cats = categories_info()
    cats_ids = [categ['id'] for categ in cats]
    with_secretary = 0
    for categ in db.session.query(CatSecretaries).all():
        if categ.cat_id in cats_ids:
            with_secretary += 1
    no_secr = cats_count - with_secretary
    renew_session()
    return render_template('categories/categories.html', cats_count=cats_count, categories=cats, no_secr=no_secr)


@app.route('/edit_category', defaults={'cat_id': None})
@app.route('/edit_category/<cat_id>')
def edit_category(cat_id):
    if cat_id is None:
        cat_id = ''
    if check_access(url='/edit_category/' + cat_id) < 10:
        return redirect(url_for('.no_access'))
    sups = get_supervisors()
    dirs = dict()
    conts = dict()
    directions = db.session.query(Directions).all()
    contests = db.session.query(Contests)
    for direct in directions:
        dir_id = direct.direction_id
        dirs[dir_id] = dict()
        dirs[dir_id]['id'] = direct.direction_id
        dirs[dir_id]['name'] = direct.dir_name
    for cont in contests:
        dir_id = cont.contest_id
        conts[dir_id] = dict()
        conts[dir_id]['id'] = cont.contest_id
        conts[dir_id]['name'] = cont.contest_name
    if cat_id is not None and cat_id != '':
        category = one_category(db.session.query(Categories).filter(Categories.cat_id == cat_id).first())
    else:
        category = None
    renew_session()
    return render_template('categories/add_category.html', supervisors=sups, directions=dirs, contests=conts,
                           category=category)


@app.route('/edited_cat', methods=['POST'])
def edited_category():
    cat_info = dict()
    cat_id = request.form['cat_id']
    if cat_id != '' and cat_id is not None:
        cat_info['cat_id'] = int(cat_id)
    else:
        cat_info['cat_id'] = None
    cat_info['cat_name'] = request.form['category_name']
    cat_info['short_name'] = request.form['short_name']
    supervisor = request.form['supervisor']
    if supervisor != 'Руководитель секции':
        cat_info['supervisor'] = int(supervisor)
    else:
        cat_info['supervisor'] = None
    cat_info['tg_channel'] = re.sub(r'https://t.me/|@', '', request.form['tg_channel'])
    cat_info['direction'] = int(request.form['direction'])
    cat_info['contest'] = int(request.form['contest'])
    cat_site_id = request.form['cat_site_id']
    if cat_site_id != '' and cat_site_id is not None:
        cat_info['cat_site_id'] = int(cat_site_id)
    else:
        cat_info['cat_site_id'] = None
    if 'drive_link' in request.form.keys():
        cat_info['drive_link'] = request.form['drive_link']
    else:
        cat_info['drive_link'] = None
    write_category(cat_info)
    renew_session()
    return redirect(url_for('.categories_list'))


@app.route('/add_categories')
def add_categories():
    if check_access(url='/add_categories') < 10:
        return redirect(url_for('.no_access'))
    renew_session()
    return render_template('categories/add_categories.html')


@app.route('/many_categs', methods=['POST'])
def many_categs():
    text = request.form['text']
    cat_text = text.split('\n')
    for cat in cat_text:
        if cat != '':
            c = cat.split('\t')
            cat_info = dict()
            cat_info['cat_id'] = None
            cat_info['cat_name'] = c[0].strip('\r')
            cat_info['short_name'] = c[1].strip('\r')
            cat_info['supervisor'] = c[2].strip('\r')
            cat_info['tg_channel'] = re.sub(r'https://t.me/|@', '', c[3].strip('\r'))
            direction = c[4].strip('\r')
            if direction == 'вернак' or direction == 'Вернак':
                cat_info['direction'] = 'Конкурс им. В. И. Вернадского'
            elif direction == 'тропа' or direction == 'Тропа':
                cat_info['direction'] = 'Тропой открытий В. И. Вернадского'
            else:
                cat_info['direction'] = direction
            cat_info['contest'] = c[5].strip('\r')
            cat_info['cat_site_id'] = ''
            cat_info['drive_link'] = ''
            write_category(cat_info)
    return redirect(url_for('.categories_list'))


@app.route('/supervisors')
def supervisors():
    sups = get_supervisors()
    c, cats = categories_info()
    relevant = [cat['supervisor_id'] for cat in cats if 'supervisor_id' in cat.keys()]
    relevant.append(21)  # Добавление Свешниковой
    relevant.append(44)  # Добавление Марусяк
    renew_session()
    return render_template('supervisors/supervisors.html', supervisors=sups, access=check_access(url='/supervisors'),
                           relevant=relevant)


@app.route('/download_supervisors')
def download_supervisors():
    sups = get_supervisors()
    c, cats = categories_info()
    relevant = [cat['supervisor_id'] for cat in cats if 'supervisor_id' in cat.keys()]
    relevant.append(21)  # Добавление Свешниковой
    relevant.append(44)  # Добавление Марусяк
    supers = [sup for sup in sups.values() if sup['id'] in relevant]
    df = pd.DataFrame(data=supers)
    if not os.path.isdir('static/files/generated_files'):
        os.mkdir('static/files/generated_files')
    with pd.ExcelWriter('static/files/generated_files/supervisors.xlsx') as writer:
        df.to_excel(writer, sheet_name='Руководители секций')
    return send_file('static/files/generated_files/supervisors.xlsx', as_attachment=True)


@app.route('/edit_supervisor', defaults={'sup_id': ''})
@app.route('/edit_supervisor/<sup_id>')
def edit_supervisor(sup_id):
    if check_access(url=('/edit_supervisor/' + sup_id)) < 10:
        return redirect(url_for('.no_access'))
    if sup_id != '':
        supervisor = supervisor_info(sup_id)
    else:
        supervisor = None
    renew_session()
    return render_template('supervisors/add_supervisor.html', supervisor=supervisor)


@app.route('/adding_supervisor', methods=['POST'])
def edited_supervisor():
    supervisor = personal_info_form()
    supervisor['sup_info'] = request.form['supervisor_info']
    sup_id = request.form['supervisor_id'].strip()
    if sup_id != '' and sup_id is not None and '\r\n' not in sup_id:
        supervisor_id = int(sup_id)
        if supervisor_id in [sup.supervisor_id for sup in Supervisors.query.all()]:
            db.session.query(Supervisors).filter(Supervisors.supervisor_id == supervisor_id).update(
                {Supervisors.last_name: supervisor['last_name'], Supervisors.first_name: supervisor['first_name'],
                 Supervisors.patronymic: supervisor['patronymic'], Supervisors.email: supervisor['email'],
                 Supervisors.tel: supervisor['tel'], Supervisors.supervisor_info: supervisor['sup_info']})
    else:
        supervisor = Supervisors(supervisor['last_name'], supervisor['first_name'], supervisor['patronymic'],
                                 supervisor['email'], supervisor['tel'], supervisor['sup_info'])
        db.session.add(supervisor)
    db.session.commit()
    renew_session()
    return redirect(url_for('.supervisors'))


@app.route('/confirm_sup_deletion/<sup_id>')
def confirm_sup_deletion(sup_id):
    access = check_access(url='/supervisor_profile/' + sup_id)
    if access < 8:
        return redirect(url_for('.no_access'))
    sup_info = supervisor_info(sup_id)
    return render_template('supervisors/confirm_supervisor_deletion.html', supervisor=sup_info)


@app.route('/delete_supervisor/<sup_id>')
def delete_supervisor(sup_id):
    supervisor = db.session.query(Supervisors).filter(Supervisors.supervisor_id == sup_id).first()
    db.session.delete(supervisor)
    db.session.commit()
    renew_session()
    return redirect(url_for('.supervisors'))


@app.route('/add_supervisors')
def add_supervisors():
    if check_access(url='/add_supervisors') < 10:
        return redirect(url_for('.no_access'))
    renew_session()
    return render_template('supervisors/add_supervisors.html')


@app.route('/many_sups', methods=['POST'])
def many_sups():
    text = request.form['text']
    sup_text = text.split('\n')
    for sup in sup_text:
        if sup != '':
            s = sup.split('\t')
            tel = re.sub(r'^8|^7|^(?=9)', '+7', ''.join([n for n in s[4] if n not in tel_unneeded]))
            supervisor = Supervisors(s[0].strip(' '), s[1].strip(' '), s[2].strip(' '), s[3].strip(' '), tel, None)
            db.session.add(supervisor)
    db.session.commit()
    sups = get_supervisors()
    renew_session()
    return redirect(url_for('.supervisors'))


# @app.route('/add_supervisors', methods=['GET'])
# def add_supervisors():
#     if check_access() < 10:
#         return redirect(url_for('.no_access'))
#     file = request.files.get('file', None)
#     # file.save(os.path.join('static/', file.txt))
#     # data = genfromtxt(file, delimiter='\t', encoding='utf-8', dtype=None, names=True).tolist()
#     # for row in data:
#     #     tel = re.sub(r'^8|^7|^(?=9)', '+7', ''.join([n for n in row[4] if n not in tel_unneeded]))
#     #     supervisor = Supervisors(row[0].strip(' '), row[1].strip(' '), row[2].strip(' '), row[3].strip(' '),
#     #                              tel, row[5].strip(' '))
#     #     db.session.add(supervisor)
#     # db.session.commit()
#     sups = get_supervisors()
#     renew_session()
#     return render_template('supervisors.html', supervisors=sups)


@app.route('/supervisor_profile/<supervisor_id>')
def supervisor_profile(supervisor_id):
    access = check_access(url='/supervisor_profile/' + supervisor_id)
    if access < 2:
        return redirect(url_for('.no_access'))
    elif access < 3:
        access = 'partial'
    sup_info = supervisor_info(supervisor_id)
    renew_session()
    return render_template('supervisors/supervisor_profile.html', supervisor=sup_info, access=access)


@app.route('/team_application')
def team_application():
    if check_access(url='/team_application') == 2 and 'profile' not in session.keys():
        return redirect(url_for('.edit_profile'))
    elif check_access(url='/team_application') < 2:
        return redirect(url_for('.no_access', message='register_first'))
    cats_count, categs = categories_info()
    if session['user_id'] in [a.user_id for a in Application.query.filter(Application.year == curr_year).all()]:
        application = application_info('user-year', user=session['user_id'])
        # if application == {curr_year: {'role': None, 'category_1': None, 'category_2': None, 'category_3': None,
        #                                'any_category': None, 'taken_part': None, 'considered': None}}:
        #     application = application[curr_year]
    else:
        application = None
    renew_session()
    return render_template('registration, logging and applications/team_application.html', application=application,
                           categories=categs)


@app.route('/application_process', methods=['POST'])
def application_process():
    role = request.form['role']
    category_1 = request.form['category_1']
    category_2 = request.form['category_2']
    category_3 = request.form['category_3']
    if 'any_category' in request.form:
        any_cat = request.form['any_category']
        any_category = bool(any_cat)
    else:
        any_category = False
    if 'taken_part' in request.form:
        taken_part = request.form['taken_part']
    else:
        taken_part = 'not_filled'
    if session['user_id'] in [user.user_id for user in Application.query.filter(Application.year == curr_year).all()]:
        db.session.query(Application).filter(Application.user_id == session['user_id']).update(
            {Application.role: role, Application.category_1: category_1, Application.category_2: category_2,
             Application.category_3: category_3, Application.any_category: any_category,
             Application.taken_part: taken_part})
    else:
        appl_id = max([appl.appl_id for appl in Application.query.all()]) + 1
        cat_sec = Application(appl_id, session['user_id'], curr_year, role, category_1, category_2, category_3,
                              any_category,
                              taken_part, 'False')
        db.session.add(cat_sec)
    db.session.commit()
    renew_session()
    return redirect(url_for('.application_page'))


@app.route('/my_applications')
def application_page():
    if check_access(url='/my_applications') < 2:
        return redirect(url_for('.no_access'))
    appl_info = application_info('user', user=session['user_id'])
    renew_session()
    return render_template('registration, logging and applications/my_applications.html', application=appl_info)


@app.route('/view_applications')
def view_applications():
    if check_access(url='/view_applications') < 8:
        return redirect(url_for('.no_access'))
    appl = application_info('year', user=session['user_id'])
    users = all_users()
    renew_session()
    return render_template('application management/view_applications.html', applications=appl, year=curr_year,
                           users=users)


@app.route('/one_application/<year>/<user>')
def see_one_application(year, user):
    if check_access(url='/one_application/' + year + '/' + user) < 8:
        return redirect(url_for('.no_access'))
    application = application_info('user-year', user=user, year=year)
    user_info = get_user_info(user)
    profile = get_profile_info(user)
    if profile['born'] is not None:
        profile['born'] = profile['born'].strftime('%d.%m.%Y')
    cats_count, cats = categories_info()
    renew_session()
    return render_template('application management/one_application.html', application=application, year=curr_year,
                           user=user_info,
                           profile=profile, categories=cats)


@app.route('/confirm_application_deletion/<year>/<user>')
def confirm_application_deletion(year, user):
    application = application_info('user-year', user, year)
    user_info = get_user_info(user)
    return render_template('application management/confirm_application_deletion.html', application=application,
                           year=year, user=user_info)


@app.route('/manage_application/<year>/<user>/<action>', defaults={'page': 'all'})
@app.route('/manage_application/<year>/<user>/<action>/<page>')
def manage_application(year, user, action, page):
    if check_access(url='/manage_application/' + year + '/' + user + '/' + action + '/' + page) < 8:
        return redirect(url_for('.no_access'))
    appl_db = db.session.query(Application).filter(Application.user_id == user).filter(Application.year == year).first()
    user_db = db.session.query(Users).filter(Users.user_id == user).first()
    if action == 'accept':
        appl_db.considered = 'True'
        if user_db.user_type == 'user':
            user_db.user_type = 'team'
    elif action == 'decline':
        appl_db.considered = 'False'
    elif action == 'await':
        appl_db.considered = 'in_process'
    elif action == 'delete':
        db.session.delete(appl_db)
    db.session.commit()
    renew_session()
    if page == 'all':
        return redirect(url_for('.view_applications'))
    else:
        return redirect(url_for('.see_one_application', year=year, user=user))


@app.route('/assign_category/<user>/<category>')
def assign_category(user, category):
    if check_access(url='/assign_category/' + user + '/' + category) < 8:
        return redirect(url_for('.no_access'))
    user_info = get_user_info(user)
    cats_count, cats = categories_info(category)
    renew_session()
    return render_template('application management/confirm_assignment.html', user=user_info, category=cats)


@app.route('/confirm_assignment/<user>/<category>')
def confirm_assignment(user, category):
    if check_access(url='/confirm_assignment/' + user + '/' + category) < 8:
        return redirect(url_for('.no_access'))
    user = int(user)
    category = int(category)
    if category in [cat.cat_id for cat in CatSecretaries.query.all()]:
        cat = db.session.query(CatSecretaries).filter(CatSecretaries.cat_id == category).first()
        cat.secretary_id = user
    else:
        cat_sec = CatSecretaries(category, user)
        db.session.add(cat_sec)
    db.session.commit()
    renew_session()
    return redirect(url_for('.view_applications'))


@app.route('/users_list', defaults={'query': 'all'})
@app.route('/users_list/<query>')
def users_list(query):
    if check_access(url='/users_list/' + query) < 8:
        return redirect(url_for('.no_access'))
    renew_session()
    users = dict()
    if query == 'all':
        users = all_users()
    else:
        tel = re.sub(r'^8|^7|^(?=9)', '+7', ''.join([n for n in query if n not in tel_unneeded]))
        try:
            if int(query) in [u.user_id for u in Users.query.all()]:
                for u in Users.query.filter(Users.user_id == query).order_by(Users.user_id.desc()).all():
                    users[u.user_id] = get_user_info(u.user_id)
        except BaseException:
            pass
        if query in [u.email for u in Users.query.all()]:
            for u in Users.query.filter(Users.email == query).order_by(Users.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif tel in [u.tel for u in Users.query.all()]:
            for u in Users.query.filter(Users.tel == tel).order_by(Users.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif query.lower() in [u.last_name.lower() for u in Users.query.all()]:
            q = ''.join([query[0].upper(), query[1:].lower()])
            for u in Users.query.filter(Users.last_name == q).order_by(Users.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif query == 'secretary':
            for u in CatSecretaries.query.order_by(CatSecretaries.secretary_id.desc()).all():
                users[u.secretary_id] = get_user_info(u.secretary_id)
        elif query == 'supervisor':
            for u in SupervisorUser.query.order_by(SupervisorUser.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif query in access_types.keys():
            us = []
            for val in [val for val in access_types.values() if val >= access_types[query]]:
                for u in Users.query.filter(Users.user_type == list(access_types.keys()
                                                                    )[list(access_types.values()).index(val)
                ]).order_by(Users.user_id.desc()).all():
                    us.append(u.user_id)
            us.sort(reverse=True)
            for u in us:
                users[u] = get_user_info(u)
    return render_template('user_management/users_list.html', users=users)


@app.route('/search_user', methods=['GET'])
def search_user():
    renew_session()
    query = request.values.get('query', str)
    return redirect(url_for('.users_list', query=query))


@app.route('/user_page/<user>', defaults={'message': None})
@app.route('/user_page/<user>/<message>')
def user_page(user, message):
    renew_session()
    if check_access(url='/user_page/' + user) < 3:
        return redirect(url_for('.no_access'))
    user_info = get_user_info(user)
    profile = get_profile_info(user)
    if profile['born'] is not None:
        profile['born'] = profile['born'].strftime('%d.%m.%Y')
    cats_count, cats = categories_info()
    supers = get_supervisors()
    return render_template('user_management/user_page.html', user=user_info, profile=profile, categories=cats,
                           message=message, supervisors=supers)


@app.route('/assign_user_type/<user>', methods=['GET'])
def assign_user_type(user):
    renew_session()
    assign_type = request.values.get('assign_type', str)
    user_db = db.session.query(Users).filter(Users.user_id == user).first()
    user_db.user_type = assign_type
    db.session.commit()
    return redirect(url_for('.user_page', user=user))


@app.route('/remove_secretary/<user_id>/<cat_id>')
def remove_secretary(user_id, cat_id):
    renew_session()
    if check_access(url='/remove_secretary/' + user_id + '/' + cat_id) < 8:
        return redirect(url_for('.no_access'))
    cat_sec = CatSecretaries.query.filter(CatSecretaries.secretary_id == user_id
                                          ).filter(CatSecretaries.cat_id == cat_id).first()
    db.session.delete(cat_sec)
    db.session.commit()
    return redirect(url_for('.user_page', user=user_id))


@app.route('/category_page/<cat_id>', defaults={'errors': None})
@app.route('/category_page/<cat_id>/<errors>')
def category_page(cat_id, errors):
    category = one_category(db.session.query(Categories).filter(Categories.cat_id == cat_id).first())
    renew_session()
    need_analysis = check_analysis(cat_id=cat_id)
    works_no_fee = get_works_no_fee(cat_id)
    show_top_100 = True
    return render_template('categories/category_page.html', category=category, need_analysis=need_analysis,
                           errors=errors, works_no_fee=works_no_fee, show_top_100=show_top_100)


@app.route('/news_list')
def news_list():
    renew_session()
    if check_access(url='/news_list') < 8:
        return redirect(url_for('.no_access'))
    news = all_news()
    return render_template('news/news_list.html', news=news)


@app.route('/edit_news', defaults={'news_id': None})
@app.route('/edit_news/<news_id>')
def edit_news(news_id):
    renew_session()
    if news_id:
        if check_access(url='/edit_news/' + news_id) < 8:
            return redirect(url_for('.no_access'))
    else:
        if check_access(url='/edit_news/') < 8:
            return redirect(url_for('.no_access'))
    if news_id == 'None' or not news_id:
        news = {'news_id': None}
    else:
        news = one_news(news_id)
    return render_template('news/edit_news.html', news=news)


@app.route('/editing_news', methods=['POST'])
def editing_news():
    renew_session()
    news = dict()
    news_id = request.form['news_id']
    news['title'] = request.form['title']
    news['content'] = request.form['content']
    news['access'] = request.form['access']
    if news_id != 'None':
        news_id = int(news_id)
        if news_id in [n.news_id for n in News.query.all()]:
            db.session.query(News).filter(News.news_id == news_id).update(
                {News.title: news['title'], News.content: news['content'],
                 News.access: news['access']})
    else:
        news['publish'] = False
        new_news = News(news['title'], news['content'], news['access'], news['publish'])
        db.session.add(new_news)
    db.session.commit()
    return redirect(url_for('.news_list'))


@app.route('/publish_news/<news_id>')
def publish_news(news_id):
    renew_session()
    if check_access(url='/publish_news/' + news_id) < 8:
        return redirect(url_for('.no_access'))
    news = db.session.query(News).filter(News.news_id == news_id).first()
    if news.publish is True:
        news.publish = False
    elif news.publish is False:
        news.publish = True
    db.session.commit()
    return redirect(url_for('.news_list'))


@app.route('/supervisor_user/<user_id>', methods=['GET'])
def supervisor_user(user_id):
    renew_session()
    sup_id = request.values.get('user_supervisor')
    user_id = int(user_id)
    user = db.session.query(Users).filter(Users.user_id == user_id).first()
    if sup_id != 'None':
        sup_id = int(sup_id)
        supervisor = db.session.query(Supervisors).filter(Supervisors.supervisor_id == sup_id).first()
        if user_id in [u.user_id for u in SupervisorUser.query.all()]:
            user_db = db.session.query(SupervisorUser).filter(SupervisorUser.user_id == user_id).first()
            user_db.supervisor_id = supervisor.supervisor_id
            db.session.commit()
        else:
            sup_user = SupervisorUser(user.user_id, supervisor.supervisor_id)
            db.session.add(sup_user)
            db.session.commit()
    else:
        if user_id in [u.user_id for u in SupervisorUser.query.all()]:
            superv = SupervisorUser.query.filter(SupervisorUser.user_id == user_id).first().supervisor_id
            user_sup = SupervisorUser.query.filter(SupervisorUser.user_id == user_id
                                                   ).filter(SupervisorUser.supervisor_id == superv).first()
            db.session.delete(user_sup)
            db.session.commit()
    return redirect(url_for('.user_page', user=user_id))


@app.route('/organising_committee')
def organising_committee():
    membs = [get_org_info(u.user_id) for u
             in OrganisingCommittee.query.filter(OrganisingCommittee.year == curr_year).all()]
    m = sorted(membs, key=lambda u: u['first_name'])
    members = sorted(m, key=lambda u: u['last_name'])
    return render_template('organising_committee/organising_committee.html', members=members,
                           access=check_access(url='/organising_committee'), curr_year=curr_year)


@app.route('/set_orgcom')
def set_orgcom():
    users = []
    user_ids = [u.user_id for u in Users.query.order_by(Users.last_name).order_by(Users.first_name).all()
                if u.user_type in [u for u in access_types.keys() if access_types[u] >= 8]]
    for u in user_ids:
        users.append(get_user_info(u))
    org = [o.user_id for o in OrganisingCommittee.query.filter(OrganisingCommittee.year == curr_year).all()]
    return render_template('organising_committee/set_orgcom.html', curr_year=curr_year, users=users, org=org)


@app.route('/save_orgcom', methods=['POST'])
def save_orgcom():
    org = request.form.getlist('orgcom')
    orgcom = [int(o) for o in org]
    for org in orgcom:
        if org not in [o.user_id for o in OrganisingCommittee.query.filter(OrganisingCommittee.year ==
                                                                           curr_year).all()]:
            member = OrganisingCommittee(user_id=org, year=curr_year)
            db.session.add(member)
            db.session.commit()
    check = [u.user_id for u in OrganisingCommittee.query.all() if u.user_id not in orgcom]
    if check:
        for user in check:
            OrganisingCommittee.query.filter(OrganisingCommittee.user_id == user).delete()
            db.session.commit()
    return redirect(url_for('.organising_committee'))


@app.route('/responsibilities')
def responsibilities():
    resps = [get_responsibility(r.responsibility_id) for r
             in Responsibilities.query.filter(Responsibilities.year == curr_year).all()]
    respons = sorted(resps, key=lambda u: u['name'])
    return render_template('organising_committee/responsibilities.html', responsibilities=respons, curr_year=curr_year)


@app.route('/add_responsibilities', defaults={'responsibility_id': ''})
@app.route('/add_responsibilities/<responsibility_id>')
def add_responsibilities(responsibility_id):
    orgcom = [get_org_info(u.user_id) for u
              in OrganisingCommittee.query.filter(OrganisingCommittee.year == curr_year).all()]
    m = sorted(orgcom, key=lambda u: u['first_name'])
    orgcom = sorted(m, key=lambda u: u['last_name'])
    if responsibility_id:
        responsibility = get_responsibility(responsibility_id)
    else:
        responsibility = None
    return render_template('organising_committee/add_responsibilities.html', curr_year=curr_year, orgcom=orgcom,
                           responsibility=responsibility)


@app.route('/save_responsibilities', methods=['POST'])
def save_responsibilities():
    year = curr_year
    name = request.form['name']
    if 'description' in request.form.keys():
        description = request.form['description']
    else:
        description = None
    if 'responsibility_id' in request.form.keys() and request.form['responsibility_id'] != '':
        responsibility_id = int(request.form['responsibility_id'])
        if responsibility_id in [r.responsibility_id for r in Responsibilities.query.all()]:
            db.session.query(Responsibilities).filter(Responsibilities.responsibility_id == responsibility_id) \
                .update({Responsibilities.name: name, Responsibilities.description: description})
        db.session.commit()
    else:
        resp = Responsibilities(name, description, year)
        db.session.add(resp)
        db.session.commit()
        responsibility_id = Responsibilities.query.filter(Responsibilities.year == curr_year) \
            .filter(Responsibilities.name == name).first().responsibility_id
    if 'assignees' in request.form.keys() and request.form['assignees']:
        ass = request.form.getlist('assignees')
        assignees = [int(assn) for assn in ass]
        for org in assignees:
            if org not in [r.user_id for r
                           in ResponsibilityAssignment.query.filter(ResponsibilityAssignment.responsibility_id
                                                                    == responsibility_id).all()]:
                ra = ResponsibilityAssignment(org, responsibility_id)
                db.session.add(ra)
                db.session.commit()
        org_users = [o.user_id for o
                     in ResponsibilityAssignment.query.filter(ResponsibilityAssignment.responsibility_id
                                                              == responsibility_id).all()]
        for user in org_users:
            if user not in assignees:
                to_del = db.session.query(ResponsibilityAssignment)\
                    .filter(ResponsibilityAssignment.responsibility_id == responsibility_id)\
                    .filter(ResponsibilityAssignment.user_id == user).first()
                db.session.delete(to_del)
            db.session.commit()
    return redirect(url_for('.responsibilities'))


@app.route('/delete_responsibility/<resp_id>')
def delete_responsibility(resp_id):
    resp_id = int(resp_id)
    if resp_id in [r.responsibility_id for r in Responsibilities.query.all()]:
        to_del = db.session.query(Responsibilities).filter(Responsibilities.responsibility_id == resp_id).first()
        db.session.delete(to_del)
        db.session.commit()
    if resp_id in [r.responsibility_id for r in ResponsibilityAssignment.query.all()]:
        for user in [u.user_id for u
                     in ResponsibilityAssignment.query
                             .filter(ResponsibilityAssignment.responsibility_id == resp_id).all()]:
            to_del = db.session.query(ResponsibilityAssignment)\
                .filter(ResponsibilityAssignment.responsibility_id == resp_id)\
                .filter(ResponsibilityAssignment.user_id == user).first()
            db.session.delete(to_del)
            db.session.commit()
    return redirect(url_for('.responsibilities'))


@app.route('/rev_analysis')
def rev_analysis_management():
    renew_session()
    if check_access(url='/rev_analysis') < 10:
        return redirect(url_for('.no_access'))
    return render_template('rev_analysis/analysis_menu.html')


@app.route('/rev_analysis_results')
def rev_analysis_results():
    rev_criteria = get_criteria(curr_year)
    works = reg_works('all', 1)
    c, cats = categories_info()
    wks = sorted(works, key=lambda d: d['rk'], reverse=True)
    works = sorted(wks, key=lambda d: d['reg_tour'])
    cr_n = len(rev_criteria)
    return render_template('rev_analysis/rev_analysis_results.html', criteria=rev_criteria, works=works, cats=cats,
                           cr_n=cr_n)


@app.route('/analysis_state')
def analysis_state():
    renew_session()
    if check_access(url='/analysis_state') < 5:
        return redirect(url_for('.no_access'))
    ana_nums, all_stats = analysis_nums()
    return render_template('rev_analysis/analysis_state.html', ana_nums=ana_nums, all_stats=all_stats)


@app.route('/analysis_criteria')
def analysis_criteria():
    renew_session()
    if check_access(url='/analysis_criteria') < 8:
        return redirect(url_for('.no_access'))
    criteria = get_criteria(curr_year)
    return render_template('rev_analysis/analysis_criteria.html', criteria=criteria)


@app.route('/add_criteria')
def add_criteria():
    renew_session()
    if check_access(url='/add_criteria') < 10:
        return redirect(url_for('.no_access'))
    return render_template('rev_analysis/add_criteria.html')


@app.route('/download_criteria')
def download_criteria():
    renew_session()
    if check_access(url='/download_criteria') < 10:
        return redirect(url_for('.no_access'))
    prev_year = curr_year - 1
    criteria = get_criteria(prev_year)
    crit = [v for v in criteria.values()]
    lines = []
    for c in crit:
        lines.append(c['name'] + '\t' + c['description'] + '\t' + str(c['year']) + '\t' + str(c['weight']))
    if not os.path.isdir('static/files/rev_crit'):
        os.mkdir('static/files/rev_crit')
    f_name = 'static/files/rev_crit/criteria_' + str(prev_year) + '.txt'
    with open(f_name, 'w', encoding='utf-8') as f:
        f.writelines([line + '\n' for line in lines])
    path = f_name
    return send_file(path, as_attachment=True)


@app.route('/adding_criteria', methods=['POST'])
def adding_criteria():
    renew_session()
    data = request.form['data']
    for line in data.split('\n'):
        if line != '':
            criteria = line.split('\t')
            name = criteria[0].strip()
            description = criteria[1].strip()
            year = datetime.datetime.strptime(criteria[2].strip(), '%Y')
            weight = criteria[3].strip()
            crit = RevCriteria(name, description, year, weight)
            db.session.add(crit)
            db.session.commit()
    return redirect(url_for('.analysis_criteria'))


@app.route('/edit_criterion/<crit_id>')
def edit_criterion(crit_id):
    renew_session()
    if check_access(url='/edit_criterion' + crit_id) < 10:
        return redirect(url_for('.no_access'))
    criterion = get_criteria(curr_year)[int(crit_id)]
    return render_template('rev_analysis/edit_criterion.html', criterion=criterion)


@app.route('/write_criterion', methods=['POST'])
def write_criterion():
    renew_session()
    crit_id = int(request.form['id'])
    crit_name = request.form['name']
    if 'description' in request.form.keys():
        description = request.form['description']
    else:
        description = None
    crit_weight = int(request.form['weight'])
    if crit_id in [c.criterion_id for c in RevCriteria.query.all()]:
        db.session.query(RevCriteria).filter(RevCriteria.criterion_id == crit_id
                                             ).update({RevCriteria.criterion_name: crit_name,
                                                       RevCriteria.criterion_description: description,
                                                       RevCriteria.weight: crit_weight})
        db.session.commit()
    return redirect(url_for('.analysis_criteria'))


@app.route('/edit_value/<val_id>')
def edit_value(val_id):
    renew_session()
    if check_access(url='/edit_value' + val_id) < 10:
        return redirect(url_for('.no_access'))
    val = db.session.query(RevCritValues).filter(RevCritValues.value_id == int(val_id)).first()
    value = dict()
    value['id'] = val.value_id
    value['name'] = val.value_name
    value['comment'] = val.comment
    value['weight'] = val.weight
    return render_template('rev_analysis/edit_value.html', value=value)


@app.route('/write_value', methods=['POST'])
def write_value():
    renew_session()
    val_id = int(request.form['id'])
    val_name = request.form['name']
    if 'comment' in request.form.keys():
        comment = request.form['description']
    else:
        comment = None
    val_weight = int(request.form['weight'])
    if val_id in [v.value_id for v in RevCritValues.query.all()]:
        db.session.query(RevCritValues).filter(RevCritValues.value_id == val_id
                                               ).update({RevCritValues.value_name: val_name,
                                                         RevCritValues.comment: comment,
                                                         RevCritValues.weight: val_weight})
        db.session.commit()
    return redirect(url_for('.analysis_criteria'))


@app.route('/add_values')
def add_values():
    renew_session()
    if check_access(url='/add_values') < 10:
        return redirect(url_for('.no_access'))
    return render_template('rev_analysis/add_values.html')


@app.route('/adding_values', methods=['POST'])
def adding_values():
    renew_session()
    data = request.form['data']
    for line in data.split('\n'):
        if line != '':
            values = line.split('\t')
            criterion = values[0].strip()
            value = values[1].strip()
            comment = values[2].strip()
            weight = values[3].strip()
            vals = RevCritValues(value, comment, weight)
            db.session.add(vals)
            db.session.commit()
            criterion_id = RevCriteria.query.filter(RevCriteria.year == datetime.datetime.strptime(str(curr_year), '%Y'
                                                                                                   ).date()
                                                    ).filter(RevCriteria.criterion_name == criterion
                                                             ).first().criterion_id
            vals = RevCritValues.query.order_by(RevCritValues.value_id.desc()
                                                ).filter(RevCritValues.value_name == value).all()
            val_ids = [v.value_id for v in vals if v.value_id not in [va.value_id for va in CriteriaValues.query.all()]]
            value_id = sorted(val_ids, reverse=True)[0]
            crit_val = CriteriaValues(criterion_id, value_id)
            db.session.add(crit_val)
            db.session.commit()
    return redirect(url_for('.analysis_criteria'))


@app.route('/download_values')
def download_values():
    renew_session()
    if check_access(url='/download_values') < 10:
        return redirect(url_for('.no_access'))
    prev_year = curr_year - 1
    criteria = get_criteria(prev_year)
    crit = [v for v in criteria.values()]
    lines = []
    for c in crit:
        crit_name = c['name']
        for v in c['values'].values():
            if v['comment'] is None:
                comment = ''
            else:
                comment = v['comment']
            lines.append(crit_name + '\t' + v['val_name'] + '\t' + comment + '\t' + str(v['val_weight']))
    if not os.path.isdir('static/files/rev_crit'):
        os.mkdir('static/files/rev_crit')
    f_name = 'static/files/rev_crit/values_' + str(prev_year) + '.txt'
    with open(f_name, 'w', encoding='utf-8') as f:
        f.writelines([line + '\n' for line in lines])
    path = f_name
    return send_file(path, as_attachment=True)


@app.route('/analysis_works/<cat_id>')
def analysis_works(cat_id):
    renew_session()
    if check_access(url='/analysis_works/' + cat_id) < 5:
        return redirect(url_for('.no_access'))
    works = get_works(cat_id, 2)
    category = one_category(db.session.query(Categories).filter(Categories.cat_id == cat_id).first())
    renew_session()
    need_analysis = check_analysis(cat_id)
    return render_template('rev_analysis/analysis_works.html', works=works, category=category,
                           need_analysis=need_analysis)


@app.route('/review_analysis/<work_id>')
def review_analysis(work_id):
    renew_session()
    if check_access(url='/review_analysis' + work_id) < 5:
        return redirect(url_for('.no_access'))
    work = work_info(work_id)
    rk, analysis = get_analysis(work_id)
    criteria = get_criteria(curr_year)
    pre_ana = get_pre_analysis(work_id)
    if pre_ana is None:
        return redirect(url_for('.pre_analysis', work_id=work_id))
    work_id = int(work_id)
    if work_id in [w.work_id for w in RevComment.query.all()]:
        wo = db.session.query(RevComment).filter(RevComment.work_id == work_id).first()
        work_comment = wo.work_comment
        rev_comment = wo.rev_comment
    else:
        work_comment = None
        rev_comment = None
    return render_template('rev_analysis/review_analysis.html', work=work, analysis=analysis, criteria=criteria,
                           pre_ana=pre_ana, work_comment=work_comment, rev_comment=rev_comment)


@app.route('/pre_analysis/<work_id>')
def pre_analysis(work_id):
    renew_session()
    if check_access(url='/pre_analysis' + work_id) < 6:
        return redirect(url_for('.no_access'))
    work = work_info(work_id)
    work_id = int(work_id)
    pre = get_pre_analysis(work_id)
    if work_id in [w.work_id for w in RevComment.query.all()]:
        work_comment = RevComment.query.filter(RevComment.work_id == work_id).first().work_comment
        if work_comment is None:
            work_comment = ''
    else:
        work_comment = ''
    return render_template('/rev_analysis/pre_analysis.html', work=work, pre_ana=pre, work_comment=work_comment)


@app.route('/write_pre_analysis', methods=['POST'])
def write_pre_analysis():
    renew_session()
    work_id = request.form['work_id']
    work_id = int(work_id)
    if 'good_work' in request.form.keys():
        if request.form['good_work'] == 'True':
            good_work = True
        else:
            good_work = False
    else:
        good_work = None
    if 'research' in request.form.keys():
        research = request.form['research']
    else:
        research = None
    if 'has_review' in request.form.keys():
        if request.form['has_review'] == 'True':
            has_review = True
            rev_type = None
        elif request.form['has_review'] == 'points':
            has_review = False
            rev_type = 'points'
        else:
            has_review = False
            rev_type = None
    else:
        has_review = None
        rev_type = None
    if 'pushed' in request.form.keys():
        pushed = request.form['pushed']
        if pushed == 'True':
            pushed = True
        elif pushed == 'False':
            pushed = False
        else:
            pushed = None
    if 'work_comment' in request.form.keys() and request.form['work_comment'] != '':
        work_comment = request.form['work_comment']
    else:
        work_comment = None
    if work_id in [w.work_id for w in PreAnalysis.query.all()]:
        db.session.query(PreAnalysis).filter(PreAnalysis.work_id == int(work_id)).update(
            {PreAnalysis.good_work: good_work, PreAnalysis.research: research,
             PreAnalysis.has_review: has_review, PreAnalysis.rev_type: rev_type, PreAnalysis.pushed: pushed})
        db.session.commit()
    else:
        pre_ana = PreAnalysis(work_id, good_work, research, has_review, rev_type, pushed, None, None)
        db.session.add(pre_ana)
        db.session.commit()
    if work_id in [w.work_id for w in RevComment.query.all()]:
        db.session.query(RevComment).filter(RevComment.work_id == int(work_id)).update(
            {RevComment.work_comment: work_comment})
        db.session.commit()
    elif work_comment is not None:
        w_comm = RevComment(work_id, work_comment, None)
        db.session.add(w_comm)
        db.session.commit()
    if has_review is True:
        return redirect(url_for('.analysis_form', work_id=work_id))
    else:
        cat_id = WorkCategories.query.filter(WorkCategories.work_id == work_id).first().cat_id
        if work_id in [a.work_id for a in RevAnalysis.query.all()]:
            rev_ana = db.session.query(RevAnalysis).filter(RevAnalysis.work_id == work_id).all()
            for ana in rev_ana:
                db.session.delete(ana)
                db.session.commit()
        return redirect(url_for('.analysis_works', cat_id=cat_id))


@app.route('/analysis_form/<work_id>', defaults={'internal': None})
@app.route('/analysis_form/<work_id>/<internal>')
def analysis_form(work_id, internal):
    renew_session()
    if check_access(url='/analysis_form' + work_id) < 6:
        return redirect(url_for('.no_access'))
    criteria = get_criteria(curr_year)
    if not internal:
        work_id = int(work_id)
        work = work_info(work_id)
        rk, analysis = get_analysis(work_id)
        if work_id in [w.work_id for w in RevComment.query.all()]:
            rev_comment = RevComment.query.filter(RevComment.work_id == work_id).first().rev_comment
            if rev_comment is None:
                rev_comment = ''
        else:
            rev_comment = ''
        return render_template('/rev_analysis/analysis_form.html', criteria=criteria, work=work, analysis=analysis,
                               rev_comment=rev_comment, internal=None)
    else:
        work = {'work_id': int(work_id)}
        rk, analysis = get_analysis(work_id, 'internal')
        if int(work_id) in [r.review_id for r in InternalReviewComments.query.all()]:
            rev_comment = InternalReviewComments.query.filter(InternalReviewComments.review_id == int(work_id)) \
                .first().comment
        else:
            rev_comment = ''
        return render_template('/rev_analysis/analysis_form.html', criteria=criteria, work=work, internal=internal,
                               analysis=analysis, rev_comment=rev_comment)


@app.route('/write_analysis/<internal>', methods=['POST'])
def write_analysis(internal):
    if internal == 'None':
        internal = None
    renew_session()
    work_id = int(request.form['work_id'])
    criteria_ids = [criterion.criterion_id for criterion in RevCriteria.query.all()]
    for criterion_id in criteria_ids:
        if str(criterion_id) in request.form.keys():
            value = int(request.form[str(criterion_id)])
            if not internal:
                if work_id in [w.work_id for w in RevAnalysis.query.all()]:
                    if criterion_id in [c.criterion_id for c in
                                        RevAnalysis.query.filter(RevAnalysis.work_id == work_id).all()]:
                        d = db.session.query(RevAnalysis).filter(RevAnalysis.work_id == work_id)
                        d.filter(RevAnalysis.criterion_id == criterion_id).update({RevAnalysis.value_id: value})
                        db.session.commit()
                    else:
                        crit_value = RevAnalysis(work_id, criterion_id, value)
                        db.session.add(crit_value)
                        db.session.commit()
                else:
                    crit_value = RevAnalysis(work_id, criterion_id, value)
                    db.session.add(crit_value)
                    db.session.commit()
            else:
                review_id = work_id
                if review_id in [r.review_id for r in InternalAnalysis.query.all()]:
                    if criterion_id in [c.criterion_id for c in
                                        InternalAnalysis.query.filter(InternalAnalysis.review_id == review_id).all()]:
                        d = db.session.query(InternalAnalysis).filter(InternalAnalysis.review_id == review_id)
                        d.filter(InternalAnalysis.criterion_id == criterion_id) \
                            .update({InternalAnalysis.value_id: value})
                        db.session.commit()
                    else:
                        crit_value = InternalAnalysis(review_id, criterion_id, value)
                        db.session.add(crit_value)
                        db.session.commit()
                else:
                    crit_value = InternalAnalysis(review_id, criterion_id, value)
                    db.session.add(crit_value)
                    db.session.commit()
    if not internal:
        if 'rev_comment' in request.form.keys() and request.form['rev_comment'] != '':
            rev_comment = request.form['rev_comment']
        else:
            rev_comment = None
        if work_id in [w.work_id for w in RevComment.query.all()]:
            db.session.query(RevComment).filter(RevComment.work_id == int(work_id)).update(
                {RevComment.rev_comment: rev_comment})
            db.session.commit()
        elif rev_comment is not None:
            rev_comm = RevComment(work_id, None, rev_comment)
            db.session.add(rev_comm)
            db.session.commit()
        cat_id = WorkCategories.query.filter(WorkCategories.work_id == work_id).first().cat_id
        return redirect(url_for('.analysis_works', cat_id=cat_id))
    else:
        review_id = int(work_id)
        if 'rev_comment' in request.form.keys() and request.form['rev_comment'] != '':
            rev_comment = request.form['rev_comment']
        else:
            rev_comment = None
        if review_id in [r.review_id for r in InternalReviewComments.query.all()]:
            db.session.query(InternalReviewComments).filter(InternalReviewComments.review_id == review_id).update(
                {InternalReviewComments.comment: rev_comment})
            db.session.commit()
        elif rev_comment:
            rev_comm = InternalReviewComments(review_id=review_id, comment=rev_comment)
            db.session.add(rev_comm)
            db.session.commit()
        reviewer_id = InternalReviews.query.filter(InternalReviews.review_id == review_id).first().reviewer_id
        return redirect(url_for('.see_reviews', reviewer_id=reviewer_id))


@app.route('/reviewer_comment/<reviewer_id>', methods=['POST'])
def reviewer_comment(reviewer_id):
    reviewer_id = int(reviewer_id)
    comment = request.form['text']
    if reviewer_id not in [r.reviewer_id for r in InternalReviewerComments.query.all()]:
        r = InternalReviewerComments(reviewer_id, comment)
        db.session.add(r)
        db.session.commit()
    else:
        db.session.query(InternalReviewerComments).filter(InternalReviewerComments.reviewer_id == reviewer_id) \
            .update({InternalReviewerComments.comment: comment})
        db.session.commit()
    return redirect(url_for('.see_reviews', reviewer_id=reviewer_id))


@app.route('/add_reviews', defaults={'done': None})
@app.route('/add_reviews/<done>')
def add_reviews(done):
    return render_template('internal_reviews/add_reviews.html', done=done)


@app.route('/save_reviews')
def save_reviews():
    response = json.loads(requests.post(url="https://vernadsky.info/all-works-json/2023/",
                                        headers=mail_data.headers).text)
    for work in response:
        work_id = int(work['number'])
        if work['reviews']:
            for revs in work['reviews']:
                reviewer = revs['reviewer'].strip()
                review_id = int(revs['id'].strip())
                if reviewer not in [r.reviewer for r in InternalReviewers.query.all()]:
                    ir = InternalReviewers(reviewer)
                    db.session.add(ir)
                    db.session.commit()
                reviewer_id = InternalReviewers.query.filter(InternalReviewers.reviewer == reviewer).first().reviewer_id
                if review_id not in [r.review_id for r in InternalReviews.query.all()]:
                    rev = InternalReviews(review_id=review_id, reviewer_id=reviewer_id)
                    db.session.add(rev)
                    db.session.commit()
                else:
                    db.session.query(InternalReviews).filter(InternalReviews.review_id == review_id) \
                        .update({InternalReviews.reviewer_id: reviewer_id})
                    db.session.commit()
                if review_id not in [w.review_id for w in
                                     WorkReviews.query.filter(WorkReviews.work_id == work_id).all()]:
                    to_add = WorkReviews(work_id, review_id)
                    db.session.add(to_add)
                    db.session.commit()
                else:
                    db.session.query(WorkReviews).filter(WorkReviews.review_id == review_id) \
                        .update({WorkReviews.work_id: work_id})
                    db.session.commit()
    done = True
    return redirect(url_for('.add_reviews', done=done))


@app.route('/int_analysis')
def int_analysis():
    if check_access(url='/int_analysis') < 8:
        return redirect(url_for('.no_access'))
    return render_template('internal_reviews/int_analysis.html')


@app.route('/reviewers_to_review')
def reviewers_to_review():
    if check_access(url='/reviewers_to_review') < 8:
        return redirect(url_for('.no_access'))
    c, cats = categories_info()
    for cat in cats:
        cat_works = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat['id'])]
        reviews = [{'work_id': w.work_id, 'reviewers': w.reviewers} for w in InternalReviews.query.all()
                   if w.work_id in cat_works]
        reviewers = []
        for rev in reviews:
            reviewers.extend([rev.strip() for rev in rev['reviewers'].split(',')])
        reviewers = set(reviewers)
        cat['reviewers'] = sorted(list(reviewers))
    return render_template('internal_reviews/reviewers_to_review.html', cats=cats)


@app.route('/internal_reviews')
def internal_reviews():
    if check_access(url='/internal_reviews') < 8:
        return redirect(url_for('.no_access'))
    reviewers = [{'id': r.reviewer_id, 'name': r.reviewer} for r in InternalReviewers.query.all()]
    for reviewer in reviewers:
        if reviewer['id'] in [r.reviewer_id for r in ReadingReviews.query.all()]:
            u = ReadingReviews.query.filter(ReadingReviews.reviewer_id == reviewer['id']).first()
            user = db.session.query(Users).filter(Users.user_id == u.reader_id).first()
            reader = {'id': user.user_id, 'name': user.first_name, 'l_name': user.last_name}
            reviewer['reader'] = reader
    return render_template('internal_reviews/internal_reviews.html', reviewers=reviewers)


@app.route('/see_reviews/<reviewer_id>')
def see_reviews(reviewer_id):
    if check_access(url='/see_reviews/' + str(reviewer_id)) < 8:
        return redirect(url_for('.no_access'))
    reviews = []
    for r in InternalReviews.query.filter(InternalReviews.reviewer_id == int(reviewer_id)).all():
        if r.review_id in [a.review_id for a in InternalAnalysis.query.all()]:
            read = True
        else:
            read = False
        reviews.append({'id': r.review_id,
                        'text': requests.post(url='https://vernadsky.info/personal_office/'
                                                  'works_distribution_to_reviewers/?review=' + str(r.review_id)
                                                  + '&raw=1', headers=mail_data.headers).text, 'read': read})
    rev_no = len(reviews)
    read = len([r for r in reviews if r['read'] is True])
    if int(reviewer_id) in [r.reviewer_id for r in ReadingReviews.query.all()]:
        read_by = ReadingReviews.query.filter(ReadingReviews.reviewer_id == reviewer_id).first().reader_id
    else:
        read_by = None
    if int(reviewer_id) in [r.reviewer_id for r in InternalReviewerComments.query.all()]:
        comment = InternalReviewerComments.query.filter(InternalReviewerComments.reviewer_id == int(reviewer_id)) \
            .first().comment
    else:
        comment = None
    return render_template('internal_reviews/see_reviews.html', reviews=reviews, reviewer_id=reviewer_id,
                           rev_no=rev_no, read_by=read_by, comment=comment, read=read)


@app.route('/assign_reviewer/<do>/<reviewer_id>/<user_id>')
def assign_reviewer(do, reviewer_id, user_id):
    reviewer_id = int(reviewer_id)
    user_id = int(user_id)
    if do == 'do':
        if reviewer_id not in [r.reviewer_id for r in ReadingReviews.query.all()]:
            read = ReadingReviews(reviewer_id, user_id)
            db.session.add(read)
            db.session.commit()
        else:
            db.session.query(ReadingReviews).filter(ReadingReviews.reviewer_id == reviewer_id) \
                .update({ReadingReviews.reader_id: user_id})
            db.session.commit()
    elif do == 'undo':
        if reviewer_id in [r.reviewer_id for r in
                           ReadingReviews.query.filter(ReadingReviews.reader_id == user_id).all()]:
            to_del = db.session.query(ReadingReviews).filter(ReadingReviews.reviewer_id == reviewer_id) \
                .filter(ReadingReviews.reader_id == user_id).first()
            db.session.delete(to_del)
            db.session.commit()
    return redirect(url_for('.see_reviews', reviewer_id=reviewer_id))


@app.route('/add_works', defaults={'works_added': None, 'works_edited': None})
@app.route('/add_works/<works_added>/<works_edited>')
def add_works(works_added, works_edited):
    renew_session()
    if check_access(url='/add_works') < 8:
        return redirect(url_for('.no_access'))
    return render_template('works/add_works.html', works_added=works_added, works_edited=works_edited)


@app.route('/applications_2_tour')
def applications_2_tour():
    renew_session()
    if check_access(url='/add_works') < 8:
        return redirect(url_for('.no_access'))
    return render_template('works/applications_2_tour.html', year=curr_year)


@app.route('/many_works', methods=['POST'])
def many_works():
    renew_session()
    text = '{"works": ' + request.form['text'].strip('\n') + '}'
    works_added = 0
    works_edited = 0

    works = json.loads(text)
    w = works['works']

    for n in w:
        edited = False
        work_site_id = int(n['id'])
        work_id = int(n['number'])
        email = n['contacts']['email']
        tel = n['contacts']['phone']
        work_name = n['title']
        cat = n['section']['id']
        country = n['organization']['country']
        region = n['organization']['region']
        city = n['organization']['city']
        country_db = db.session.query(Cities)
        if country in [c.country for c in country_db.all()]:
            region_db = country_db.filter(Cities.country == country)
            if region in [r.region for r in region_db.all()]:
                city_db = region_db.filter(Cities.region == region)
                if city in [c.city for c in city_db.all()]:
                    timeshift = city_db.filter(Cities.city == city).first().msk_time_shift
                else:
                    timeshift = None
            else:
                timeshift = None
        else:
            timeshift = None
        if cat == 0:
            cat_id = None
        else:
            cat_id = Categories.query.filter(Categories.cat_site_id == cat).first().cat_id
        authors = n['authors']
        author_1_name = authors[0]['name']
        author_1_age = authors[0]['age']
        author_1_class = authors[0]['class']
        if len(authors) > 1:
            author_2_name = authors[1]['name']
            author_2_age = authors[1]['age']
            author_2_class = authors[1]['class']
        else:
            author_2_name = None
            author_2_age = None
            author_2_class = None
        if len(authors) > 2:
            author_3_name = authors[2]['name']
            author_3_age = authors[2]['age']
            author_3_class = authors[2]['class']
        else:
            author_3_name = None
            author_3_age = None
            author_3_class = None
        teacher_name = n['teacher']['name']
        if teacher_name == '':
            teacher_name = None
        status_id = int(n['status']['id'])
        status_name = n['status']['value']
        reg_tour = n['regional_tour']
        if work_id in [w.work_id for w in Works.query.all()]:
            db.session.query(Works).filter(Works.work_id == work_id).update({Works.work_name: work_name,
                                                                             Works.work_site_id: work_site_id,
                                                                             Works.email: email, Works.tel: tel,
                                                                             Works.author_1_name: author_1_name,
                                                                             Works.author_1_age: author_1_age,
                                                                             Works.author_1_class: author_1_class,
                                                                             Works.author_2_name: author_2_name,
                                                                             Works.author_2_age: author_2_age,
                                                                             Works.author_2_class: author_2_class,
                                                                             Works.author_3_name: author_3_name,
                                                                             Works.author_3_age: author_3_age,
                                                                             Works.author_3_class: author_3_class,
                                                                             Works.teacher_name: teacher_name,
                                                                             Works.reg_tour: reg_tour,
                                                                             Works.msk_time_shift: timeshift})
            edited = True
            db.session.commit()
        else:
            work_write = Works(work_id, work_name, work_site_id, email, tel, author_1_name, author_1_age,
                               author_1_class,
                               author_2_name, author_2_age, author_2_class, author_3_name, author_3_age, author_3_class,
                               teacher_name, reg_tour, timeshift, None)
            db.session.add(work_write)
            works_added += 1
            db.session.commit()
        if status_id not in [s.status_id for s in ParticipationStatuses.query.all()]:
            part_status = ParticipationStatuses(status_id, status_name)
            db.session.add(part_status)
            db.session.commit()
        if work_id in [s.work_id for s in WorkStatuses.query.all()]:
            db.session.query(WorkStatuses).filter(WorkStatuses.work_id == work_id
                                                  ).update({WorkStatuses.status_id: status_id})
            db.session.commit()
            edited = True
        else:
            work_status = WorkStatuses(work_id, status_id)
            db.session.add(work_status)
            db.session.commit()
        if work_id in [w.work_id for w in WorkCategories.query.all()]:
            if not cat_id:
                work_cat = db.session.query(WorkCategories).filter(WorkCategories.work_id == work_id).first()
                db.session.delete(work_cat)
                db.session.commit()
                edited = True
            else:
                db.session.query(WorkCategories).filter(WorkCategories.work_id == work_id
                                                        ).update({WorkCategories.cat_id: cat_id})
                db.session.commit()
                edited = True
        else:
            if cat_id:
                work_cat = WorkCategories(work_id, cat_id)
                db.session.add(work_cat)
                db.session.commit()
        if edited:
            works_edited += 1
    return redirect(url_for('.add_works', works_added=works_added, works_edited=works_edited))


@app.route('/many_applications', methods=['POST'])
def many_applications():
    renew_session()
    text = '{"works": ' + request.form['text'].strip('\n') + '}'
    works = json.loads(text)
    w = works['works']
    works_applied = []
    participants = []
    for n in w:
        works = [{'work': int(a['number']), 'appl': int(n['id']), 'arrived': bool(n['arrival'])} for a in n['works']]
        works_applied.extend(works)
        part_s = [{'id': int(p['id']), 'appl': int(n['id']), 'last_name': p['last_name'],
                   'first_name': p['first_name'], 'patronymic_name': p['patronymic_name'],
                   'participant_class': p['class'], 'role': p['role']} for p in n['delegation']['members']]
        participants.extend(part_s)
        for participant in ParticipantsApplied.query.filter(ParticipantsApplied.appl_id == int(n['id'])).all():
            if participant.participant_id not in [p['id'] for p in participants]:
                part_to_del = db.session.query(ParticipantsApplied).filter(ParticipantsApplied.participant_id ==
                                                                           participant.participant_id).first()
                db.session.delete(part_to_del)
                db.session.commit()
    for appl in set(a.appl_id for a in ParticipantsApplied.query.all()):
        if appl not in [a['appl'] for a in participants]:
            ParticipantsApplied.query.filter(ParticipantsApplied.appl_id == appl).delete()
            db.session.commit()
    for work in works_applied:
        if work['work'] in [wo.work_id for wo in Applications2Tour.query.all()]:
            db.session.query(Applications2Tour).filter(Applications2Tour.work_id == work['work']
                                                       ).update({Applications2Tour.appl_no: work['appl'],
                                                                 Applications2Tour.arrived: work['arrived']})
            db.session.commit()
        else:
            if work['work'] in [wo.work_id for wo in Works.query.all()]:
                wo = Works.query.filter(Works.work_id == work['work']).first().work_id
                appl = Applications2Tour(wo, work['appl'], False)
                db.session.add(appl)
            db.session.commit()
    for participant in participants:
        if participant['id'] in [part.participant_id for part in ParticipantsApplied.query.all()]:
            db.session.query(ParticipantsApplied
                             ).filter(ParticipantsApplied.participant_id == participant['id']
                                      ).update({ParticipantsApplied.appl_id: participant['appl'],
                                                ParticipantsApplied.last_name: participant['last_name'],
                                                ParticipantsApplied.first_name: participant['first_name'],
                                                ParticipantsApplied.patronymic_name: participant['patronymic_name'],
                                                ParticipantsApplied.participant_class: participant['participant_class'],
                                                ParticipantsApplied.role: participant['role']})
            db.session.commit()
        else:
            part = ParticipantsApplied(participant['id'], participant['appl'], participant['last_name'],
                                       participant['first_name'], participant['patronymic_name'],
                                       participant['participant_class'], participant['role'], None)
            db.session.add(part)
            db.session.commit()
    return redirect(url_for('.applications_2_tour'))


@app.route('/top_100')
def top_100():
    if check_access(url='/top_100') < 5:
        return redirect(url_for('.no_access'))
    total, no_fee = no_fee_nums()
    return render_template('works/top_100.html', no_fee=no_fee, total=total)


@app.route('/apply_for_online', defaults={'errs_a': None, 'errs_b': None})
@app.route('/apply_for_online/<errs_a>/<errs_b>')
def apply_for_online(errs_a, errs_b):
    if errs_b == 'a':
        errs_b = None
    elif errs_b is not None:
        errs_b = errs_b.split('\n')
    if errs_a == 'a':
        errs_a = None
    elif errs_a is not None:
        errs_a = errs_a.split('\n')
    return render_template('online_reports/apply_for_online.html', errors_a=errs_a, errors_b=errs_b)


@app.route('/applied_for_online', methods=['POST'])
def applied_for_online():
    works = request.form['works']
    works_list = []
    success = False
    if ',' in works:
        works_list.extend(works.split(','))
    else:
        works_list.append(works)
    errors = {}
    for work in set(works_list):
        try:
            work = int(work.strip())
            if work in [w.work_id for w in Works.query.all()]:
                work_db = db.session.query(Works).filter(Works.work_id == work).first()
                if WorkStatuses.query.filter(WorkStatuses.work_id == work).first().status_id < 6:
                    errors[work] = 'работа не прошла во Второй тур'
                else:
                    if work_db.work_id in [w.work_id for w in ParticipatedWorks.query.all()]:
                        errors[work] = 'работа уже участвовала во 2 туре'
                    else:
                        if work not in [w.work_id for w in AppliedForOnline.query.all()]:
                            w = AppliedForOnline(work_db.work_id)
                            db.session.add(w)
                            db.session.commit()
                            success = True
            else:
                errors[work] = 'работа не найдена'
        except ValueError:
            if success is False and work not in errors.keys():
                errors[work] = 'некорректный номер работы'
            pass
    errs = ''
    if errors != {}:
        for work, error in errors.items():
            errs += str(work) + ' - ' + error + '\n'
    else:
        errs = None
    return redirect(url_for('.apply_for_online', errs_a=errs, errs_b='a'))


@app.route('/participated', methods=['POST'])
def participated():
    works = request.form['works']
    works_list = []
    success = False
    if ',' in works:
        works_list.extend(works.split(','))
    else:
        works_list.append(works)
    errors = {}
    for work in set(works_list):
        try:
            work = int(work.strip())
            if work in [w.work_id for w in Works.query.all()]:
                if work not in [w.work_id for w in ParticipatedWorks.query.all()]:
                    work_db = db.session.query(Works).filter(Works.work_id == work).first()
                    w = ParticipatedWorks(work_db.work_id)
                    db.session.add(w)
                    db.session.commit()
                    success = True
            else:
                errors[work] = 'работа не найдена'
        except ValueError:
            if success is False and work not in errors.keys():
                errors[work] = 'некорректный номер работы'
            pass
    errs = ''
    if errors != {}:
        for work, error in errors.items():
            errs += str(work) + ' - ' + error + '\n'
    else:
        errs = None
    return redirect(url_for('.apply_for_online', errs_b=errs, errs_a='a'))


@app.route('/online_applicants')
def online_applicants():
    cats = []

    text = '<h2>Работы, заявленные для участия в Дополнительном онлайн-конкурсе</h2>\n'
    text += '''<p>В список выступающих работа будет включена только после оплаты оргвзноса.
        Если вы оплатили оргвзнос 3 или больше рабочих дня назад, и это не отражено в таблице,
        пришлите чек оплаты оргвзноса на <a href="info@vernadsky.info" target="_blank">info@vernadsky.info</a>.
        <br>Если вы подали заявку на участие, но не были включены в список ниже,
        напишите об этом на <a href="info@vernadsky.info" target="_blank">info@vernadsky.info</a>.</p>\n'''
    table = '''<table frame="void" border="1px" bordercolor="#4962A4" cellpadding="3px" cellspacing="0px">
        <tr>
            <td width="6%" align="сenter"><b>
                Номер работы
            </b></td>
            <td width="59%" align="сenter"><b>
                Название
            </b></td>
            <td width="25%" align="сenter"><b>
                Авторы
            </b></td>
            <td width="10%" align="сenter"><b>
                Оргвзнос
            </b></td>
        </tr>'''

    for cat in [c.cat_id for c in Categories.query.filter(Categories.year == curr_year).all()]:
        c, cat_info = categories_info(cat)
        cat_works = [work_info(w.work_id) for w in
                     Works.query.join(WorkCategories, Works.work_id == WorkCategories.work_id)
                     .filter(WorkCategories.cat_id == cat).all() if w.work_id in [wo.work_id for wo
                                                                                  in AppliedForOnline.query.all()]]
        cat_info['works'] = cat_works
        cats.append(cat_info)
        if cat_info['works']:
            table += '''\n<tr><td align="сenter" colspan="4"><b>'''
            cat_row = cat_info['name'] + '''</b></td>\n</tr>'''
            table += cat_row
            for work in cat_info['works']:
                table += '''\n<tr><td align="сenter">'''
                to_add = str(work['work_id']) + '''</td><td>'''
                table += to_add
                to_add = work['work_name'] + '''</td><td>'''
                table += to_add
                to_add = work['authors'] + '''</td><td align="сenter">'''
                table += to_add
                if work['payed'] is True:
                    to_add = '''Оплачен</td><td>'''
                else:
                    to_add = '''Не оплачен</td></tr>'''
                table += to_add

    table += '''\n</table>'''
    text += table
    with open('static/files/generated_files/online_applicants.html', 'w', encoding='utf-8') as f:
        f.write(text)
    return render_template('online_reports/online_applicants.html', cats=cats)


@app.route('/download_applicants')
def download_applicants():
    return send_file('static/files/generated_files/online_applicants.html', as_attachment=True)


@app.route('/works_for_free/<cat_id>', methods=['POST'])
def works_for_free(cat_id):
    works = request.form['works']
    works_list = []
    success = False
    if ',' in works:
        works_list.extend(works.split(','))
    else:
        works_list.append(works)
    errors = {}
    for work in works_list:
        try:
            work = int(work.strip())
            if work in [w.work_id for w in Works.query.all()]:
                work_db = db.session.query(Works).filter(Works.work_id == work).first()
                if work_db.work_id in [w.work_id for w
                                       in WorkCategories.query.filter(WorkCategories.cat_id == cat_id).all()]:
                    if WorkStatuses.query.filter(WorkStatuses.work_id == work).first().status_id < 2:
                        errors[work] = 'работа не прошла на Конкурс'
                    else:
                        if work_db.reg_tour:
                            errors[work] = 'работа регионального тура, нельзя отменить оргвзнос'
                        else:
                            if work not in [w.work_id for w in WorksNoFee.query.all()]:
                                wnf = WorksNoFee(work_db.work_id)
                                db.session.add(wnf)
                                db.session.commit()
                                success = True
                else:
                    errors[work] = 'работа не из вашей секции'
            else:
                errors[work] = 'работа не найдена'
        except BaseException:
            if success is False and work not in errors.keys():
                errors[work] = 'некорректный номер работы'
            pass
    errs = ''
    if errors != {}:
        for work, error in errors.items():
            errs += str(work) + ' - ' + error + '\n'
    else:
        errs = None
    return redirect(url_for('.category_page', cat_id=cat_id, errors=errs))


@app.route('/remove_no_fee/<cat_id>/<work_id>')
def remove_no_fee(cat_id, work_id):
    work = db.session.query(WorksNoFee).filter(WorksNoFee.work_id == work_id).first()
    db.session.delete(work)
    db.session.commit()
    return redirect(url_for('.category_page', cat_id=cat_id))


@app.route('/no_fee_list')
def no_fee_list():
    cats = []
    for cat in Categories.query.join(CatDirs).order_by(CatDirs.dir_id, CatDirs.contest_id, Categories.cat_name).all():
        cat_db = db.session.query(Categories).filter(Categories.cat_id == cat.cat_id).first()
        works = []
        for work_id in [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat_db.cat_id).all()]:
            if work_id in [w.work_id for w in WorksNoFee.query.all()]:
                work_db = db.session.query(Works).filter(Works.work_id == work_id).first()
                works.append({'work_id': work_id, 'work_name': work_db.work_name,
                              'authors': ', '.join([str(work_db.author_1_name), str(work_db.author_2_name),
                                                    str(work_db.author_3_name)]).replace(', None', '')})
        cats.append({'cat_id': cat_db.cat_id, 'cat_name': cat_db.cat_name, 'works': works})
    return render_template('works/no_fee_list.html', cats=cats)


@app.route('/drive_links')
def drive_links():
    count, categories = categories_info()
    return render_template('categories/drive_links.html', categories=categories)


@app.route('/set_report_dates', defaults={'message': None})
@app.route('/set_report_dates/<message>')
def set_report_dates(message):
    c, cats = categories_info()
    cat_dates = []
    for cat in cats:
        c_dates = {'cat_id': cat['id'], 'cat_name': cat['name']}
        if cat['id'] in [c.cat_id for c in ReportDates.query.all()]:
            dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat['id']).first()
            if dates_db.day_1:
                c_dates['day_1'] = dates_db.day_1.strftime('%Y-%m-%d')
                c_dates['d_1'] = days[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d.%m')
            else:
                c_dates['day_1'] = None
                c_dates['d_1'] = None
            if dates_db.day_2:
                c_dates['day_2'] = dates_db.day_2.strftime('%Y-%m-%d')
                c_dates['d_2'] = days[dates_db.day_2.strftime('%w')] + ', ' + dates_db.day_2.strftime('%d.%m')
            else:
                c_dates['day_2'] = None
                c_dates['d_2'] = None
            if dates_db.day_3:
                c_dates['day_3'] = dates_db.day_3.strftime('%Y-%m-%d')
                c_dates['d_3'] = days[dates_db.day_3.strftime('%w')] + ', ' + dates_db.day_3.strftime('%d.%m')
            else:
                c_dates['day_3'] = None
                c_dates['d_3'] = None
        else:
            c_dates['day_1'] = None
            c_dates['day_2'] = None
            c_dates['day_3'] = None
        cat_dates.append(c_dates)
    return render_template('online_reports/set_report_dates.html', cat_dates=cat_dates, message=message)


@app.route('/save_report_dates', methods=['POST'])
def save_report_dates():
    dates = []
    for cat_id in [c.cat_id for c in Categories.query.filter(Categories.year == curr_year).all()]:
        if str(cat_id) + '_day_1' in request.form.keys() and request.form[str(cat_id) + '_day_1'] != '':
            day_1 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_1'], '%Y-%m-%d').date()
        elif cat_id in [c.cat_id for c in ReportDates.query.all()]:
            day_1 = ReportDates.query.filter(ReportDates.cat_id == cat_id).first().day_1
        else:
            day_1 = None
        if str(cat_id) + '_day_2' in request.form.keys() and request.form[str(cat_id) + '_day_2'] != '':
            day_2 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_2'], '%Y-%m-%d').date()
        elif cat_id in [c.cat_id for c in ReportDates.query.all()]:
            day_2 = ReportDates.query.filter(ReportDates.cat_id == cat_id).first().day_2
        else:
            day_2 = None
        if str(cat_id) + '_day_3' in request.form.keys() and request.form[str(cat_id) + '_day_3'] != '':
            day_3 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_3'], '%Y-%m-%d').date()
        elif cat_id in [c.cat_id for c in ReportDates.query.all()]:
            day_3 = ReportDates.query.filter(ReportDates.cat_id == cat_id).first().day_3
        else:
            day_3 = None
        dates.append({'cat_id': cat_id, 'day_1': day_1, 'day_2': day_2, 'day_3': day_3})
    for date in dates:
        if date['cat_id'] in [c.cat_id for c in ReportDates.query.all()]:
            db.session.query(ReportDates).filter(ReportDates.cat_id == date['cat_id']
                                                 ).update({ReportDates.day_1: date['day_1'],
                                                           ReportDates.day_2: date['day_2'],
                                                           ReportDates.day_3: date['day_3']})
            db.session.commit()
        else:
            rep_d = ReportDates(date['cat_id'], date['day_1'], date['day_2'], date['day_3'])
            db.session.add(rep_d)
            db.session.commit()
            db.session.commit()
        success = 'Даты добавлены'
    return redirect(url_for('.set_report_dates', message=success))


@app.route('/reports_order/<cat_id>')
def reports_order(cat_id):
    cat_name = Categories.query.filter(Categories.cat_id == cat_id).first().cat_name
    works = get_works(cat_id, 2, 'online')
    participating = 0
    works_unordered = []
    approved_for_2 = len(works)
    for work in works.keys():
        if works[work]['appl_no']:
            participating += 1
        if works[work]['work_id'] not in [w.work_id for w in ReportOrder.query.all()]:
            works_unordered.append(works[work])
    dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
    c_dates = []
    if dates_db.day_1:
        d_1 = {'d': 'day_1', 'day': days[dates_db.day_1.strftime('%w')],
               'day_full': days_full[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d') + ' ' + \
                           months_full[dates_db.day_1.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_1':
                day_works.append(work)
        d_1['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_1['works']]:
            d_1['max_order'] = max([w['report_order'] for w in d_1['works']])
        c_dates.append(d_1)
    if dates_db.day_2:
        d_2 = {'d': 'day_2', 'day': days[dates_db.day_2.strftime('%w')],
               'day_full': days_full[dates_db.day_2.strftime('%w')] + ', ' + dates_db.day_2.strftime('%d') + ' ' + \
                           months_full[dates_db.day_2.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_2':
                day_works.append(work)
        d_2['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_2['works']]:
            d_2['max_order'] = max([w['report_order'] for w in d_2['works']])
        c_dates.append(d_2)
    if dates_db.day_3:
        d_3 = {'d': 'day_3', 'day': days[dates_db.day_3.strftime('%w')],
               'day_full': days_full[dates_db.day_3.strftime('%w')] + ', ' + dates_db.day_3.strftime('%d') + ' ' + \
                           months_full[dates_db.day_3.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_3':
                day_works.append(work)
        d_3['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_3['works']]:
            d_3['max_order'] = max([w['report_order'] for w in d_3['works']])
        c_dates.append(d_3)
    return render_template('online_reports/reports_order.html', works_unordered=works_unordered,
                           participating=participating, c_dates=c_dates, approved_for_2=approved_for_2,
                           cat_id=cat_id, cat_name=cat_name)


@app.route('/works_list_schedule/<cat_id>')
def works_list_schedule(cat_id):
    cat_name = Categories.query.filter(Categories.cat_id == cat_id).first().cat_name
    works = get_works(cat_id, 2)
    participating = 0
    works_unordered = []
    approved_for_2 = len(works)
    for work in works.keys():
        if works[work]['appl_no']:
            participating += 1
        if works[work]['work_id'] not in [w.work_id for w in ReportOrder.query.all()]:
            works_unordered.append(works[work])
    dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
    c_dates = []
    if dates_db.day_1:
        d_1 = {'d': 'day_1'}
        d_1['day'] = days[dates_db.day_1.strftime('%w')]
        d_1['day_full'] = days_full[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d') + ' ' + \
                          months_full[dates_db.day_1.strftime('%m')]
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_1':
                day_works.append(work)
        d_1['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_1['works']] != []:
            d_1['max_order'] = max([w['report_order'] for w in d_1['works']])
        c_dates.append(d_1)
    if dates_db.day_2:
        d_2 = {'d': 'day_2'}
        d_2['day'] = days[dates_db.day_2.strftime('%w')]
        d_2['day_full'] = days_full[dates_db.day_2.strftime('%w')] + ', ' + dates_db.day_2.strftime('%d') + ' ' + \
                          months_full[dates_db.day_2.strftime('%m')]
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_2':
                day_works.append(work)
        d_2['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_2['works']] != []:
            d_2['max_order'] = max([w['report_order'] for w in d_2['works']])
        c_dates.append(d_2)
    if dates_db.day_3:
        d_3 = {'d': 'day_3'}
        d_3['day'] = days[dates_db.day_3.strftime('%w')]
        d_3['day_full'] = days_full[dates_db.day_3.strftime('%w')] + ', ' + dates_db.day_3.strftime('%d') + ' ' + \
                          months_full[dates_db.day_3.strftime('%m')]
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_3':
                day_works.append(work)
        d_3['works'] = sorted(day_works, key=lambda w: w['report_order'])
        if [w['report_order'] for w in d_3['works']] != []:
            d_3['max_order'] = max([w['report_order'] for w in d_3['works']])
        c_dates.append(d_3)
    return render_template('online_reports/works_list_schedule.html', works_unordered=works_unordered,
                           participating=participating, c_dates=c_dates, approved_for_2=approved_for_2,
                           cat_id=cat_id, cat_name=cat_name)


@app.route('/work_date/<cat_id>/<work_id>/<day>/<page>')
def work_date(cat_id, work_id, day, page):
    write_work_date(cat_id=cat_id, work_id=work_id, day=day)
    return redirect(url_for('.' + page, cat_id=cat_id))


@app.route('/report_order_many/<cat_id>', methods=['POST'])
def report_order_many(cat_id):
    works = get_works(cat_id, 2)
    schedule = {}
    for work in works.values():
        if str(work['work_id']) in request.form.keys():
            schedule[work['work_id']] = request.form[str(work['work_id'])]
    for w in schedule.keys():
        write_work_date(cat_id=cat_id, work_id=w, day=schedule[w])
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/unorder/<cat_id>/<work_id>')
def unorder(cat_id, work_id):
    work_id = int(work_id)
    work_db = ReportOrder.query.filter(ReportOrder.work_id == work_id).first()
    order_deleted = work_db.order
    if work_id in [w.work_id for w in ReportOrder.query.all()]:
        work = ReportOrder.query.filter(ReportOrder.work_id == work_id).first()
        db.session.delete(work)
        db.session.query(Works).filter(Works.work_id == work_id).update({Works.reported: False})
        db.session.commit()
    for work in [w.work_id for w in ReportOrder.query.filter(ReportOrder.cat_id == int(cat_id)
                                                             ).filter(ReportOrder.report_day == work_db.report_day
                                                                      ).all() if w.order > order_deleted]:
        new = ReportOrder.query.filter(ReportOrder.work_id == work).first().order - 1
        db.session.query(ReportOrder).filter(ReportOrder.work_id == work
                                             ).update({ReportOrder.order: new})
        db.session.commit()
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/confirm_clear_schedule/<cat_id>')
def confirm_clear_schedule(cat_id):
    dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
    c_dates = []
    if dates_db.day_1:
        d_1 = {'d': 'day_1', 'day': days[dates_db.day_1.strftime('%w')],
               'day_full': days_full[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d') + ' ' +
                           months_full[dates_db.day_1.strftime('%m')]}
        c_dates.append(d_1)
    if dates_db.day_2:
        d_2 = {'d': 'day_2', 'day': days[dates_db.day_2.strftime('%w')],
               'day_full': days_full[dates_db.day_2.strftime('%w')] + ', ' + dates_db.day_2.strftime('%d') + ' ' +
                           months_full[dates_db.day_2.strftime('%m')]}
        c_dates.append(d_2)
    if dates_db.day_3:
        d_3 = {'d': 'day_3', 'day': days[dates_db.day_3.strftime('%w')],
               'day_full': days_full[dates_db.day_3.strftime('%w')] + ', ' + dates_db.day_3.strftime('%d') + ' ' +
                           months_full[dates_db.day_3.strftime('%m')]}
        c_dates.append(d_3)
    return render_template('online_reports/confirm_clear_schedule.html', cat_id=cat_id, c_dates=c_dates)


@app.route('/clear_schedule/<cat_id>/<day>')
def clear_schedule(cat_id, day):
    works_db = db.session.query(ReportOrder).filter(ReportOrder.cat_id == int(cat_id))
    works = [w.work_id for w in ReportOrder.query.filter(ReportOrder.cat_id == int(cat_id)).all()]
    for work in works:
        db.session.query(Works).filter(Works.work_id == work).update({Works.reported: False})
        db.session.commit()
    if day == 'all':
        to_delete = works_db
    else:
        to_delete = works_db.filter(ReportOrder.report_day == day)
    to_delete.delete()
    db.session.commit()
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/reorder/<cat_id>/<work_id>/<direction>')
def reorder(cat_id, work_id, direction):
    order_db = db.session.query(ReportOrder).filter(ReportOrder.work_id == work_id).first()
    order_1 = order_db.order
    day = order_db.report_day
    if direction == 'up':
        order_2 = order_1 - 1
    else:
        order_2 = order_1 + 1
    db.session.query(ReportOrder).filter(ReportOrder.cat_id == int(cat_id)
                                         ).filter(ReportOrder.report_day == day
                                                  ).filter(ReportOrder.order == order_2
                                                           ).update({ReportOrder.order: order_1})
    db.session.commit()
    db.session.query(ReportOrder).filter(ReportOrder.cat_id == int(cat_id)
                                         ).filter(ReportOrder.report_day == day
                                                  ).filter(ReportOrder.work_id == work_id
                                                           ).update({ReportOrder.order: order_2})
    db.session.commit()
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/download_schedule/<cat_id>')
def download_schedule(cat_id):
    works = get_works(cat_id, 2)
    dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
    c_dates = []
    if dates_db.day_1:
        d_1 = {'day_full': days_full[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d') + ' ' +
                           months_full[dates_db.day_1.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_1':
                day_works.append(work)
        d_1['works'] = sorted(day_works, key=lambda w: w['report_order'])
        c_dates.append(d_1)
    if dates_db.day_2:
        d_2 = {'day_full': days_full[dates_db.day_2.strftime('%w')] + ', ' + dates_db.day_2.strftime('%d') + ' ' + \
                           months_full[dates_db.day_2.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_2':
                day_works.append(work)
        d_2['works'] = sorted(day_works, key=lambda w: w['report_order'])
        c_dates.append(d_2)
    if dates_db.day_3:
        d_3 = {'day_full': days_full[dates_db.day_3.strftime('%w')] + ', ' + dates_db.day_3.strftime('%d') + ' ' + \
                           months_full[dates_db.day_3.strftime('%m')]}
        day_works = []
        for work in works.values():
            if 'report_day' in work.keys() and work['report_day'] == 'day_3':
                day_works.append(work)
        d_3['works'] = sorted(day_works, key=lambda w: w['report_order'])
        c_dates.append(d_3)
    cat_name = Categories.query.filter(Categories.cat_id == cat_id).first().cat_name
    if not os.path.exists('static/files/generated_files/schedules/' + str(curr_year)):
        os.makedirs('static/files/generated_files/schedules/' + str(curr_year))
    path = 'static/files/generated_files/schedules/' + str(curr_year) + '/' + 'Расписание ' + cat_name + '.docx'

    document = document_set()

    h = 'Расписание заседания секции' + '\n' + cat_name

    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = h
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for day in c_dates:
        document.add_heading(day['day_full'], level=1)
        for work in day['works']:
            document.add_paragraph(str(work['report_order']) + '. ' + str(work['work_id']) + ' – ' + work['work_name'] +
                                   ' – ' + work['authors'], style='Normal')

    document.save(path)
    return send_file(path, as_attachment=True)


@app.route('/add_cities')
def add_cities():
    return render_template('works/add_cities.html')


@app.route('/many_cities', methods=['POST'])
def many_cities():
    text = request.form['text']
    lines = text.split('\n')
    for line in lines:
        if line != '':
            info = line.split('\t')
            if info[0] == '':
                country = None
            else:
                country = info[0]
            if info[1] == '':
                region = None
            else:
                region = info[1]
            if info[2] == '':
                area = None
            else:
                area = info[2]
            if info[3] == '':
                city = None
            else:
                city = info[3]
            if info[4] == '':
                timeshift = None
            else:
                timeshift = int(info[4])

            if city not in [c.city for c in Cities.query.all()]:
                city_add = Cities(country, region, area, city, timeshift)
                db.session.add(city_add)
            else:
                cit = db.session.query(Cities).filter(Cities.city == city)
                if region not in [c.region for c in cit.all()]:
                    city_add = Cities(country, region, area, city, timeshift)
                    db.session.add(city_add)
                elif area not in [c.area for c in cit.all()]:
                    city_add = Cities(country, region, area, city, timeshift)
                    db.session.add(city_add)
                else:
                    db.session.query(Cities).filter(Cities.region == region
                                                    ).filter(Cities.area == area
                                                             ).filter(Cities.city == city
                                                                      ).update({Cities.msk_time_shift: timeshift})
            db.session.commit()
    return redirect(url_for('.add_cities'))


@app.route('/reported/<cat_id>/<work_id>/<action>')
def reported(cat_id, work_id, action):
    if action == 'check':
        report = True
    else:
        report = False
    db.session.query(Works).filter(Works.work_id == work_id).update({Works.reported: report})
    db.session.commit()
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/search_participant', defaults={'query': 'sear'})
@app.route('/search_participant/<query>')
def search_participant(query):
    renew_session()
    if check_access(url='/search_participant') < 3:
        return redirect(url_for('.no_access'))
    response = {'type': None, 'value': query}
    if query:
        try:
            qu = int(query)
            if len(query) == 6 and qu:
                response = {'type': 'work', 'works': work_info(int(query))}
            elif len(query) == 5:
                response = {'type': 'appl', 'value': application_2_tour(int(query))}
            else:
                response = {'type': None}
        except ValueError:
            if query == 'sear':
                response = 'search'
            elif query.lower() in [p.last_name.lower() for p in ParticipantsApplied.query.all()]:
                parts = [p.participant_id for p
                         in ParticipantsApplied.query.filter(ParticipantsApplied.last_name == query.lower()).all()]
                parts.extend([p.participant_id for p
                              in
                              ParticipantsApplied.query.filter(ParticipantsApplied.last_name == query.upper()).all()])
                parts.extend([p.participant_id for p
                              in ParticipantsApplied.query.filter(ParticipantsApplied.last_name ==
                                                                  ''.join(
                                                                      [query[0].upper(), query[1:].lower()])).all()])
                p = []
                for part in parts:
                    appl = ParticipantsApplied.query.filter(ParticipantsApplied.participant_id == part).first().appl_id
                    if appl not in [pa['id'] for pa in p]:
                        partic = application_2_tour(appl)
                        p.append(partic)
                response = {'type': 'appls', 'value': p}
            authors = [{'id': a.work_id, 'authors': [a.author_1_name, a.author_2_name, a.author_3_name]} for a in
                       Works.query.all()]
            wks = []
            for a in authors:
                if query.lower() in [a[:len(query)].lower() for a in a['authors'] if a is not None]:
                    wks.append(a['id'])
            w = [work_info(wo) for wo in wks]
            if response['type']:
                response['works'] = w
            else:
                response = {'type': 'name', 'value': w}
    else:
        response = {'type': None, 'value': query}
    return render_template('participants_and_payment/search_participant.html', response=response)


@app.route('/searching_participant', methods=['GET'])
def searching_participant():
    renew_session()
    query = request.values.get('query', str)
    return redirect(url_for('.search_participant', query=query))


@app.route('/discount_and_participation_mode/<part_id>')
def discount_and_participation_mode(part_id):
    if len(part_id) == 5:
        info = application_2_tour(int(part_id))
        info['type'] = 'application'
    elif len(part_id) == 6:
        info = work_info(int(part_id))
        info['type'] = 'work'
    else:
        return redirect(url_for('.search_participant'))
    return render_template('participants_and_payment/discount_and_participation_mode.html', info=info)


@app.route('/set_fee/<part_id>', methods=['POST'])
def set_fee(part_id):
    if len(part_id) == 6:
        part_fee = int(request.form[str(part_id) + ';fee'])
        part_format = request.form[str(part_id) + ';format']
        if int(part_id) in [p.work_id for p in Discounts.query.all()]:
            db.session.query(Discounts).filter(Discounts.work_id == int(part_id)
                                               ).update({Discounts.payment: part_fee,
                                                         Discounts.participation_format: part_format})
        else:
            discount = Discounts(None, int(part_id), part_fee, part_format)
            db.session.add(discount)
        db.session.commit()
    elif len(part_id) == 5:
        for participant in [p['id'] for p in application_2_tour(part_id)['participants']]:
            part_fee = int(request.form[str(participant) + ';fee'])
            part_format = request.form[str(participant) + ';format']
            if int(participant) in [p.participant_id for p in Discounts.query.all()]:
                db.session.query(Discounts).filter(Discounts.participant_id == int(participant)
                                                   ).update({Discounts.payment: part_fee,
                                                             Discounts.participation_format: part_format})
            else:
                discount = Discounts(int(participant), None, part_fee, part_format)
                db.session.add(discount)
            db.session.commit()
    return redirect(url_for('.search_participant', query=part_id))


@app.route('/load_statement', defaults={'success': False})
@app.route('/load_statement/<success>')
def load_statement(success):
    renew_session()
    return render_template('participants_and_payment/load_statement.html', success=success)


@app.route('/add_bank_statement', methods=['POST'])
def add_bank_statement():
    data = request.files['file'].read().decode('ptcp154')
    lines = data.split('\n')
    statement = []
    for line in lines[2:]:
        if line != '':
            sta = {name: value for name, value in zip(lines[0].split('\t'), line.split('\t'))}
            statement.append(sta)
    for payment in statement:
        if payment != {}:
            payment['date_oper'] = datetime.datetime.strptime(payment['date_oper'], '%d.%m.%Y')
            if payment['date_oper'] != datetime.datetime.now().date:
                if payment['d_c'] == 'C':
                    pay = BankStatement(date=payment['date_oper'], order_id=payment['number'],
                                        debit=float(payment['sum_val'].replace(',', '.')), credit=0,
                                        organisation=payment['plat_name'], tin=payment['plat_inn'],
                                        bic=payment['plat_bic'],
                                        bank_name=payment['plat_bank'], account=payment['plat_acc'],
                                        payment_comment=payment['text70'])
                    db.session.add(pay)
                    db.session.commit()
    return redirect(url_for('.load_statement', success=True))


@app.route('/manage_payments')
def manage_payments():
    statement = statement_info()
    return render_template('participants_and_payment/manage_payments.html', statement=statement)


@app.route('/id_payments')
def id_payments():
    statement = statement_info()
    return render_template('participants_and_payment/id_payments.html', statement=statement)


@app.route('/set_payee/<payment_id>', defaults={'payee': None})
@app.route('/set_payee/<payment_id>/<payee>')
def set_payee(payment_id, payee):
    payment = payment_info(payment_id)
    participant = {'type': None, 'participant': payee}
    if payee is not None:
        payee = payee.strip()
        try:
            payee = int(payee)
        except ValueError:
            pass
        if payee in [p.appl_id for p in ParticipantsApplied.query.all()]:
            participant = {'type': 'appl', 'participant': [application_2_tour(payee)]}
        elif payee in [w.work_id for w in Works.query.all()]:
            participant = {'type': 'work', 'works': work_info(payee)}
        else:
            if payee.lower() in [p.last_name.lower() for p in ParticipantsApplied.query.all()]:
                parts = [p.participant_id for p
                         in ParticipantsApplied.query.filter(ParticipantsApplied.last_name == payee.lower()).all()]
                parts.extend([p.participant_id for p
                              in ParticipantsApplied.query.filter(ParticipantsApplied.last_name == payee.upper()).all()])
                parts.extend([p.participant_id for p
                              in ParticipantsApplied.query.filter(ParticipantsApplied.last_name ==
                                                                  ''.join([payee[0].upper(), payee[1:].lower()])).all()])
                p = []
                for part in parts:
                    appl = ParticipantsApplied.query.filter(ParticipantsApplied.participant_id == part).first().appl_id
                    if appl not in [pa['id'] for pa in p]:
                        partic = application_2_tour(appl)
                        p.append(partic)
                participant = {'type': 'name', 'participant': p}
            authors = [{'id': a.work_id, 'authors': [a.author_1_name, a.author_2_name, a.author_3_name]} for a in
                       Works.query.all()]
            wks = []
            for a in authors:
                if payee.lower() in [a[:len(payee)].lower() for a in a['authors'] if a is not None]:
                    wks.append(a['id'])
            w = [work_info(wo) for wo in wks]
            if participant['type']:
                participant['works'] = w
            else:
                participant = {'type': 'name', 'works': w}
    else:
        participant = {'type': None, 'participant': payee}
    return render_template('participants_and_payment/set_payee.html', payment=payment, participant=participant)


@app.route('/application_payment/<payment_id>', methods=['GET'], defaults={'payee': None})
@app.route('/application_payment/<payment_id>/<payee>')
def application_payment(payment_id, payee):
    if payee is None:
        payee = request.values.get('payee', str)
    return redirect(url_for('.set_payee', payment_id=payment_id, payee=payee))


@app.route('/сheck_payees/<payment_id>/<appl>')
def сheck_payees(payment_id, appl):
    payment = payment_info(payment_id)
    application = application_2_tour(appl)
    return render_template('participants_and_payment/check_payees.html', payment=payment, appl=application)


@app.route('/set_payment/<payment_id>/<payee>', methods=['POST'])
def set_payment(payment_id, payee):
    if len(payee) == 6:
        for_work = True
        participant = int(payee)
        if str(participant) not in request.form.keys():
            if participant in [p.participant for p in PaymentRegistration.query.all()]:
                if PaymentRegistration.query.filter(PaymentRegistration.participant == participant
                                                    ).first().payment_id == int(payment_id):
                    PaymentRegistration.query.filter(PaymentRegistration.participant == participant).delete()
                    db.session.commit()
        else:
            data = request.form[str(participant)]
            if data == 'on':
                if participant not in [p.participant for p in PaymentRegistration.query.all()]:
                    payment = PaymentRegistration(payment_id, participant, for_work)
                    db.session.add(payment)
                    db.session.commit()
                else:
                    PaymentRegistration.query.filter(PaymentRegistration.participant == participant).delete()
                    db.session.commit()
        db.session.commit()
    elif len(payee) == 5:
        for_work = False
        participants = [p.participant_id for p
                        in ParticipantsApplied.query.filter(ParticipantsApplied.appl_id == int(payee)).all()]
        for participant in participants:
            if str(participant) not in request.form.keys():
                if participant in [p.participant for p in PaymentRegistration.query.all()]:
                    if PaymentRegistration.query.filter(PaymentRegistration.participant == participant
                                                        ).first().payment_id == int(payment_id):
                        PaymentRegistration.query.filter(PaymentRegistration.participant == participant).delete()
                        db.session.commit()
            else:
                data = request.form[str(participant)]
                if data == 'on':
                    if participant not in [p.participant for p in PaymentRegistration.query.all()]:
                        payment = PaymentRegistration(payment_id, participant, for_work)
                        db.session.add(payment)
                        db.session.commit()
                    else:
                        db.session.query(PaymentRegistration).filter(PaymentRegistration.participant == participant
                                                                     ).update({'payment_id': payment_id,
                                                                               'for_work': for_work})
                        db.session.commit()
    return redirect(url_for('.id_payments'))


@app.route('/delete_payment/<payment_id>')
def delete_payment(payment_id):
    BankStatement.query.filter(BankStatement.payment_id == payment_id).delete()
    db.session.commit()
    return redirect(url_for('.manage_payments'))


# БАЗА ЗНАНИЙ

@app.route('/knowledge_main')
def knowledge_main():
    if check_access(url='/knowledge_main') < 8:
        return redirect(url_for('.no_access'))
    now = datetime.datetime.now().date()
    date = days_full[now.strftime('%w')] + ', ' + now.strftime('%d') + ' ' + months_full[
        now.strftime('%m')] + ' ' + now.strftime('%Y')
    return render_template('knowledge-main.html', date=date)


@app.route('/invoice')
def invoice():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/invoice.html')


@app.route('/contact')
def contact():
    if check_access(url='/contact') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/contact.html')


@app.route('/email')
def email():
    if check_access(url='/email') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/email.html')


@app.route('/email_schedule')
def email_schedule():
    if check_access(url='/email_schedule') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/email_schedule.html')


@app.route('/phone_schedule')
def phone_schedule():
    if check_access(url='/phone_schedule') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/phone_schedule.html')


@app.route('/working_programme')
def working_programme():
    if check_access(url='/working_programme') < 5:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/working_programme.html')


@app.route('/online_additional_contest')
def online_additional_contest():
    if check_access(url='/online_additional_contest') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/online_additional_contest.html')


@app.route('/consult_works')
def consult_works():
    if check_access(url='/consult_works') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/consult_works.html')


@app.route('/vernadsky_olympiade')
def vernadsky_olympiade():
    if check_access(url='/vernadsky_olympiade') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/vernadsky_olympiade.html')


@app.route('/general_info')
def general_info():
    if check_access(url='/general_info') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/general_info.html')


@app.route('/frequent_actions')
def frequent_actions():
    if check_access(url='/frequent_actions') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/frequent_actions.html')


@app.route('/registration_on_site')
def registration_on_site():
    if check_access(url='/registration_on_site') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/registration_on_site.html')


@app.route('/attach_work')
def attach_work():
    if check_access(url='/attach_work') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/attach_work.html')


@app.route('/approve_for_2_tour')
def approve_for_2_tour():
    if check_access(url='/approve_for_2_tour') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/approve_for_2_tour.html')


@app.route('/approve_for_1_tour')
def approve_for_1_tour():
    if check_access(url='/approve_for_1_tour') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/approve_for_1_tour.html')


# ОРГКОМИТЕТ

# @app.route('/contact_team')
# def contact_team():
#     if check_access(url='/invoice') < 8:
#         return redirect(url_for('.no_access'))
#     return render_template('knowledge/org/contact_team.html')

# s
@app.route('/bank_details')
def bank_details():
    if check_access(url='/bank_details') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/bank_details.html')


@app.route('/banks_and_payments')
def banks_and_payments():
    if check_access(url='/banks_and_payments') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/banks_and_payments.html')


@app.route('/guarantee_letters')
def guarantee_letters():
    if check_access(url='/guarantee_letters') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/guarantee_letters.html')


@app.route('/creativity_contest')
def creativity_contest():
    if check_access(url='/creativity_contest') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/creativity_contest.html')


@app.route('/session_shedule')
def session_shedule():
    if check_access(url='/session_shedule') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/session_shedule.html')


@app.route('/apply_2_tour')
def apply_2_tour():
    if check_access(url='/apply_2_tour') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_2_tour.html')


@app.route('/programme_grid')
def programme_grid():
    if check_access(url='/programme_grid') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/programme_grid.html')


@app.route('/feedback')
def feedback():
    if check_access(url='/feedback') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/feedback.html')


@app.route('/movement_projects')
def movement_projects():
    if check_access(url='/movement_projects') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/movement_projects.html')


@app.route('/working_resources')
def working_resources():
    if check_access(url='/working_resources') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/working_resources.html')


@app.route('/apply_for_participant')
def apply_for_participant():
    if check_access(url='/apply_for_participant') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_for_participant.html')


@app.route('/contest_calendar')
def contest_calendar():
    if check_access(url='/contest_calendar') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/contest_calendar.html')


@app.route('/apply_1_tour')
def apply_1_tour():
    if check_access(url='/apply_1_tour') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_1_tour.html')


@app.route('/faq')
def faq():
    if check_access(url='/faq') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/FAQ.html')


@app.route('/tour_2')
def tour_2():
    if check_access(url='/tour_2') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/tour_2.html')


@app.route('/secretary_knowledge')
def secretary_knowledge():
    if check_access(url='/secretary_knowledge') < 5:
        return redirect(url_for('.no_access'))
    return render_template('secretary_knowledge.html')


if __name__ == '__main__':
    app.run(debug=False)
