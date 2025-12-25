#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script per leggere i messaggi dal TelosB via seriale e pubblicarli su MQTT.
VERSIONE CORRETTA PER INSTANT CONTIKI / TINYOS
"""

from __future__ import print_function
import serial
import struct
import json
import time
import sys
from datetime import datetime

# Gestione import MQTT opzionale
try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

SERIAL_PORT = "COM7"
BAUD_RATE = 115200
TIMEOUT = 2

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "underpass/sensor/data"
MQTT_TOPIC_STATUS = "underpass/sensor/status"
MQTT_CLIENT_ID = "telosb_serial_reader"

JSON_FILE = "underpass_data.json"

# =============================================================================
# STRUTTURA DATI CORRETTA
# =============================================================================
# Correzione 1: La dimensione è 22 byte, non 23.
REPORT_MSG_SIZE = 22

# Correzione 2: TinyOS usa Big-Endian per i tipi nx_ (network types).
# Usiamo '!' invece di '<' per indicare Big-Endian.
# H=uint16, h=int16, B=uint8
REPORT_MSG_FORMAT = '!HHBhHHHBBBBBBBH'
MAGIC_HEADER = 0xAA55


# =============================================================================
# CLASSE MQTT (Semplificata)
# =============================================================================

class MQTTPublisher:
    def __init__(self, broker, port, client_id):
        self.client = mqtt.Client(client_id)
        self.connected = False
        self.broker = broker
        self.port = port

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.connected = True
            return True
        except Exception as e:
            print("ERRORE connessione MQTT: " + str(e))
            return False

    def publish(self, topic, payload):
        if self.connected:
            try:
                self.client.publish(topic, payload)
                return True
            except:
                return False
        return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()


# =============================================================================
# FUNZIONI DECODIFICA
# =============================================================================

def decode_report_msg(data):
    if len(data) < REPORT_MSG_SIZE:
        return None

    try:
        values = struct.unpack(REPORT_MSG_FORMAT, data[:REPORT_MSG_SIZE])

        if values[0] != MAGIC_HEADER:
            return None

        # Calcolo Checksum
        # Somma i valori numerici dei byte (Python 2/3 compatibile)
        checksum_calc = 0
        payload_bytes = data[:REPORT_MSG_SIZE - 2]
        for b in payload_bytes:
            val = ord(b) if isinstance(b, str) else b
            checksum_calc += val

        checksum_calc &= 0xFFFF
        checksum_recv = values[14]  # L'ultimo elemento è il checksum

        if checksum_calc != checksum_recv:
            print("Checksum Errato: Calc " + str(checksum_calc) + " vs Recv " + str(checksum_recv))
            return None

        report = {
            "timestamp": datetime.now().isoformat(),
            "luminosita_lux": values[1],
            "duty_cycle_luci": values[2],
            "temperatura_celsius": values[3],
            "pressione_hpa": values[4],
            "umidita_percentuale": values[5],
            "livello_acqua_cm": values[6],
            "semafori": {
                "moto": {"giallo": bool(values[7]), "rosso": bool(values[8])},
                "auto": {"giallo": bool(values[9]), "rosso": bool(values[10])},
                "camion": {"giallo": bool(values[11]), "rosso": bool(values[12])}
            },
            "cambio_drastico": bool(values[13])
        }
        return report

    except struct.error as e:
        print("Errore struct: " + str(e))
        return None


def save_to_json(data, filename):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass


def get_stato_sistema(report):
    livello = report['livello_acqua_cm']
    if livello >= 6:
        return "CHIUSURA_TOTALE"
    elif livello >= 5:
        return "CRITICITA_ELEVATA"
    elif livello >= 3:
        return "STOP_AUTO_MOTO"
    elif livello >= 2:
        return "CRITICITA_MODERATA"
    elif livello >= 1:
        return "ATTENZIONE"
    else:
        return "AGIBILE"


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("SMART UNDERPASS BRIDGE (Fix per Instant Contiki)")

    mqtt_pub = None
    if MQTT_AVAILABLE:
        print("MQTT: Abilitato")
        mqtt_pub = MQTTPublisher(MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID)
        if not mqtt_pub.connect():
            print("MQTT: Connessione fallita")
    else:
        print("MQTT: Non disponibile (salvataggio locale)")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        print("Seriale aperta su " + SERIAL_PORT)
    except Exception as e:
        print("ERRORE Seriale: " + str(e))
        sys.exit(1)

    buffer = bytearray()

    try:
        while True:
            # CORREZIONE COMPATIBILITA' PYSERIAL OLD/NEW
            n_waiting = 0
            if hasattr(ser, 'in_waiting'):
                n_waiting = ser.in_waiting
            else:
                n_waiting = ser.inWaiting()  # Metodo vecchio per PySerial 2.x

            if n_waiting > 0:
                new_data = ser.read(n_waiting)
                buffer.extend(new_data)

                while len(buffer) >= REPORT_MSG_SIZE:
                    # Cerca Magic Header (0xAA55 in Big Endian è \xAA\x55)
                    # Nota: struct.pack('!H', 0xAA55) produce b'\xaa\x55'
                    header_bytes = b'\xaa\x55'

                    # Hack per compatibilità python 2 bytearray find
                    str_buffer = bytes(buffer)
                    idx = str_buffer.find(header_bytes)

                    if idx == -1:
                        if len(buffer) > 2: buffer = buffer[-2:]
                        break

                    if idx > 0:
                        buffer = buffer[idx:]

                    if len(buffer) < REPORT_MSG_SIZE:
                        break

                    raw_data = bytes(buffer[:REPORT_MSG_SIZE])
                    buffer = buffer[REPORT_MSG_SIZE:]

                    report = decode_report_msg(raw_data)

                    if report:
                        print("\n[RICEVUTO] " + report['timestamp'])
                        print("Temp: %d C | Press: %d hPa | Umid: %d %%" % (
                            report['temperatura_celsius'],
                            report['pressione_hpa'],
                            report['umidita_percentuale']))
                        print("Acqua: %d cm | Luci: %d lux" % (
                            report['livello_acqua_cm'],
                            report['luminosita_lux']))

                        json_data = json.dumps(report)
                        save_to_json(report, JSON_FILE)

                        if MQTT_AVAILABLE and mqtt_pub and mqtt_pub.connected:
                            mqtt_pub.publish(MQTT_TOPIC_DATA, json_data)
                            print(">> Inviato MQTT")

                # Gestione debug printf (testo semplice)
                while b'\n' in buffer:
                    idx = buffer.find(b'\n')
                    if idx != -1 and idx < 80:  # Se è una linea corta probabilmente è testo
                        line = buffer[:idx].decode('utf-8', 'ignore').strip()
                        buffer = buffer[idx + 1:]
                        # Filtra caratteri strani
                        # Cerca questo blocco nel while b'\n' in buffer:
                        if len(line) > 2 and "RICEVUTO" not in line:
                            print("[DEBUG MOTE] " + line)  # Assicurati che stampi tutto
                    else:
                        break

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nChiusura...")
    except Exception as e:
        print("\nERRORE CRITICO: " + str(e))
    finally:
        ser.close()
        if mqtt_pub: mqtt_pub.disconnect()


if __name__ == "__main__":
    main()