# -*- coding: utf-8 -*-

from dotenv import load_dotenv
import os
import requests
import logging
import sched, time, threading


scheduler = sched.scheduler(time.monotonic, time.sleep)

logging.basicConfig(
    filename='logfile.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
domain = os.getenv('GITLAB_DOMAIN')
project_id = os.getenv('GITLAB_PROJECT_NUMBER')
INTERVAL_CONST = int(os.getenv('INTERVAL'))

URL = f"https://{domain}/api/v4/projects/{project_id}/merge_requests"

acess_token = os.getenv('GITLAB_ACCESS_TOKEN', 'none')#Если нет значения, то пишем none
headers = {}
#Если используеться acess_token, то чтобы получить доступ к приватному репозиторию нужно добавить заголовок в запрос
if acess_token != "none":
    headers = {
        'PRIVATE-TOKEN': acess_token
    }

from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler
tg_token = os.getenv('TG_BOT_TOKEN')
bot = Bot(token=tg_token)
chats = []

def gitlab_API_request():
    response = None
    text = []
    try:
        #Получаем данные через API gitlab
        response = requests.get(URL, headers = headers)
    except Exception as e:
        logger.error(e)
        print(e)
        text.append("Что-то пошло не так при доступе к gitlab. Проверьте соединение с сервером.")
        return text
    #Преобразуем данные для дальнейшего использования
    data = response.json() #Здесь получаем список из объектов json
    if not data:
        return None

    for item in data:
        if item['state'] == 'opened':
            text.append(f"""\
Напоминание! У вас открыт MergeRequest в проекте по адресу {item['web_url']}
Title: {item['title']}
Source branch: {item['source_branch']}
Author: {item['author']['username']}""")

    return text

def start(update: Update, context):
#При старте бота подписываем чат пользователя для отправления уведомлений
    user = update.effective_user
#можно использовать переменную окружения для определения первого запуска бота.
    if os.getenv('IS_ADMIN_EXIST', 'none') == "none":
        text = f"""\
Здраствуйте, {user.full_name}!
Вы первый пользователь бота. Теперь вы будете получать оповещения о проекте, который был указан при запуске бота.
/help - для вывода списка команд"""
        os.environ["IS_ADMIN_EXIST"] = "yes"
        chats.append(update.message.chat_id)
    else:
        text = "Теперь Вы подписаны на рассылку напоминаний."
        #добавляем id чата в список
        chats.append(update.message.chat_id)
    update.message.reply_text(text)

def send_to_all(message):
#Для каждого пользователя из chats (в том числе и для группы) отправляем сообщение через бот
    for id in chats:
        try:
            bot.send_message(id, text=message)
        except Exception as e:
            logger.error(e)
            print(e)

def send_notification():
#Получаем сообщения и отправляем всем подписавшимся пользователям
    messages = gitlab_API_request()
    if not messages:
        pass
    else:
        for message in messages:
            send_to_all(message)
            time.sleep(5)



def scheduler_tool(exec_interval, func, scheduled_event=None):
#Добавляем и запускаем задачу
    if scheduled_event:
        scheduler.cancel(scheduled_event)
    new_event = scheduler.enter(exec_interval, 1, func)
    scheduler.run(blocking=False)
    return new_event


def scheduler_loop(event):
#В цикле запускаем отсчет до отправки сообщений в интервале INTERVAL_CONST
    while os.getenv('IS_ADMIN_EXIST', 'none') == "none":
        time.sleep(5)
    while True:
        scheduler_tool(float(INTERVAL_CONST), send_notification)
        for i in range(0,INTERVAL_CONST,5):
            time.sleep(5)
            if event.is_set():
                return
        

def helpCommand(update: Update, context):
    text = """\
/add_poject - добавить проект для мониторинга merge requests (не реализовано)
/list_projects - вывести список отслеживаемых проектов (не реализовано)
/del_poject - удалить проект из списка (не реализовано)"""
    update.message.reply_text(text)

def main():
    updater = Updater(tg_token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", helpCommand))

    event = threading.Event()
    t = threading.Thread(target=scheduler_loop, args=(event,))
    t.start()
    updater.start_polling()
    # Останавливаем бота и фоновый таймер при нажатии Ctrl+C
    updater.idle()
    event.set()
    t.join()


if __name__ == '__main__':
    main()