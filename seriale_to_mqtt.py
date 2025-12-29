from __future__ import print_function
import serial
import struct
import json
import time
import sys
from datetime import datetime
try:
    import paho.mqtt.client as mqtt

    MQTT_DISPONIBILE = True
except ImportError:
    MQTT_DISPONIBILE = False

# CONFIGURAZIONE

PORTA_SERIALE = "COM7"
BAUD_RATE = 115200
TIMEOUT = 2

INDIRIZZO_SERVER_MQTT = "broker.hivemq.com"
PORTA_MQTT = 1883
CANALE_MQTT = "angelica/iot/data"
MQTT_CLIENT_ID = "sender_angelica_pc"

SIZE_PACCHETTO = 22
FORMATO_PACCHETTO = '!HHBhHHHBBBBBBBH'  # Big-Endian
MAGIC_HEADER = 0xAA55

class MQTTmittente:
    def __init__(self, indirizzo, porta, client_id):
        self.client = mqtt.Client(client_id)
        self.connesso = False
        self.indirizzo_mqtt = indirizzo
        self.porta = porta

    def connessione(self):
        try:
            self.client.connect(self.indirizzo_mqtt, self.porta, 60)
            self.client.loop_start()
            self.connesso = True
            return True
        except Exception as e:
            print("ERRORE connessione MQTT: " + str(e))
            return False

    def pubblica(self, topic, payload):
        if self.connesso:
            try:
                self.client.publish(topic, payload)
                return True
            except:
                return False
        return False

    def disconnetti(self):
        self.client.loop_stop()
        self.client.disconnect()


def controllo_messaggio_ricevuto(data):
    if len(data) < SIZE_PACCHETTO:
        return None
    try:
        values = struct.unpack(FORMATO_PACCHETTO, data[:SIZE_PACCHETTO])
        if values[0] != MAGIC_HEADER:
            return None
        checksum_calcolata = sum([b if isinstance(b, int) else ord(b) for b in data[:SIZE_PACCHETTO - 2]]) & 0xFFFF
        checksum_ricevuta = values[14]
        if checksum_calcolata != checksum_ricevuta:
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
    except struct.error:
        return None


def main():
    print("Ricezione dati - SmartUnderpass")

    mqtt_pub = None
    if MQTT_DISPONIBILE:
        print("MQTT: Abilitato -> " + INDIRIZZO_SERVER_MQTT)
        mqtt_pub = MQTTmittente(INDIRIZZO_SERVER_MQTT, PORTA_MQTT, MQTT_CLIENT_ID)
        mqtt_pub.connessione()

    try:
        ser = serial.Serial(PORTA_SERIALE, BAUD_RATE, timeout=TIMEOUT)
        print("In ascolto su " + PORTA_SERIALE + "\n")
    except Exception as e:
        print("ERRORE SERIALE: " + str(e))
        sys.exit(1)

    buffer = bytearray()
    try:
        while True:
            num_byte_disponibili = getattr(ser, 'in_waiting', ser.inWaiting())
            if num_byte_disponibili > 0:
                nuovi_dati = ser.read(num_byte_disponibili)
                buffer.extend(nuovi_dati)
            while len(buffer) >= 2:
                header_bytes = b'\xaa\x55'
                indice_posizione_magic_header = buffer.find(header_bytes)
                if indice_posizione_magic_header == -1:
                    if len(buffer) > 100:
                        buffer = buffer[-1:]
                    break
                if indice_posizione_magic_header > 0:
                    buffer = buffer[indice_posizione_magic_header:]
                if len(buffer) < SIZE_PACCHETTO:
                    break
                pacchetto_completo = bytes(buffer[:SIZE_PACCHETTO])
                report = controllo_messaggio_ricevuto(pacchetto_completo)
                if report:
                    print(f"[{report['timestamp'][11:19]}] DATI RICEVUTI:")
                    print(
                        f"   Meteo: {report['temperatura_celsius']}°C | {report['umidita_percentuale']}% | {report['pressione_hpa']} hPa")
                    print(f"   Acqua: {report['livello_acqua_cm']} cm | Luci: {report['luminosita_lux']} lux")
                    if report['cambio_drastico']:
                        print("ALLARME CAMBIO DRASTICO")
                    print("-" * 40)
                    if mqtt_pub and mqtt_pub.connesso:
                        mqtt_pub.pubblica(CANALE_MQTT, json.dumps(report))
                    buffer = buffer[SIZE_PACCHETTO:]
                else:
                    buffer = buffer[2:]
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nChiusura...")
    finally:
        ser.close()
        if mqtt_pub: mqtt_pub.disconnetti()


if __name__ == "__main__":
    main()