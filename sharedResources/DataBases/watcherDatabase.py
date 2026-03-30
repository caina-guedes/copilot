
import asyncio
import aiosqlite
import json
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
from sharedResources.debuggingResources.unified_monitor import monitor_class
logger = LoggerManager.get_logger(__name__, filename=__name__ + '.log')


@monitor_class
class WatcherNotsentEventsDatabase:
    main_reference = None
    def __init__(self):
        self.lock = asyncio.Lock()
        # self.initialize_not_sent_events()
        self.conn = None
        self.__class__.main_reference = self

    @classmethod
    async def create(cls):
        self = cls()
        await self.initialize_not_sent_events()
        return self
    
    @classmethod
    async def close(cls):
        self = cls.main_reference
        async with self.lock:
            if self.conn:
                await self.conn.close()
                self.conn = None
                print("Database connection closed safely.")

    async def ensure_connection(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(self.db_path)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")

    async def ensure_connection(self):
        if self.conn is None:
            await self.initialize_not_sent_events()

    async def initialize_not_sent_events(self):
        async with self.lock:
            # print("Initializing not_sent_events database...")
            self.conn = await aiosqlite.connect('not_sent_events.db')
            print("Database connection established.")
            # Ensure the table exists
            # print("Creating not_sent_events table if it does not exist...")
            # self.cursor = self.conn.cursor()
            await self.conn.execute('''
                CREATE TABLE IF NOT EXISTS not_sent_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    not_sent_event TEXT NOT NULL
                )
            ''')
            # print("not_sent_events table is ready.")
            # Commit the changes
            # print("Committing changes to the database...")
            await self.conn.commit()
            # print("Changes committed successfully.")
            # conn.close()

    async def save_event(self,event,retrieve_id=False):
        """
        Save an event to the not_sent_events table.
        If retrieve_id is True, return the ID of the inserted event.
        """
        logger.info("estou no save_event do not_sent_db")
        query = "INSERT INTO not_sent_events (not_sent_event) VALUES (?)"

        # query = f'''INSERT INTO not_sent_events (not_sent_event) 
        #                VALUES ({json.dumps(event)})'''
        saved_event = False
        print("estou no save_event do not_sent_db logo antes de await self.ensure_connection()")
        await self.ensure_connection()
        print("estou no save_event do not_sent_db logo depois de await self.ensure_connection()")
        async with self.lock:
            print("estou no save_event do not_sent_db logo depois de self.lock")
            try:
                print("estou no save_event do not_sent_db logo antes de self.conn.execute(query)")
                cursor = await self.conn.execute(query, (json.dumps(event),))
                print("estou no save_event do not_sent_db logo depois de self.conn.execute(query)")
                saved_event = True
            except aiosqlite.Error as e:
                await self.initialize_not_sent_events()
                cursor = await self.conn.execute(query)
                saved_event = True
            except Exception as e:
                log_error_forensics_plus(e)
                logger.error(f"Error saving event on the database: {e}")

            if retrieve_id and saved_event:
                event_id = cursor.lastrowid
                await self.conn.commit()
                return event_id
            await self.conn.commit()
            return saved_event

    async def show_not_sent_events(self,give=True,show=False,only_quantity=False):
        await self.ensure_connection()
        async with self.lock:
            cursor = await self.conn.execute('SELECT * FROM not_sent_events')
            events = await cursor.fetchall()
            if only_quantity:
                logger.info(f"Quantidade de eventos não enviados: {len(events)}")
                return len(events)
            if give:
                return events
            if show:
                logger.info("Eventos não enviados:")
                for event in events:
                    logger.info(f"ID: {event[0]}, Evento: {json.loads(event[1])}")
                    logger.info("-" * 40)

    async def delete_event(self, event_id):
        """
        Deletes an event from the not_sent_events table by its ID.
        """
        success = False
        await self.ensure_connection()
        async with self.lock:
            try:
                await self.conn.execute('DELETE FROM not_sent_events WHERE id = ?', (event_id,))
                await self.conn.commit()
                success = True
            except aiosqlite.Error as e:
                logger.error(f"Error deleting event with ID {event_id}: {e}")
            return success


LifecycleMaster.register_cleanup_function(
    WatcherNotsentEventsDatabase.close,
    priority = 50,
    name = "WatcherNotsentEventsDatabase.close", 
    register_in_atexit = False
    )
