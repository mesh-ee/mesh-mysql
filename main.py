import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

import sys
import time
import meshtastic.tcp_interface
from pubsub import pub
from db import init_db
from handlers import on_connected, on_receive_data
from dotenv import load_dotenv
import os
import sdnotify
import socket

load_dotenv()

def main():
    init_db()

    pub.subscribe(on_connected, "meshtastic.connection.established")
    pub.subscribe(on_receive_data, "meshtastic.receive")

    n = sdnotify.SystemdNotifier()

    while True:
        iface = None
        try:
            print("Connecting via tcp interface...")
            iface = meshtastic.tcp_interface.TCPInterface(os.getenv("TCP_INTERFACE_IP"))
            print("Connected to Meshtastic device!")
            n.notify("READY=1")

            while True:
                n.notify("WATCHDOG=1")
                time.sleep(10)

        except (BrokenPipeError, ConnectionResetError, socket.error) as e:
            print(f"[ERROR] Lost TCP connection: {e}. Reconnecting in 5s…")
            n.notify("WATCHDOG=1")
            time.sleep(5)

        except Exception as e:
            print(f"[ERROR] Unexpected failure: {e}. Retrying in 10s…")
            n.notify("WATCHDOG=1")
            time.sleep(10)

        finally:
            if iface:
                try:
                    iface.close()
                except Exception:
                    pass
                iface = None


if __name__ == "__main__":
    main()