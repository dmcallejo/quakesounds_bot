import app.logger as logger

LOG = logger.get_logger('migration_tool')


def migrate(from_db, to_db):
    sounds = from_db.get_sounds()
    users = from_db.get_users()
    queries = from_db.get_queries()
    results = from_db.get_results()
    LOG.info("Migrating %d sounds, %d users, %d queries, %d results.",
             len(sounds), len(users), len(queries), len(results))
    for sound in sounds:
        if to_db.get_sound(sound.id):
            continue
        to_db.add_sound(sound.id,
                        sound.filename,
                        sound.text,
                        sound.tags,
                        sound.disabled)
    for user in users:
        if to_db.get_user(user.id):
            continue
        to_db.add_user(user.id,
                       user.is_bot,
                       user.first_name,
                       user.last_name,
                       user.username,
                       user.language_code,
                       user.queries,
                       user.results,
                       user.first_seen)
    for query in queries:
        if to_db.get_query(query.id):
            continue
        to_db.add_raw_query(query.id,
                            query.user,
                            query.text,
                            query.timestamp)
    for result in results:
        if to_db.get_result(result.id):
            continue
        to_db.add_raw_result(result.id,
                             result.user,
                             result.sound,
                             result.timestamp)
    LOG.info("Migration finished.")