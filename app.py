import json

from flask import Flask
from flask import render_template, request, redirect, url_for, session
from models import *
import mail_data
import re
import datetime
import os
from cryptography.fernet import Fernet
from flask_mail import Mail, Message
from sqlalchemy import update, delete
import asyncio
from flask import send_file

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
    link = 'http://nleontovich.pythonanywhere.com/approve/' + str(user_id)
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
    if user_db.last_login:
        user_info['last_login'] = user_db.last_login.strftime('%d.%m.%Y %H:%M:%S')
    if user in [u.secretary_id for u in CatSecretaries.query.all()]:
        user_info['secretary'] = True
        user_info['cat_id'] = [c.cat_id for c in db.session.query(CatSecretaries).filter(
            CatSecretaries.secretary_id == user).all()]
    else:
        user_info['cat_id'] = []
    if user in [s.user_id for s in SupervisorUser.query.all()]:
        user_info['supervisor_id'] = SupervisorUser.query.filter(SupervisorUser.user_id == user).first().supervisor_id
    return user_info


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
        if same_email is None:
            user_db.email = user_info['email']
        elif session['user_id'] in same_email:
            if same_email.remove(session['user_id']) is None:
                user_db.email = user_info['email']
        else:
            return 'email'
        # Проверка существования другого пользователя с новым введенным телефоном
        same_tel = [user.user_id for user in db.session.query(Users).filter(Users.email == user_info['tel']).all()]
        if same_tel is None:
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
        if cat_info['supervisor'] is not None and cat_info['supervisor'] !='':
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
                sup = db.session.query(Supervisors).filter(Supervisors.last_name == sup_name[0] and
                                                           Supervisors.first_name == sup_name[1] and
                                                           Supervisors.patronymic == sup_name[2]).first()
                db_cat = db.session.query(Categories).filter(Categories.cat_id == cat_info['cat_id']).first()
            else:
                sup = None
        if sup is not None:
            cat = CatSupervisors(db_cat.cat_id, sup.supervisor_id)
            db.session.add(cat)
    db.session.commit()
    return True


def one_category(categ):
    cat = dict()
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
    if db.session.query(CatSupervisors).filter(CatSupervisors.cat_id == cat_id).first():
        sup_id = db.session.query(CatSupervisors).filter(CatSupervisors.cat_id == cat_id).first().supervisor_id
        sup = db.session.query(Supervisors).filter(Supervisors.supervisor_id == sup_id).first()
        cat['supervisor_id'] = sup.supervisor_id
        cat['supervisor'] = sup.last_name + ' ' + sup.first_name + ' ' + sup.patronymic
        cat['supervisor_email'] = sup.email
        cat['supervisor_tel'] = sup.tel
    if db.session.query(CatSecretaries).filter(CatSecretaries.cat_id == cat_id).first():
        sec_id = db.session.query(CatSecretaries).filter(CatSecretaries.cat_id == cat_id).first().secretary_id
        user = db.session.query(Users).filter(Users.user_id == sec_id).first()
        cat['secretary_id'] = user.user_id
        cat['secretary'] = user.last_name + ' ' + user.first_name
        cat['secretary_full'] = user.last_name + ' ' + user.first_name + ' ' + user.patronymic
        cat['secretary_email'] = user.email
        cat['secretary_tel'] = user.tel
    if cat_id in [cat.cat_id for cat in ReportDates.query.all()]:
        dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat['id']).first()
        dates = []
        if dates_db.day_1:
            dates.append(days[dates_db.day_1.strftime('%w')] + ' ' + dates_db.day_1.strftime('%d') + ' ' +
                         months[dates_db.day_1.strftime('%m')])
        if dates_db.day_2:
            dates.append(days[dates_db.day_2.strftime('%w')] + ' ' + dates_db.day_2.strftime('%d') + ' ' +
                         months[dates_db.day_2.strftime('%m')])
        if dates_db.day_3:
            dates.append(days[dates_db.day_3.strftime('%w')] + ' ' + dates_db.day_3.strftime('%d') + ' ' +
                         months[dates_db.day_3.strftime('%m')])
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
        applications = db.session.query(Application).filter(Application.user_id == user).order_by(Application.year)
    elif info_type == 'year':
        applications = db.session.query(Application).join(Users).filter(Application.year == year).order_by(
            Users.last_name)
    elif info_type == 'user-year':
        applications = db.session.query(Application).filter(Application.user_id == user and Application.year == year)
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
    if work['timeshift']:
        if work['timeshift'] >= 0:
            work['timeshift'] = '+' + str(work['timeshift'])
        else:
            work['timeshift'] = str(work['timeshift'])
    if work_id in [w.work_id for w in RevAnalysis.query.all()]:
        if len(RevAnalysis.query.filter(RevAnalysis.work_id == work_id).all()) == len(RevCriteria.query.all()):
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
    return work


def get_works(cat_id, status):
    # в status пишется, работы, допущенные до какого тура, мы ищем
    if status == 1:
        stat = ['Допущена до 1-го тура', 'Направлена на рецензирование', 'Отрецензирована',
                'Окончила 1-й тур. Не допущена до 2-го тура', 'Допущена до 2-го тура']
    elif status == 2:
        stat = ['Допущена до 2-го тура']
    works = dict()
    cat_works = db.session.query(WorkCategories).filter(WorkCategories.cat_id == cat_id
                                                        ).order_by(WorkCategories.work_id).all()
    for work in cat_works:
        work_db = db.session.query(Works).filter(Works.work_id == work.work_id).first()
        w_no = work_db.work_id
        status_id = WorkStatuses.query.filter(WorkStatuses.work_id == w_no).first().status_id
        if ParticipationStatuses.query.filter(ParticipationStatuses.status_id == status_id).first().status_name \
                in stat:
            works[w_no] = work_info(w_no)
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
                                      ).join(CatDirs).join(Directions
                                                           ).join(Contests).order_by(CatDirs.dir_id, CatDirs.contest_id,
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


def get_analysis(work_id):
    rk = 0
    analysis = dict()
    analysis_db = db.session.query(RevAnalysis).filter(RevAnalysis.work_id == work_id).all()
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
        cat_works = get_works(cat.cat_id, 1)
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
    ana_nums = dict()
    all_stats = dict()
    all_stats['regionals'] = 0
    all_stats['analysed'] = 0
    regions = []
    for key in cats.keys():
        ana_nums[key] = dict()
        ana_nums[key]['cat_id'] = cats[key]['id']
        ana_nums[key]['cat_name'] = cats[key]['name']
        ana_nums[key]['analysed'] = 0
        cat_works = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cats[key]['id'])]
        ana_nums[key]['regional_applied'] = 0
        for work in cat_works:
            work_db = db.session.query(Works).filter(Works.work_id == work).first()
            status_id = WorkStatuses.query.filter(WorkStatuses.work_id == work_db.work_id).first().status_id
            status = ParticipationStatuses.query.filter(ParticipationStatuses.status_id == status_id
                                                        ).first().status_name
            if work_db.reg_tour is not None and status != 'Не прошла на конкурс':
                ana_nums[key]['regional_applied'] += 1
                all_stats['regionals'] += 1
                regions.append(work_db.reg_tour)
                if work_info(work)['analysis'] is True:
                    ana_nums[key]['analysed'] += 1
                    all_stats['analysed'] += 1
        ana_nums[key]['left'] = ana_nums[key]['regional_applied'] - ana_nums[key]['analysed']
    all_stats['left'] = all_stats['regionals'] - all_stats['analysed']
    all_stats['regions'] = len(set(regions))
    return ana_nums, all_stats


def check_analysis(cat_id):
    works = get_works(cat_id, 1)
    for key in works:
        if works[key]['reg_tour'] is not None \
                and ('analysis' not in works[key].keys()
                     or works[key]['analysis'] is False):
            return True
    return False


def no_fee_nums():
    cats_no, cats = categories_info()
    total = 0
    for cat in cats.values():
        works = get_works_no_fee(cat['id'])
        cat['works'] = ', '.join([str(w) for w in works.keys()])
        cat['works_no'] = len(works)
        total += cat['works_no']
    return total, cats


def check_order(cat_works):
    for d in [d.report_day for d in ReportOrder.query.all()]:
        if [w.work_id for w in ReportOrder.query.filter(ReportOrder.report_day == d).all()]:
            prev_order = 0
            wo = {}
            order_dict = {}
            for work in cat_works:
                if work in [w.work_id for w in ReportOrder.query.filter(ReportOrder.report_day == d
                                                                        ).order_by(ReportOrder.order).all()]:
                    order = db.session.query(ReportOrder).filter(ReportOrder.work_id == work,
                                                                 ReportOrder.report_day == d).first().order
                    wo[work] = order
                    order_dict = {w: o for w, o in sorted(wo.items(), key=lambda item: item[1])}
            if order_dict != {}:
                for w, o in order_dict.items():
                    prev_order += 1
                    if o != prev_order:
                        db.session.query(ReportOrder).filter(ReportOrder.work_id == w
                                                             ).update({
                            ReportOrder.order: prev_order})
                        db.session.commit()


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
    with_secretary = db.session.query(CatSecretaries).count()
    no_secr = cats_count - with_secretary + 34
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
    relevant.append(21) #Добавление Свешниковой
    renew_session()
    return render_template('supervisors/supervisors.html', supervisors=sups, access=check_access(url='/supervisors'),
                           relevant=relevant)


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
    sup_id = request.form['supervisor_id']
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
    if session['user_id'] in [a.user_id for a in Application.query.all()]:
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
        cat_sec = Application(appl_id, session['user_id'], curr_year, role, category_1, category_2, category_3, any_category,
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
    appl_db = db.session.query(Application).filter(Application.user_id == user and Application.year == year).first()
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
        except Exception:
            pass
        if query in [u.email for u in Users.query.all()]:
            for u in Users.query.filter(Users.email == query).order_by(Users.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif tel in [u.tel for u in Users.query.all()]:
            for u in Users.query.filter(Users.tel == tel).order_by(Users.user_id.desc()).all():
                users[u.user_id] = get_user_info(u.user_id)
        elif query.lower() in [u.last_name.lower() for u in Users.query.all()]:
            q = ''.join([query[0].upper()] + [s.lower() for s in query[1:]])
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
                                          and CatSecretaries.cat_id == cat_id).first()
    db.session.delete(cat_sec)
    db.session.commit()
    return redirect(url_for('.user_page', user=user_id))


@app.route('/category_page/<cat_id>', defaults={'errors': None})
@app.route('/category_page/<cat_id>/<errors>')
def category_page(cat_id, errors):
    category = one_category(db.session.query(Categories).filter(Categories.cat_id == cat_id).first())
    renew_session()
    need_analysis = check_analysis(cat_id)
    works_no_fee = get_works_no_fee(cat_id)
    show_top_100 = False
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
                                                   and SupervisorUser.supervisor_id == superv).first()
            db.session.delete(user_sup)
            db.session.commit()
    return redirect(url_for('.user_page', user=user_id))


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
            criterion_id = RevCriteria.query.filter(RevCriteria.criterion_name == criterion).first().criterion_id
            value_id = RevCritValues.query.order_by(RevCritValues.value_id.desc()
                                                    ).filter(RevCritValues.value_name == value).first().value_id
            crit_val = CriteriaValues(criterion_id, value_id)
            db.session.add(crit_val)
            db.session.commit()
    return redirect(url_for('.analysis_criteria'))


@app.route('/analysis_works/<cat_id>')
def analysis_works(cat_id):
    renew_session()
    if check_access(url='/analysis_works/' + cat_id) < 5:
        return redirect(url_for('.no_access'))
    works = get_works(cat_id, 1)
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
    return render_template('rev_analysis/review_analysis.html', work=work, analysis=analysis, criteria=criteria,
                           pre_ana=pre_ana)


@app.route('/pre_analysis/<work_id>')
def pre_analysis(work_id):
    renew_session()
    if check_access(url='/pre_analysis' + work_id) < 6:
        return redirect(url_for('.no_access'))
    work = work_info(work_id)
    pre = get_pre_analysis(int(work_id))
    return render_template('/rev_analysis/pre_analysis.html', work=work, pre_ana=pre)


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
    if work_id in [w.work_id for w in PreAnalysis.query.all()]:
        db.session.query(PreAnalysis).filter(PreAnalysis.work_id == int(work_id)).update(
            {PreAnalysis.good_work: good_work, PreAnalysis.research: research,
             PreAnalysis.has_review: has_review, PreAnalysis.rev_type: rev_type, PreAnalysis.pushed: pushed})
        db.session.commit()
    else:
        pre_ana = PreAnalysis(work_id, good_work, research, has_review, rev_type, pushed, None, None)
        db.session.add(pre_ana)
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


@app.route('/analysis_form/<work_id>')
def analysis_form(work_id):
    renew_session()
    if check_access(url='/analysis_form' + work_id) < 6:
        return redirect(url_for('.no_access'))
    criteria = get_criteria(curr_year)
    work = work_info(work_id)
    rk, analysis = get_analysis(int(work_id))
    return render_template('/rev_analysis/analysis_form.html', criteria=criteria, work=work, analysis=analysis)


@app.route('/write_analysis', methods=['POST'])
def write_analysis():
    renew_session()
    work_id = int(request.form['work_id'])
    criteria_ids = [criterion.criterion_id for criterion in RevCriteria.query.all()]
    for criterion_id in criteria_ids:
        if str(criterion_id) in request.form.keys():
            value = int(request.form[str(criterion_id)])
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
    cat_id = WorkCategories.query.filter(WorkCategories.work_id == work_id).first().cat_id
    return redirect(url_for('.analysis_works', cat_id=cat_id))


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
        work_id = int(n['number'])
        work_site_id = int(n['id'])
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
            edited = True
        else:
            work_status = WorkStatuses(work_id, status_id)
            db.session.add(work_status)
        db.session.commit()
        if work_id in [w.work_id for w in WorkCategories.query.all()]:
            if not cat_id:
                work_cat = db.session.query(WorkCategories).filter(WorkCategories.work_id == work_id).first()
                db.session.delete(work_cat)
                edited = True
            else:
                db.session.query(WorkCategories).filter(WorkCategories.work_id == work_id
                                                        ).update({WorkCategories.cat_id: cat_id})
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
    for n in w:
        works = [{'work': int(a['number']), 'appl': int(n['id'])} for a in n['works']]
        works_applied.extend(works)
    for work in works_applied:
        if work['work'] in [wo.work_id for wo in Applications2Tour.query.all()]:
            db.session.query(Applications2Tour).filter(Applications2Tour.work_id == work['work']
                                                       ).first().update({Applications2Tour.appl_no: work['appl'],
                                                                         Applications2Tour.arrived: work['appl']})
            db.session.commit()
        else:
            wo = Works.query.filter(Works.work_id == work['work']).first().work_id
            appl = Applications2Tour(wo, work['appl'], False)
            db.session.add(appl)
            db.session.commit()
    return redirect(url_for('.applications_2_tour'))


@app.route('/top_100')
def top_100():
    if check_access(url='/top_100') < 5:
        return redirect(url_for('.no_access'))
    total, no_fee = no_fee_nums()
    return render_template('works/top_100.html', no_fee=no_fee, total=total)


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
        except Exception:
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
    for cat in cats.values():
        c_dates = {'cat_id': cat['id'], 'cat_name': cat['name']}
        if cat['id'] in [c.cat_id for c in ReportDates.query.all()]:
            dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat['id']).first()
            if dates_db.day_1:
                c_dates['day_1'] = dates_db.day_1.strftime('%Y-%m-%d')
            else:
                c_dates['day_1'] = None
            if dates_db.day_2:
                c_dates['day_2'] = dates_db.day_2.strftime('%Y-%m-%d')
            else:
                c_dates['day_2'] = None
            if dates_db.day_3:
                c_dates['day_3'] = dates_db.day_3.strftime('%Y-%m-%d')
            else:
                c_dates['day_3'] = None
        else:
            c_dates['day_1'] = None
            c_dates['day_2'] = None
            c_dates['day_3'] = None
        cat_dates.append(c_dates)
    return render_template('online_reports/set_report_dates.html', cat_dates=cat_dates, message=message)


@app.route('/save_report_dates', methods=['POST'])
def save_report_dates():
    dates = []
    for cat_id in [c.cat_id for c in Categories.query.all()]:
        if str(cat_id) + '_day_1' in request.form.keys() and request.form[str(cat_id) + '_day_1'] != '':
            day_1 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_1'], '%Y-%m-%d').date()
        else:
            day_1 = None
        if str(cat_id) + '_day_2' in request.form.keys() and request.form[str(cat_id) + '_day_2'] != '':
            day_2 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_2'], '%Y-%m-%d').date()
        else:
            day_2 = None
        if str(cat_id) + '_day_3' in request.form.keys() and request.form[str(cat_id) + '_day_3'] != '':
            day_3 = datetime.datetime.strptime(request.form[str(cat_id) + '_day_3'], '%Y-%m-%d').date()
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

        success = 'Даты добавлены'
    return redirect(url_for('.set_report_dates', message=success))


@app.route('/reports_order/<cat_id>')
def reports_order(cat_id):
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
    work_id = int(work_id)
    cat_works = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat_id).all()]
    last_order = 1
    for work in cat_works:
        if work in [w.work_id for w in ReportOrder.query.filter(ReportOrder.report_day == day).all()]:
            order = db.session.query(ReportOrder).filter(ReportOrder.work_id == work,
                                                         ReportOrder.report_day == day).first().order
            if order >= last_order:
                last_order = order + 1
    if work_id in [w.work_id for w in ReportOrder.query.all()]:
        db.session.query(ReportOrder).filter(ReportOrder.work_id == work_id
                                             ).update({ReportOrder.report_day: day,
                                                       ReportOrder.order: last_order})
        db.session.commit()
    else:
        o = ReportOrder(work_id, day, last_order)
        db.session.add(o)
        db.session.commit()
    check_order(cat_works)
    return redirect(url_for('.' + page, cat_id=cat_id))


@app.route('/unorder/<cat_id>/<work_id>')
def unorder(cat_id, work_id):
    work_id = int(work_id)
    if work_id in [w.work_id for w in ReportOrder.query.all()]:
        work = ReportOrder.query.filter(ReportOrder.work_id == work_id).first()
        db.session.delete(work)
        db.session.commit()
    cat_works = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat_id).all()]
    check_order(cat_works)
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
    db.session.query(ReportOrder).filter(ReportOrder.report_day == day
                                         ).filter(ReportOrder.order == order_2
                                                  ).update({ReportOrder.order: order_1})
    db.session.commit()
    db.session.query(ReportOrder).filter(ReportOrder.report_day == day
                                         ).filter(ReportOrder.work_id == work_id
                                                  ).update({ReportOrder.order: order_2})
    db.session.commit()
    cat_works = [w.work_id for w in WorkCategories.query.filter(WorkCategories.cat_id == cat_id).all()]
    check_order(cat_works)
    return redirect(url_for('.reports_order', cat_id=cat_id))


@app.route('/download_schedule/<cat_id>')
def download_schedule(cat_id):
    works = get_works(cat_id, 2)
    dates_db = db.session.query(ReportDates).filter(ReportDates.cat_id == cat_id).first()
    c_dates = []
    if dates_db.day_1:
        d_1 = {'day_full': days_full[dates_db.day_1.strftime('%w')] + ', ' + dates_db.day_1.strftime('%d') + ' ' + \
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
    lines = []
    for day in c_dates:
        lines.append(day['day_full'])
        for work in day['works']:
            lines.append(str(work['report_order']) + '\t' + str(work['work_id']) + ' - ' + work['work_name']) \
                # + ' - ' + work['authors'])
        lines.append('')
    cat_name = Categories.query.filter(Categories.cat_id == cat_id).first().cat_name
    path = 'static/files/schedules/' + str(curr_year) + '/' + 'Расписание ' + cat_name + '.txt'
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines([line + '\n' for line in lines])
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


# БАЗА ЗНАНИЙ

@app.route('/knowledge_main')
def knowledge_main():
    if check_access(url='/invoice') < 3:
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
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/contact.html')


@app.route('/email')
def email():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/email.html')


@app.route('/email_schedule')
def email_schedule():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/email_schedule.html')


@app.route('/phone_schedule')
def phone_schedule():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/phone_schedule.html')


@app.route('/working_programme')
def working_programme():
    if check_access(url='/invoice') < 5:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/working_programme.html')


@app.route('/online_additional_contest')
def online_additional_contest():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/online_additional_contest.html')


@app.route('/consult_works')
def consult_works():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/consult_works.html')


@app.route('/vernadsky_olympiade')
def vernadsky_olympiade():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/vernadsky_olympiade.html')


@app.route('/general_info')
def general_info():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/general_info.html')


@app.route('/frequent_actions')
def frequent_actions():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/frequent_actions.html')


@app.route('/registration_on_site')
def registration_on_site():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/registration_on_site.html')


@app.route('/attach_work')
def attach_work():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/attach_work.html')


@app.route('/approve_for_2_tour')
def approve_for_2_tour():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/approve_for_2_tour.html')


@app.route('/approve_for_1_tour')
def approve_for_1_tour():
    if check_access(url='/invoice') < 8:
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
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/bank_details.html')


@app.route('/banks_and_payments')
def banks_and_payments():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/banks_and_payments.html')


@app.route('/guarantee_letters')
def guarantee_letters():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/guarantee_letters.html')


@app.route('/creativity_contest')
def creativity_contest():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/creativity_contest.html')


@app.route('/session_shedule')
def session_shedule():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/session_shedule.html')


@app.route('/apply_2_tour')
def apply_2_tour():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_2_tour.html')


@app.route('/programme_grid')
def programme_grid():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/programme_grid.html')


@app.route('/feedback')
def feedback():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/feedback.html')


@app.route('/movement_projects')
def movement_projects():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/movement_projects.html')


@app.route('/working_resources')
def working_resources():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/working_resources.html')


@app.route('/apply_for_participant')
def apply_for_participant():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_for_participant.html')


@app.route('/contest_calendar')
def contest_calendar():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/contest_calendar.html')


@app.route('/apply_1_tour')
def apply_1_tour():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/apply_1_tour.html')


@app.route('/faq')
def faq():
    if check_access(url='/invoice') < 3:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/FAQ.html')


@app.route('/tour_2')
def tour_2():
    if check_access(url='/invoice') < 8:
        return redirect(url_for('.no_access'))
    return render_template('knowledge/org/tour_2.html')


if __name__ == '__main__':
    app.run(debug=False)

