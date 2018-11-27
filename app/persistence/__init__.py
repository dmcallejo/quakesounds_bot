import datetime
from pony.orm import *
import app.logger as logger

LOG = logger.get_logger('persistence')


class Database:

    def __init__(self, provider, filename=None, host=None, port=None, user=None, password=None, database_name=None):
        self.db = pony.orm.Database()

        class Sound(self.db.Entity):
            id = PrimaryKey(int)
            filename = Required(str, index=True, unique=True)
            text = Required(str)
            tags = Required(str)
            uses = Set('ResultHistory')
            disabled = Required(bool)

        class User(self.db.Entity):
            id = PrimaryKey(int)
            is_bot = Required(bool)
            first_name = Required(str)
            last_name = Optional(str)
            username = Optional(str)
            language_code = Optional(str)
            queries = Set('QueryHistory')
            results = Set('ResultHistory')
            first_seen = Required(datetime.datetime, sql_default='CURRENT_TIMESTAMP')

        class QueryHistory(self.db.Entity):
            id = PrimaryKey(int, auto=True)
            user = Required(User)
            text = Optional(str)
            timestamp = Required(datetime.datetime, sql_default='CURRENT_TIMESTAMP')

        class ResultHistory(self.db.Entity):
            id = PrimaryKey(int, auto=True)
            user = Required(User)
            sound = Required(Sound)
            timestamp = Required(datetime.datetime, sql_default='CURRENT_TIMESTAMP')

        if provider == 'mysql':
            LOG.info('Starting persistence layer using MySQL on %s:%s db: %s', host, port, database_name)
            LOG.debug('MySQL data: host --> %s, port -->%s, user --> %s, db --> %s, password empty --> %s',
                      host, port, user, database_name, str(password is None))
            self.db.bind(provider='mysql', host=host, port=int(port), user=user, passwd=password, db=database_name)
        elif provider == 'postgres':
            LOG.info('Starting persistence layer using PostgreSQL on %s:%s db: %s', host, port, database_name)
            LOG.debug('PostgreSQL data: host --> %s, port --> %s, user --> %s, db --> %s, password empty --> %s',
                      host, user, port, database_name, str(password is None))
            self.db.bind(provider='postgres', host=host, port=port, user=user, password=password,
                         database=database_name)
        elif filename is not None:
            LOG.info('Starting persistence layer on file %s using SQLite.', filename)
            self.db.bind(provider='sqlite', filename=filename, create_db=True)
        else:
            LOG.info('Starting persistence layer on memory using SQLite.')
            self.db.bind(provider='sqlite', filename=':memory:')
        self.db.generate_mapping(create_tables=True)

    @db_session
    def get_sounds(self, include_disabled=True):
        if include_disabled:
            query = self.db.Sound.select()
        else:
            query = self.db.Sound.select(lambda sound: sound.disabled is False)
        sounds = [Sound(db_object)
                  for db_object in query]
        LOG.debug("get_sounds: Obtained %d: %s", len(sounds), str(sounds))
        return sounds

    @db_session
    def get_sound(self, id=None, filename=None):
        if not id:
            db_object = self.db.Sound.get(filename=filename)
        elif not filename:
            db_object = self.db.Sound.get(id=id)
        else:
            db_object = self.db.Sound.get(id=id, filename=filename)

        if db_object:
            return Sound(db_object)

    @db_session
    def add_sound(self, id, filename, text, tags, disabled=False):
        LOG.info('Adding sound: %s %s', id, filename)
        self.db.Sound(id=id, filename=filename, text=text, tags=tags, disabled=disabled)
        commit()

    @db_session
    def delete_sound(self, sound):
        assert type(sound) is Sound
        LOG.info('Deleting sound %s', str(sound))
        sound = self.db.Sound.get(filename=sound.filename)
        if len(sound.uses) > 0:
            sound.delete()
        else:
            sound.disabled = True

    @db_session
    def add_user(self, id, is_bot, first_name, last_name, username, language_code, queries, results, first_seen):
        LOG.info("Adding user {} {} (@{}) - {}".format(first_name, last_name, username, first_seen))
        self.db.User(id=id,
                     is_bot=is_bot,
                     first_name=first_name,
                     last_name=last_name,
                     username=username,
                     language_code=language_code,
                     # queries=queries,
                     # results=results,
                     first_seen=first_seen)

    @db_session
    def add_or_update_user(self, user):
        if not isinstance(user, dict):
            user = vars(user)
            LOG.debug('Translated type: %s', str(user))
        db_user = self.get_user(id=user['id'])
        if db_user is not None and user != db_user:
            LOG.info('Updating user: %s', str(db_user))
            updated_user = self.db.User[user['id']]
            updated_user.id = user['id']
            updated_user.is_bot = user['is_bot']
            updated_user.first_name = user['first_name']
            updated_user.last_name = (user['last_name'] if user['last_name'] is not None else '')
            updated_user.username = (user['username'] if user['username'] is not None else '')
            updated_user.language_code = (user['language_code'] if user['language_code'] is not None else '')
        elif db_user is None:
            LOG.info('Adding user: %s', str(user))
            self.db.User(id=user['id'], is_bot=user['is_bot'], first_name=user['first_name'],
                         last_name=(user['last_name'] if user['last_name'] is not None else ''),
                         username=(user['username'] if user['username'] is not None else ''),
                         language_code=(user['language_code'] if user['language_code'] is not None else ''))
        else:
            LOG.debug('User %s already in database.', user['id'])
            return
        commit()
        return self.get_user(user['id'])

    @db_session
    def get_users(self):
        query = self.db.User.select()
        users = query[:]
        LOG.debug("get_users: Obtained %d: %s", len(users), str(users))
        return users

    @db_session
    def get_user(self, id=None, username=None):
        if not id:
            db_object = self.db.User.get(username=username)
        elif not username:
            db_object = self.db.User.get(id=id)
        else:
            db_object = self.db.User.get(id=id, username=username)

        if db_object:
            return object_to_user(db_object)

    @db_session
    def add_raw_query(self, id, user, text, timestamp):
        LOG.info("Adding query: {} - {} ({})".format(user, text, timestamp))
        self.db.QueryHistory(id=id, user=self.db.User[user.id], text=text, timestamp=timestamp)

    @db_session
    def add_query(self, query):
        LOG.info("Adding query: %s", str(query))
        from_user = query.from_user
        db_user = self.get_user(from_user.id)
        if not db_user:
            db_user = self.add_or_update_user(from_user)

        self.db.QueryHistory(user=self.db.User[db_user['id']], text=query.query)

    @db_session
    def get_query(self, id):
        return self.db.QueryHistory.get(id=id)

    @db_session
    def get_queries(self):
        query = self.db.QueryHistory.select()
        queries = query[:]
        LOG.debug("get_queries: Obtained %d: %s", len(queries), str(queries))
        return queries

    @db_session
    def add_raw_result(self, id, user, sound, timestamp):
        LOG.info("Adding result: {} - {} ({})".format(user, sound, timestamp))
        self.db.ResultHistory(id=id, user=self.db.User[user.id], sound=self.db.Sound[sound.id], timestamp=timestamp)

    @db_session
    def add_result(self, result):
        LOG.info("Adding result: %s", str(result))
        from_user = result.from_user
        db_user = self.get_user(from_user.id)
        if not db_user:
            db_user = self.add_or_update_user(from_user)

        self.db.ResultHistory(user=self.db.User[db_user['id']], sound=self.db.Sound[result.result_id])

    @db_session
    def get_result(self, id):
        return self.db.ResultHistory.get(id=id)

    @db_session
    def get_results(self):
        query = self.db.ResultHistory.select()
        results = query[:]
        LOG.debug("get_results: Obtained %d: %s", len(results), str(results))
        return results

    @db_session
    def get_latest_used_sounds_from_user(self, user_id, limit=3):
        user = self.db.User.get(id=user_id)
        if user:
            results = self.db.Sound.select_by_sql('SELECT sound.* '
                                                  'FROM sound, resulthistory '
                                                  'WHERE sound.id = resulthistory.sound '
                                                  'AND resulthistory.id IN '
                                                  '(SELECT MAX(id) '
                                                  'FROM resulthistory '
                                                  'WHERE resulthistory.user = $user '
                                                  'GROUP BY resulthistory.sound) '
                                                  'ORDER BY resulthistory.id DESC '
                                                  'LIMIT $limit;',
                                                  globals={'user': user.id, 'limit': limit})
            LOG.debug("Obtained %d latest used sound results.", len(results))
            return [Sound(db_object)
                    for db_object in results]
        else:
            return []


class Sound:
    def __init__(self, db_object):
        self.id = db_object.id
        self.filename = db_object.filename
        self.text = db_object.text
        self.tags = db_object.tags
        self.disabled = db_object.disabled

    def __repr__(self):
        return f"Sound({self.id} {self.filename})"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return (
                self.__class__ == other.__class__ and
                self.id == other.id)


# MAPPERS


def object_to_sound(db_object):
    return {'id': db_object.id, 'filename': db_object.filename, 'text': db_object.text, 'tags': db_object.tags}


def object_to_user(db_object):
    return {'id': db_object.id, 'is_bot': db_object.is_bot, 'first_name': db_object.first_name,
            'username': (db_object.username if db_object.username is not '' else None),
            'last_name': (db_object.last_name if db_object.last_name is not '' else None),
            'language_code': (db_object.language_code if db_object.language_code is not '' else None)}


def object_to_query(db_object):
    return {'id': db_object.id, 'user': object_to_user(db_object.user), 'text': db_object.text,
            'timestamp': db_object.timestamp}


def object_to_result(db_object):
    return {'id': db_object.id, 'user': object_to_user(db_object.user), 'sound': object_to_sound(db_object.sound),
            'timestamp': db_object.timestamp}
