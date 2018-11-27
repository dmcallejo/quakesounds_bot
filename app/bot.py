import telebot
import requests
import string
import telebot.types as types
import argparse
import json
import unidecode
import random
from time import sleep
from app.persistence import *
import app.logger as logger
import os
import PrettyUptime
import webhook

BOT_NAME = 'QuakeSounds_Bot'
logger.set_logger(BOT_NAME)
LOG = logger.get_logger()
REMOVE_CHARS = string.punctuation + string.whitespace
TELEGRAM_INLINE_MAX_RESULTS = 48

_ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
_ENV_TELEGRAM_USER_ALIAS = "TELEGRAM_USER_ALIAS"
_ENV_SQLITE_FILE = 'SQLITE_FILE'
_ENV_DATABASE_NAME = 'DATABASE_NAME'
_ENV_MYSQL_HOST = 'MYSQL_HOST'
_ENV_MYSQL_PORT = 'MYSQL_PORT'
_ENV_MYSQL_USER = 'MYSQL_USER'
_ENV_MYSQL_PASSWORD = 'MYSQL_PASSWORD'
_ENV_DATA_JSON = 'DATA_JSON'
_ENV_LOGGING_FILE = 'LOGFILE'
_ENV_WEBHOOK_HOST = 'WEBHOOK_HOST'
_ENV_WEBHOOK_PORT = 'WEBHOOK_PORT'
_ENV_WEBHOOK_LISTEN = 'WEBHOOK_LISTEN'
_ENV_WEBHOOK_LISTEN_PORT = 'WEBHOOK_LISTEN_PORT'


parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbosity", help="Defines log verbosity",
                    choices=['CRITICAL', 'ERROR', 'WARN', 'INFO', 'DEBUG'], default='INFO')
parser.add_argument("-b", "--bucket", help="Bucket or url where audios are stored",
                    default='https://github.com/dmcallejo/quakesounds_bot/raw/master/quakesounds/')
parser.add_argument("--sqlite", help="SQLite file path")
parser.add_argument("--database", type=str, help="Database name", default=BOT_NAME.lower())
parser.add_argument("--mysql-host", type=str, help="mysql host")
parser.add_argument("--mysql-port", type=str, help="mysql port", default='3306')
parser.add_argument("--mysql-user", type=str, help="mysql user")
parser.add_argument("--mysql-password", type=str, help="mysql password")
parser.add_argument("--token", type=str, help="Telegram API token given by @botfather.")
parser.add_argument("--admin", type=str, help="Alias of the admin user.")
parser.add_argument("--data", type=str, help="Data JSON path.", default='data.json')
parser.add_argument("--logfile", type=str, help="Log to defined file.")
parser.add_argument("--webhook-host", type=str, help="Sets a webhook to the specified host.")
parser.add_argument("--webhook-port", type=int, help="Webhook port. Default is 443.", default=443)
parser.add_argument("--webhook-listening", type=str, help="Webhook local listening IP. Default is 0.0.0.0",
                    default="0.0.0.0")
parser.add_argument("--webhook-listening-port", type=int, help="Webhook local listening port. Default is 8080", default=8080)


args = parser.parse_args()

BUCKET = args.bucket


try:
    args.logfile = os.environ[_ENV_LOGGING_FILE]
except KeyError:
    pass

if args.logfile:
    logger.add_file_handler(args.logfile, args.verbosity)

logger.set_log_level(args.verbosity)


try:
    args.token = os.environ[_ENV_TELEGRAM_BOT_TOKEN]
except KeyError as key_error:
    if not args.token:
        LOG.critical(
            'No telegram bot token provided. Please do so using --token argument or %s environment variable.',
            _ENV_TELEGRAM_BOT_TOKEN)
        exit(1)

try:
    args.admin = os.environ[_ENV_TELEGRAM_USER_ALIAS]
except KeyError as key_error:
    if not args.admin:
        LOG.warn(
            'No admin user specified. Please do so using --admin argument or %s environment variable.',
            _ENV_TELEGRAM_USER_ALIAS)

try:
    args.database = os.environ[_ENV_DATABASE_NAME]
except KeyError:
    pass

try:
    args.mysql_host = os.environ[_ENV_MYSQL_HOST]
except KeyError:
    pass

try:
    args.mysql_port = os.environ[_ENV_MYSQL_PORT]
except KeyError:
    pass

try:
    args.mysql_user = os.environ[_ENV_MYSQL_USER]
except KeyError:
    pass

try:
    args.mysql_password = os.environ[_ENV_MYSQL_PASSWORD]
except KeyError:
    pass

try:
    args.data = os.environ[_ENV_DATA_JSON]
except KeyError:
    pass

try:
    args.sqlite = os.environ[_ENV_SQLITE_FILE]
except KeyError:
    pass

try:
    args.webhook_host = os.environ[_ENV_WEBHOOK_HOST]
except KeyError:
    pass

try:
    args.webhook_port = os.environ[_ENV_WEBHOOK_PORT]
except KeyError:
    pass

try:
    args.webhook_listening = os.environ[_ENV_WEBHOOK_LISTEN]
except KeyError:
    pass

try:
    args.webhook_listening_port = os.environ[_ENV_WEBHOOK_LISTEN_PORT]
except KeyError:
    pass

LOG.info('Starting up bot...')
if args.sqlite and args.mysql_host:
    LOG.info("SQLite and MySQL databases on arguments. Attempting data migration...")
    try:
        sqlite = Database('sqlite', filename=args.sqlite, create=False)
        mysql = Database('mysql', host=args.mysql_host, port=args.mysql_port, database_name=args.database,
                         user=args.mysql_user, password=args.mysql_password)
        migrate(sqlite, mysql)
    except OSError as e:
        LOG.info("Migration aborted: %s.", e.args)
if args.mysql_host:
    LOG.info('Using MySQL as persistence layer: host %s port %s', args.mysql_host, args.mysql_port)
    database = Database('mysql', host=args.mysql_host, port=args.mysql_port, database_name=args.database,
                        user=args.mysql_user, password= args.mysql_password)
else:
    LOG.info('Using SQLite as persistence layer.')
    database = Database('sqlite', filename=args.sqlite)

bot = telebot.TeleBot(args.token)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    LOG.debug(message)
    cid = message.chat.id
    bot.send_message(cid,
                     "This is an inline bot. Type its name in a conversation to use it.")
    database.add_or_update_user(message.from_user)


@bot.inline_handler(lambda query: query.query == '')
def query_empty(inline_query):
    LOG.debug(inline_query)
    r = []
    recently_used_sounds = database.get_latest_used_sounds_from_user(inline_query.from_user.id)
    for sound in recently_used_sounds:
        r.append(types.InlineQueryResultVoice(
            sound.id, BUCKET + sound.filename, '🕚 '+sound.text, caption=sound.text))
    for sound in sounds:
        if sound in recently_used_sounds:
            continue
        r.append(types.InlineQueryResultVoice(
            sound.id, BUCKET + sound.filename, sound.text, caption=sound.text))
        if len(r) > TELEGRAM_INLINE_MAX_RESULTS:  # https://core.telegram.org/bots/api#answerinlinequery
            break
    bot.answer_inline_query(inline_query.id, r, is_personal=True, cache_time=0)
    on_query(inline_query)


@bot.inline_handler(lambda query: query.query)
def query_text(inline_query):
    LOG.debug(inline_query)
    try:
        text = unidecode.unidecode(inline_query.query.translate(REMOVE_CHARS).lower())
        LOG.debug("Querying: " + text)
        r = []
        for sound in sounds:
            if text in sound.tags:  # FIXME: Improve search
                r.append(types.InlineQueryResultVoice(
                    sound.id, BUCKET + sound.filename, sound.text, caption=sound.text))
            if len(r) > TELEGRAM_INLINE_MAX_RESULTS:
                break
        bot.answer_inline_query(inline_query.id, r, cache_time=5)
        on_query(inline_query)
    except Exception as e:
        LOG.error("Query aborted" + str(e), e)


@bot.chosen_inline_handler(func=lambda chosen_inline_result: True)
def on_result(chosen_inline_result):
    LOG.debug('Chosen result: %s', str(chosen_inline_result))
    try:
        database.add_result(chosen_inline_result)
    except Exception as e:
        LOG.error("Couldn't save result" + str(e), e)


def on_query(query):
    try:
        database.add_query(query)
    except Exception as e:
        LOG.error("Couldn't save query" + str(e), e)


def synchronize_sounds():
    db_sounds = database.get_sounds(include_disabled=False)
    LOG.debug("Sounds in db (%d)", len(db_sounds))

    b_data_json = open(args.data).read()
    data_json = json.loads(b_data_json)

    json_sounds = data_json["sounds"]
    LOG.debug("Sounds in data.json (%d)", len(json_sounds))

    # Adding new sounds to db
    for jsound in json_sounds:
        query = database.get_sound(filename=jsound["filename"])
        if not query:
            jsound["id"] = ''.join(random.choices(string.digits, k=8))
            database.add_sound(jsound["id"], jsound["filename"], jsound["text"], jsound["tags"])

    # Removing deleted sounds from db
    db_sounds = database.get_sounds(include_disabled=False)
    for db_sound in db_sounds:
        found = None
        for jsound in json_sounds:
            if jsound["filename"] == db_sound.filename:
                found = jsound
                break
        if not found:
            database.delete_sound(db_sound)
            db_sounds.remove(db_sound)

    return db_sounds


# ADMIN COMMANDS

def message_is_from_admin(message):
    from_user = message.from_user
    return from_user.username == args.admin


@bot.message_handler(commands=['stats'], func=lambda message: message_is_from_admin(message))
def send_stats(message):
    LOG.debug(message)
    cid = message.chat.id
    uptime = PrettyUptime.get_pretty_python_uptime(custom_name='Bot')
    users = database.get_users()
    queries = database.get_queries()
    results = database.get_results()
    bot.send_message(cid,
                     '🤖 {uptime}\n'
                     '*All time stats:*\n'
                     '👥 Users: {num_users}\n'
                     '🔎 Queries: {num_queries}\n'
                     '🔊 Results: {num_results}\n'.format(num_users=len(users),
                                                         num_queries=len(queries),
                                                         num_results=len(results),
                                                         uptime=uptime), parse_mode='Markdown')


@bot.message_handler(commands=['uptime'], func=lambda message: message_is_from_admin(message))
def send_uptime(message):
    LOG.debug(message)
    cid = message.chat.id
    py_uptime = PrettyUptime.get_pretty_python_uptime(custom_name='Bot')
    machine_uptime = PrettyUptime.get_pretty_machine_uptime_string()
    machine_info = PrettyUptime.get_pretty_machine_info()
    bot.send_message(cid,
                     '💻 {machine_info}\n'
                     '⌛ {machine_uptime}\n'
                     '🤖 {py_uptime}\n'
                     .format(machine_info=machine_info, machine_uptime=machine_uptime, py_uptime=py_uptime))


sounds = synchronize_sounds()
LOG.info('Serving %i sounds.', len(sounds))

if args.webhook_host:
    webhook.start_webhook(bot, args.webhook_host, args.webhook_port, args.webhook_listening, args.webhook_listening_port)
else:
    try:
        bot.remove_webhook()
    except telebot.apihelper.ApiException as e:
        LOG.debug(e)
    while True:
        try:
            sleep(1)
            LOG.debug("Polling started")
            bot.polling()
        except requests.exceptions.ConnectionError as connection_error:
            LOG.error("ConnectionError: Cannot connect to server.")
            LOG.debug(connection_error)
        except requests.exceptions.ReadTimeout as read_timeout:
            LOG.error("ReadTimeout: Lost connection to the server.")
            LOG.debug(read_timeout)
        except Exception as e:
            LOG.critical(e)
            raise e