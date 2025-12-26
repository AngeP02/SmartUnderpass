#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script per leggere i messaggi dal TelosB via seriale e pubblicarli su MQTT.
AGGIORNATO PER VISUALIZZARE LOGICA ISTERESI ACQUA
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

SERIAL_PORT = "COM7"  # <--- VERIFICA CHE SIA CORRETTA
BAUD_RATE = 115200
TIMEOUT = 2

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_DATA = "angelica/iot/data"
MQTT_CLIENT_ID = "sender_angelica_pc"

JSON_FILE = "underpass_data.json"

# =============================================================================
# STRUTTURA DATI (AMSend)
# =============================================================================
# Deve corrispondere alla struct ReportMsg nel file .h
REPORT_MSG_SIZE = 22
REPORT_MSG_FORMAT = '!HHBhHHHBBBBBBBH'  # Big-Endian
MAGIC_HEADER = 0xAA55


# =============================================================================
# CLASSE MQTT
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
        checksum_calc = 0
        payload_bytes = data[:REPORT_MSG_SIZE - 2]
        for b in payload_bytes:
            val = ord(b) if isinstance(b, str) else b
            checksum_calc += val

        checksum_calc &= 0xFFFF
        checksum_recv = values[14]

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


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("SMART UNDERPASS BRIDGE (Lettura dati + Debug Isteresi)")
    print("-------------------------------------------------------")

    mqtt_pub = None
    if MQTT_AVAILABLE:
        print("MQTT: Abilitato -> " + MQTT_BROKER)
        mqtt_pub = MQTTPublisher(MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID)
        if not mqtt_pub.connect():
            print("MQTT: Connessione fallita")
    else:
        print("MQTT: Non disponibile")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        print("Seriale aperta su " + SERIAL_PORT)
    except Exception as e:
        print("ERRORE APERTURA SERIALE: " + str(e))
        sys.exit(1)

    buffer = bytearray()

    try:
        while True:
            # Compatibilità PySerial 2/3
            n_waiting = 0
            if hasattr(ser, 'in_waiting'):
                n_waiting = ser.in_waiting
            else:
                n_waiting = ser.inWaiting()

            if n_waiting > 0:
                new_data = ser.read(n_waiting)
                buffer.extend(new_data)

                # --- 1. CERCA E DECODIFICA PACCHETTI BINARI (AMSend) ---
                while len(buffer) >= REPORT_MSG_SIZE:
                    header_bytes = b'\xaa\x55'

                    # Cerca l'header
                    str_buffer = bytes(buffer)
                    idx = str_buffer.find(header_bytes)

                    # Se non lo trova ma il buffer è pieno di testo, pulisci
                    if idx == -1:
                        # Non cancellare tutto subito, potremmo avere printf
                        break

                    # Se l'header non è all'inizio, controlla se c'è testo prima
                    if idx > 0:
                        # C'è roba prima dell'header? Potrebbe essere testo printf
                        text_part = buffer[:idx]
                        if b'\n' in text_part:
                            # Lascia che il gestore testo sotto lo stampi
                            break
                        else:
                            # Spazzatura, scarta fino all'header
                            buffer = buffer[idx:]

                    # Ora buffer inizia con AA 55
                    if len(buffer) < REPORT_MSG_SIZE:
                        break

                    raw_data = bytes(buffer[:REPORT_MSG_SIZE])

                    # Decodifica
                    report = decode_report_msg(raw_data)

                    if report:
                        # Rimuovi il pacchetto processato dal buffer
                        buffer = buffer[REPORT_MSG_SIZE:]

                        print("\n[RICEVUTO PACKET] " + report['timestamp'])
                        print(" > Meteo: %d C | %d hPa | %d %%" % (
                            report['temperatura_celsius'],
                            report['pressione_hpa'],
                            report['umidita_percentuale']))
                        print(" > Acqua: %d cm | Luci: %d lux" % (
                            report['livello_acqua_cm'],
                            report['luminosita_lux']))

                        json_data = json.dumps(report)
                        save_to_json(report, JSON_FILE)

                        if MQTT_AVAILABLE and mqtt_pub and mqtt_pub.connected:
                            mqtt_pub.publish(MQTT_TOPIC_DATA, json_data)
                            print(" > MQTT Inviato")
                    else:
                        # Header trovato ma pacchetto invalido (es. checksum), avanza di 1 byte
                        buffer = buffer[1:]

                # --- 2. GESTIONE MESSAGGI DEBUG (Printf) ---
                while b'\n' in buffer:
                    # Se l'header binario è all'inizio, non toccare, è compito del while sopra
                    if len(buffer) >= 2 and buffer[0] == 0xAA and buffer[1] == 0x55:
                        break

                    idx = buffer.find(b'\n')
                    if idx != -1:
                        # Estrai la linea
                        line_bytes = buffer[:idx]
                        buffer = buffer[idx + 1:]  # Rimuovi dal buffer

                        # Filtro lunghezza (aumentato a 150 per i messaggi lunghi)
                        if len(line_bytes) > 0 and len(line_bytes) < 150:
                            try:
                                line = line_bytes.decode('utf-8', 'ignore').strip()
                                # Stampa solo se è testo leggibile
                                if len(line) > 1:
                                    if ">>>" in line:
                                        # Evidenzia i messaggi di controllo logica
                                        print("\033[93m[LOGIC] " + line + "\033[0m")
                                    elif "RICEVUTO" not in line:
                                        print("[MOTE] " + line)
                            except:
                                pass
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