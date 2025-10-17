from db import SessionLocal, Message, Node, Telemetry, Position, Traceroute
from pubsub import pub
import json

MY_NODE_ID = None

def on_connected(interface, topic=pub.AUTO_TOPIC):
    print("Connected to Meshtastic device:")
    node = interface.getMyNodeInfo()
    MY_NODE_ID = node['num']
    print(MY_NODE_ID)


def on_receive_data(packet, interface):
    try:
        decoded = packet.get('decoded', {})
        portnum = decoded.get('portnum', None)
        match portnum:
            case "NODEINFO_APP":
                handle_nodeinfo_packet(packet, interface)
            case "POSITION_APP":
                handle_position_packet(packet, interface)
            case "TELEMETRY_APP":
                handle_telemetry_packet(packet, interface)
            case "TEXT_MESSAGE_APP":
                handle_message_packet(packet, interface)
            case "TRACEROUTE_APP":
                handle_traceroute_packet(packet, interface)
            case "ROUTING_APP":
                print(f"Routing packet received: {packet}")
            case _:
                print(f"Unknown port number: {portnum}\nPacket: {packet}")
                return
    except Exception as e:
        print(f"Error processing packet: {e}")

def handle_nodeinfo_packet(packet, interface):
    try:
        decoded = packet.get('decoded', {})
        user = decoded.get('user', {})

        short_id = user.get('id', None)
        long_id = packet.get('from', None)
        long_name = user.get('longName', None)
        short_name = user.get('shortName', None)
        role = user.get('role', "CLIENT")
        hw_model = user.get('hwModel', None)
        is_unmessagable = user.get('isUnmessagable', False)

        longitude = None
        latitude = None

        print(f"Received user info from {short_id}: {long_name}")

        session = SessionLocal()

        node = session.query(Node).filter_by(long_id=long_id).first()
        if not node and short_id:
            node = session.query(Node).filter_by(short_id=short_id).first()

        if node:
            updated = False
            if node.long_name != long_name:
                node.long_name = long_name
                updated = True
            if node.short_name != short_name:
                node.short_name = short_name
                updated = True
            if node.short_id != short_id:
                node.short_id = short_id
                updated = True
            if node.role != role:
                node.role = role
                updated = True
            if node.hw_model != hw_model:
                node.hw_model = hw_model
                updated = True
            if node.is_unmessagable != is_unmessagable:
                node.is_unmessagable = is_unmessagable
                updated = True

            if updated:
                session.commit()
                print("User info updated in database!")
            else:
                print("User info already up to date, no changes made.")
        else:
            new_node = Node(
                short_id=short_id,
                long_id=long_id,
                long_name=long_name,
                short_name=short_name,
                role=role,
                hw_model=hw_model,
                longitude=None,
                latitude=None,
                is_unmessagable=is_unmessagable
            )
            session.add(new_node)
            session.commit()
            print("New user info saved to database!")

        session.close()

    except Exception as e:
        print(f"Error processing packet: {e}")


def handle_message_packet(packet, interface):
    try:
        decoded = packet.get('decoded', {})
        text = decoded.get('text')
        if not text:
            return

        from_long_id = packet.get('from', 0)
        rx_rssi = packet.get('rxRssi') or 0
        rx_snr = int(packet.get('rxSnr') or 0)
        rx_time = packet.get('rxTime') or 0
        via_mqtt = packet.get('viaMqtt', False)

        print(f"Received message from {from_long_id}: {text}")

        if (packet.get('to') == MY_NODE_ID):
            print("Message is for me, ignoring.")
            return

        session = SessionLocal()
        from_node = session.query(Node).filter_by(long_id=from_long_id).first()
        if not from_node:
            from_node = Node(long_id=from_long_id)
            session.add(from_node)
            session.commit()
            print(f"Created minimal node entry for long_id {from_long_id}")

        msg = Message(
            from_node_id=from_node.id,
            text=text,
            rx_rssi=rx_rssi,
            rx_snr=rx_snr,
            rx_time=rx_time,
            via_mqtt=via_mqtt
        )
        session.add(msg)
        session.commit()
        session.close()
        print("Message saved to database!")

    except Exception as e:
        print(f"Error processing packet: {e}")

def handle_position_packet(packet, interface):
    try:
        decoded = packet.get('decoded', {})
        position = decoded.get('position', {})

        from_long_id = packet.get("from", 0)
        latitude = position.get("latitude", 0.0)
        longitude = position.get("longitude", 0.0)
        altitude = position.get("altitude", 0)
        satsInView = position.get("satsInView", None)

        if (from_long_id == 0):
            return

        if (latitude == 0.0 and longitude == 0.0):
            return

        print(f"Received position from {from_long_id}: {latitude}, {longitude}, {altitude}")
        session = SessionLocal()

        node = session.query(Node).filter_by(long_id=from_long_id).first()
        if not node:
            node = Node(long_id=from_long_id)
            session.add(node)
            session.commit()
            print(f"Created minimal node entry for long_id {from_long_id}")

        if packet.get('hopStart') == packet.get('hopLimit'):
            rx_snr = int(packet.get('rxSnr') or 0)
            via_mqtt = packet.get('viaMqtt', False)
            hops = {
                "snrTowards": [],
                "route": []
            }
            hops["snrTowards"].append(rx_snr)
            traceroute_entry = Traceroute(
                from_node_id=from_long_id,
                to_node_id=15, #magic number 
                hops=json.dumps(hops),
                via_mqtt=via_mqtt
            )
            print(f"Adding direct traceroute entry for position packet from {from_long_id} to {MY_NODE_ID}")
            session.add(traceroute_entry)

        pos = Position(
            node_id=node.id,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            satsInView=satsInView
        )
        session.add(pos)
        session.commit()
        session.close()

        print(f"Position saved to database!")

    except Exception as e:
        print(f"Error processing packet: {e}")

def handle_telemetry_packet(packet, interface):
    try: 
        decoded = packet.get('decoded', {})
        deviceMetrics = decoded.get('telemetry', {}).get('deviceMetrics', {})
        environmentMetrics = decoded.get('telemetry', {}).get('environmentMetrics', {})
        long_id = packet.get('from', None)
        if long_id is None:
            return

        battery = deviceMetrics.get('batteryLevel', None)
        uptime = deviceMetrics.get('uptimeSeconds', None)
        voltage = deviceMetrics.get('voltage', None)
        channel_util = deviceMetrics.get('channelUtilization', None)
        air_util_tx = deviceMetrics.get('airUtilTx', None)
        temperature = environmentMetrics.get('temperature', None)
        humidity = environmentMetrics.get('relativeHumidity', None)
        pressure = environmentMetrics.get('barometricPressure', None)
        if battery is None and uptime is None and voltage is None and channel_util is None and air_util_tx is None and temperature is None and humidity is None and pressure is None:
            return

        print(f"Received telemetry from {long_id}: Battery={battery}, Uptime={uptime}, Voltage={voltage}, Channel Util={channel_util}, Air Util TX={air_util_tx}")

        session = SessionLocal()
        node = session.query(Node).filter_by(long_id=long_id).first()
        if not node:
            node = Node(long_id=long_id)
            session.add(node)
            session.commit()
            print(f"Created minimal node entry for long_id {long_id}")

        if packet.get('hopStart') == packet.get('hopLimit'):
            rx_snr = int(packet.get('rxSnr') or 0)
            via_mqtt = packet.get('viaMqtt', False)
            hops = {
                "snrTowards": [],
                "route": []
            }
            hops["snrTowards"].append(rx_snr)
            traceroute_entry = Traceroute(
                from_node_id=from_long_id,
                to_node_id=15, #magic number 
                hops=json.dumps(hops),
                via_mqtt=via_mqtt
            )
            print(f"Adding direct traceroute entry for position packet from {from_long_id} to {MY_NODE_ID}")
            session.add(traceroute_entry)

        telemetry = Telemetry(
            node_id=node.id,
            battery=battery,
            uptime=uptime,
            voltage=voltage,
            channel_util=channel_util,
            air_util_tx=air_util_tx,
            temperature=temperature,
            humidity=humidity,
            pressure=pressure
        )
        session.add(telemetry)
        session.commit()
        session.close()

        print("Telemetry data saved to database!")
    except Exception as e:
        print(f"Error processing packet: {e}")

def handle_traceroute_packet(packet, interface):
    try:
        decoded = packet.get('decoded', {})
        from_node_id = packet.get('from', None)
        to_node_id = packet.get('to', None)

        if from_node_id is None or to_node_id is None:
            return
        
        traceroute = decoded.get('traceroute', {})
        route = traceroute.get("route", [])
        snr_towards = traceroute.get("snrTowards", [])

        filtered_route = [h for h in route if h != 4294967295]
        filtered_snr = [s for s in snr_towards if s != -128]

        hops = {
            "route": filtered_route,
            "snrTowards": filtered_snr
        }

        via_mqtt = packet.get('viaMqtt', False)

        print(f"Received traceroute from {from_node_id} to {to_node_id}: {hops}")

        session = SessionLocal()
        from_node = session.query(Node).filter_by(long_id=from_node_id).first()
        if not from_node:
            from_node = Node(long_id=from_node_id)
            session.add(from_node)
            session.commit()
            print(f"Created minimal node entry for long_id {from_node_id}")
        to_node = session.query(Node).filter_by(long_id=to_node_id).first()
        if not to_node:
            to_node = Node(long_id=to_node_id)
            session.add(to_node)
            session.commit()
            print(f"Created minimal node entry for long_id {to_node_id}")

        traceroute_entry = Traceroute(
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            hops=json.dumps(hops),
            via_mqtt=via_mqtt
        )
        session.add(traceroute_entry)
        session.commit()
        session.close()
        print("Traceroute data saved to database!")

    except Exception as e:
        print(f"Error processing packet: {e}")
