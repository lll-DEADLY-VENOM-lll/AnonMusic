import sys
import asyncio
from pyrogram import Client
from pyrogram.errors import (
    PeerIdInvalid,
    ChatIdInvalid,
    UserNotParticipant,
    UsernameNotOccupied,
    RPCError,
)

import config
from ..logging import LOGGER

# Global lists
assistants = []
assistantids = []

class Userbot(Client):
    def __init__(self):
        self.one = self._create_client(config.STRING1, "AnonXAss1", 1)
        self.two = self._create_client(config.STRING2, "AnonXAss2", 2)
        self.three = self._create_client(config.STRING3, "AnonXAss3", 3)
        self.four = self._create_client(config.STRING4, "AnonXAss4", 4)
        self.five = self._create_client(config.STRING5, "AnonXAss5", 5)

    def _create_client(self, string, name, num):
        if string:
            client = Client(
                name=name,
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(string),
                no_updates=True,
            )
            client.no = num # Assistant number save kar rahe hain
            return client
        return None

    async def _start_assistant(self, client, session_name):
        if not client:
            return

        try:
            await client.start()
            
            # User details fetch karein
            me = await client.get_me()
            client.id = me.id
            client.name = me.mention
            client.username = me.username

            # Username check
            if not client.username:
                LOGGER(__name__).error(
                    f"⚙️ Assistant {client.no} ({session_name}) ka username set nahi hai. "
                    f"Telegram me jaakar username banayein."
                )
                # Username ke bina bot aksar fail ho jata hai, isliye exit logic
                sys.exit(1)

            # Logger ID par message bhejne ki koshish (Bot exit nahi hoga agar ye fail hua)
            try:
                await client.send_message(
                    config.LOGGER_ID,
                    f"✅ Assistant {client.no} Started\nID: {client.id}\nName: {client.name}"
                )
            except Exception as e:
                LOGGER(__name__).warning(
                    f"⚠️ Assistant {client.no} log message nahi bhej saka (Is it in Log Group?): {e}"
                )

            assistants.append(client.no)
            assistantids.append(client.id)
            LOGGER(__name__).info(f"✅ Assistant {client.no} Started as {client.name}")

        except RPCError as e:
            LOGGER(__name__).error(f"🚫 Assistant {client.no} ({session_name}) RPC Error: {e}")
            sys.exit(1)
        except Exception as e:
            LOGGER(__name__).error(f"🚫 Assistant {client.no} ({session_name}) Unexpected Error: {e}")
            sys.exit(1)

    async def start(self):
        LOGGER(__name__).info("Assistants start ho rahe hain...")
        
        # Ek saath saare assistants ko start karne ke liye list
        tasks = []
        if self.one: tasks.append(self._start_assistant(self.one, "STRING1"))
        if self.two: tasks.append(self._start_assistant(self.two, "STRING2"))
        if self.three: tasks.append(self._start_assistant(self.three, "STRING3"))
        if self.four: tasks.append(self._start_assistant(self.four, "STRING4"))
        if self.five: tasks.append(self._start_assistant(self.five, "STRING5"))

        if not tasks:
            LOGGER(__name__).error("🚫 Koi bhi Session String (STRING1-5) nahi mili. Exiting.")
            sys.exit(1)

        # Saare tasks ko run karein
        await asyncio.gather(*tasks)
        
        if not assistants:
            LOGGER(__name__).error("🚫 Koi bhi assistant start nahi ho paya. Exiting.")
            sys.exit(1)
            
        LOGGER(__name__).info(f"✅ Total {len(assistants)} assistants successfully active hain.")

    async def stop(self):
        LOGGER(__name__).info("Assistants ko stop kiya ja raha hai...")
        for client in [self.one, self.two, self.three, self.four, self.five]:
            if client:
                try:
                    await client.stop()
                except Exception:
                    pass
        LOGGER(__name__).info("✅ Saare assistants safely stop ho gaye.")
