import os
import base64
# from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build
# import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']
SERVICE_ACCOUNT_FILE = 'credentials.json'

def get_service():
    # creds = None
    # Если существует токен, загружаем его
    # if os.path.exists('token.json'):
    #     creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # Если нет токена или он недействителен, запускаем авторизацию
    # if not creds or not creds.valid:
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        # flow = InstalledAppFlow.from_client_secrets_file('secret.json', SCOPES)
        # secr = flow.run_local_server(port=0)
        # # Сохраняем токен для будущих запусков
        # with open('token.json', 'w') as token:
        #     token.write(secr)
    service = build('gmail', 'v1', credentials=creds)
    return service

def create_message_text(sender, to, subject, body):
    """Создаёт простое текстовое письмо и кодирует его в Base64."""
    message = MIMEText(body, 'plain', 'utf-8')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def create_message_html(sender, to, subject, html_body):
    """Создаёт HTML-письмо и кодирует его в Base64."""
    message = MIMEText(html_body, 'html', 'utf-8')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_message(service, user_id, message):
    """Отправляет сообщение через Gmail API."""
    try:
        sent_message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f'Message Id: {sent_message["id"]}')
        return sent_message
    except Exception as e:
        print(f'An error occurred: {e}')
        return None

def create_message_with_attachment(sender, to, subject, html_body, attachments=None):
    """
    Создаёт письмо с HTML-телом и вложениями.f
    """
    if attachments is None:
        attachments = []

    # Создаём "контейнер" письма
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    # Добавляем HTML-текст
    msg_alternative = MIMEMultipart('alternative')
    message.attach(msg_alternative)
    part_html = MIMEText(html_body, 'html', 'utf-8')
    msg_alternative.attach(part_html)

    # Прикрепляем файлы
    for attach in attachments:
        mime_part = MIMEBase('application', 'octet-stream')
        mime_part.set_payload(attach['data'])
        encoders.encode_base64(mime_part)
        mime_part.add_header('Content-Disposition', 'attachment', filename=attach['filename'])
        message.attach(mime_part)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def create_message_with_attachments(sender, to, subject, html_body, attachments, bcc=None, reply_to=None):
    """
    Создаёт письмо (HTML) с вложениями.

    :param sender: Адрес отправителя (например, "team@vernadsky.info")
    :param to: Адрес получателя (строка)
    :param subject: Тема письма
    :param html_body: HTML-содержимое письма
    :param attachments: список словарей вида:
        [
          {
            'filename': 'diploma.pdf',
            'content_type': 'application/pdf',
            'data': b'байтовые_данные_файла'
          },
          ...
        ]
    :param bcc: скрытая копия (строка), по желанию
    :param reply_to: адрес для "Reply-To" (строка), по желанию
    :return: Словарь {'raw': ...} для передачи в send_message(service, 'me', ...)
    """
    # Создаём "контейнер" письма
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    if bcc:
        message['bcc'] = bcc
    if reply_to:
        message['reply-to'] = reply_to

    # Добавляем HTML-текст
    msg_alternative = MIMEMultipart('alternative')
    message.attach(msg_alternative)
    part_html = MIMEText(html_body, 'html', 'utf-8')
    msg_alternative.attach(part_html)

    # Прикрепляем файлы
    for attach in attachments:
        mime_part = MIMEBase('application', 'octet-stream')
        mime_part.set_payload(attach['data'])
        encoders.encode_base64(mime_part)
        mime_part.add_header(
            'Content-Disposition',
            f'attachment; filename="{attach["filename"]}"'
        )
        message.attach(mime_part)

    # Кодируем всё это в Base64, чтобы Gmail API смог принять
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

if __name__ == '__main__':
    service = get_service()
    message = create_message_text(
        sender="team@vernadsky.info",      # замени на свой Gmail
        to="shelexovivan@gmail.com",           # замени на email получателя
        subject="Тестовое письмо",
        body="Привет!"
    )
    send_message(service, "me", message)
