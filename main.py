import logging
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
import traceback

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

load_dotenv()


def connect_meshtastic(ip: str):
    """Try to connect to a Meshtastic device via TCP and return the interface."""
    print(f"Connecting to Meshtastic device at {ip}...")
    iface = meshtastic.tcp_interface.TCPInterface(ip)
    print("Connected to Meshtastic device!")
    return iface


def main():
    init_db()
    pub.subscribe(on_connected, "meshtastic.connection.established")
    pub.subscribe(on_receive_data, "meshtastic.receive")

    n = sdnotify.SystemdNotifier()
    tcp_ip = os.getenv("TCP_INTERFACE_IP")

    iface = None
    reconnect_delay = 5

    while True:
        try:
            iface = connect_meshtastic(tcp_ip)
            n.notify("READY=1")

            while True:
                n.notify("WATCHDOG=1")
                time.sleep(10)

        except (BrokenPipeError, ConnectionResetError, socket.error, OSError) as e:
            print(f"[WARN] Connection lost or failed: {e}")
            traceback.print_exc()
            print(f"Reconnecting in {reconnect_delay}s...")
            n.notify("WATCHDOG=1")
            time.sleep(reconnect_delay)

        except Exception as e:
            print(f"[ERROR] Unexpected failure: {e}")
            traceback.print_exc()
            print(f"Retrying in {reconnect_delay}s...")
            n.notify("WATCHDOG=1")
            time.sleep(reconnect_delay)

        finally:
            if iface:
                try:
                    iface.close()
                    print("Closed Meshtastic interface.")
                except Exception as e:
                    print(f"[WARN] Error closing interface: {e}")
                iface = None


if __name__ == "__main__":
    main()
