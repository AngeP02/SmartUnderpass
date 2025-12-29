import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import threading
import pandas as pd
import altair as alt
from datetime import datetime

INDIRIZZO_SERVER_MQTT = "broker.hivemq.com"
PORTA = 1883
CANALE_MQTT = "angelica/iot/data"
CLIENT_ID = "dashboard_angelica_final"
st.set_page_config(
    page_title="Smart Underpass | Real-Time",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown("""
<style>
    .stApp {
        background-color: #284451;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    .kpi-card {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 10px;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f3f4f6;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #6b7280;
    }
    .status-banner {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    h3, h4, h6 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

class MQTTDataStore:
    def __init__(self):
        self.ultimo_pacchetto_dati = None
        self.orario_ultima_ricezione = None
        self.conta_messaggi = 0
        self.lock = threading.Lock()


if 'data_store' not in st.session_state:
    st.session_state.data_store = MQTTDataStore()

if 'storico_letture' not in st.session_state:
    st.session_state.storico_letture = []

data_store = st.session_state.data_store

def on_connect(client, userdata, flags, connesso):
    if connesso == 0:
        client.subscribe(CANALE_MQTT)
    else:
        st.error(f"Connessione fallita codice errore: {connesso}")


def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        dati = json.loads(payload)
        with data_store.lock:
            data_store.ultimo_pacchetto_dati = dati
            data_store.orario_ultima_ricezione = time.time()
            data_store.conta_messaggi += 1
    except Exception as e:
        print(f"Errore nella lettura del messaggio: {e}")


@st.cache_resource
def start_mqtt():
    client = mqtt.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(INDIRIZZO_SERVER_MQTT, PORTA, 60)
        client.loop_start()
        return client
    except Exception as e:
        return None


client = start_mqtt()

def livello_allerta(livello_acqua):
    if livello_acqua >= 4.0:
        return {
            "testo": "CHIUSURA TOTALE",
            "colore_sfondo": "linear-gradient(90deg, #7f1d1d, #ef4444)"
        }
    if livello_acqua >= 3.0:
        return {
            "testo": "STOP MOTO / STOP AUTO / CRITICO CAMION",
            "colore_sfondo": "linear-gradient(90deg, #7c2d12, #f97316)"
        }
    if livello_acqua >= 2.0:
        return {
            "testo": "STOP MOTO / CRITICO AUTO / AGIBILE CAMION",
            "colore_sfondo": "linear-gradient(90deg, #713f12, #eab308)"
        }
    if livello_acqua >= 1.0:
        return {
            "testo": "ATTENZIONE",
            "colore_sfondo": "linear-gradient(90deg, #1e3a8a, #3b82f6)"
        }
    return {
        "testo": "SISTEMA AGIBILE",
        "colore_sfondo": "linear-gradient(90deg, #064e3b, #10b981)"
    }

def grafica_card_indicatori(label, value, sub="", icon=""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

def disegna_semaforo(tipo_veicolo, dati_mqtt_semaforo=None, livello_rischio=0):
    rosso_off = "#440000"
    giallo_off = "#443300"
    verde_off = "#003311"

    rosso_on = "#ff4b4b"
    giallo_on = "#ffaa00"
    verde_on = "#00cc44"

    rosso, giallo, verde = rosso_off, giallo_off, verde_off

    if dati_mqtt_semaforo:
        if dati_mqtt_semaforo.get('rosso'):
            rosso = rosso_on
        elif dati_mqtt_semaforo.get('giallo'):
            giallo = giallo_on
        else:
            verde = verde_on
    else:
        if livello_rischio == 2:
            rosso = rosso_on
        elif livello_rischio == 1:
            giallo = giallo_on
        else:
            verde = verde_on

    st.markdown(f"""
    <div style="
        background-color: #1f2937; 
        padding: 15px; 
        border-radius: 12px; 
        width: 100%; 
        border: 1px solid #374151;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    ">
        <h4 style="margin-bottom: 15px; color: #e5e7eb; font-size: 1rem;">{tipo_veicolo}</h4>
        <div style="background-color: {rosso}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {rosso if rosso == rosso_on else 'transparent'}; border: 2px solid #111;"></div>
        <div style="background-color: {giallo}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {giallo if giallo == giallo_on else 'transparent'}; border: 2px solid #111;"></div>
        <div style="background-color: {verde}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {verde if verde == verde_on else 'transparent'}; border: 2px solid #111;"></div>
    </div>
    """, unsafe_allow_html=True)

def crea_grafico(dati, y_col, color, title, y_domain=None):
    base = alt.Chart(dati).encode(
        x=alt.X('index', axis=alt.Axis(labels=False, tickOpacity=0, title=None)),
        tooltip=['Time', y_col]
    )
    area = base.mark_area(
        line={'color': color, 'strokeWidth': 2},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color=color, offset=0),
                   alt.GradientStop(color='rgba(255,255,255,0)', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        ),
        interpolate='monotone',
        opacity=0.3
    ).encode(
        y=alt.Y(y_col,
                scale=alt.Scale(domain=y_domain) if y_domain else alt.Scale(zero=False),
                axis=alt.Axis(title=None, labelColor='#9ca3af', gridColor='#374151', domainColor='#374151'))
    )
    return (area.properties(height=180, title=alt.TitleParams(text=title, color='white'))
            .configure_view(stroke=None,fill='transparent')
            .configure(background='transparent').configure_axis(grid=True, gridColor='#374151'))


with data_store.lock:
    mqtt_data = data_store.ultimo_pacchetto_dati

if mqtt_data is None:
    st.warning("**In attesa di dati dal sensore**")
    time.sleep(2)
    st.rerun()

else:
    temperatura = mqtt_data.get('temperatura_celsius', 0.0)
    umidita = mqtt_data.get('umidita_percentuale', 0.0)
    pressione = mqtt_data.get('pressione_hpa', 1013.0)
    luminosita_lux = mqtt_data.get('luminosita_lux', 0)
    livello_acqua = mqtt_data.get('livello_acqua_cm', 0.0)
    semafori = mqtt_data.get('semafori', {})
    cambio_drastico = mqtt_data.get('cambio_drastico', 0) == 1

    sicurezza = livello_allerta(livello_acqua)

    st.markdown(f"""
    <div class="status-banner" style="background: {sicurezza['colore_sfondo']};">
        <div style="font-size: 1.2rem; opacity: 0.8;">STATO SOTTOPASSO</div>
        <div style="font-size: 2.5rem;">{sicurezza['testo']}</div>
        <div>Livello Acqua: {livello_acqua} cm</div>
    </div>
    """, unsafe_allow_html=True)

    if cambio_drastico:
        grafica_card_indicatori("️AGGIORNAMENTO: Rilevato un cambio importante dei valori", "")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        grafica_card_indicatori("Temperatura", f"{temperatura}°")
    with col2:
        grafica_card_indicatori("Umidità", f"{umidita}%")
    with col3:
        grafica_card_indicatori("Pressione [hPa]", f"{pressione}")

    duty_cycle = mqtt_data.get('duty_cycle_luci', 0)
    with col4:
        grafica_card_indicatori(f"Luci - {int(luminosita_lux)} Lux", f"{duty_cycle}%")

    st.divider()

    c_moto, c_auto, c_camion = st.columns(3)


    fallback_rischio_moto = 2 if livello_acqua >= 2 else (1 if livello_acqua >= 1 else 0)
    fallback_rischio_auto = 2 if livello_acqua >= 3 else (1 if livello_acqua >= 2 else 0)
    fallback_rischio_camion = 2 if livello_acqua >= 6 else (1 if livello_acqua >= 5 else 0)

    with c_moto:
        disegna_semaforo("Moto", semafori.get('moto'), fallback_rischio_moto)
    with c_auto:
        disegna_semaforo("Auto", semafori.get('auto'), fallback_rischio_auto)
    with c_camion:
        disegna_semaforo("Camion", semafori.get('camion'), fallback_rischio_camion)

    st.divider()

    if luminosita_lux < 100:
        etichetta = "NOTTE 🌑"
        colore = "#6b7280"
    elif luminosita_lux < 1000:
        etichetta = "NUUVOLOSO / CREPUSCOLO ☁️"
        colore = "#9ca3af"
    elif luminosita_lux < 3000:
        etichetta = "LUCE GIORNO ⛅"
        colore = "#fbbf24"
    else:
        etichetta = "PIENO SOLE ☀️"
        colore = "#f59e0b"

    valore_massimo = min((luminosita_lux / 4000) * 100, 100)

    st.markdown(f"""
    <div style="
        background-color: #1f2937; 
        border: 1px solid #374151;
        padding: 15px; 
        border-radius: 10px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        display: flex;
        align-items: center;
        gap: 15px;
    ">
        <div style="
            font-size: 2.5rem; 
            width: 60px; 
            text-align: center;
            filter: drop-shadow(0 0 10px {colore});
        ">☀️</div>
        <div style="width: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 5px;">
                <span style="color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">Sensore Lux</span>
                <span style="color: {colore}; font-weight: bold; font-size: 1.1rem;">{etichetta}</span>
            </div>
            <div style="background-color: #374151; width: 100%; height: 12px; border-radius: 6px; position: relative; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.6);">
                <div style="
                    width: {valore_massimo}%; 
                    height: 100%; 
                    background: linear-gradient(90deg, #4b5563, #f59e0b, #fbbf24, #fffbeb); 
                    border-radius: 6px;
                    box-shadow: 0 0 15px #fbbf24;
                    transition: width 0.8s ease-in-out;
                "></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 0.8rem; color: #6b7280;">
                <span>0 Lux</span>
                <span style="color: #e5e7eb; font-weight: bold;">{int(luminosita_lux)} Lux Rilevati</span>
                <span>5000 Lux</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    timestamp = datetime.now().strftime('%H:%M:%S')
    st.session_state.storico_letture.append({
        'Tempo': timestamp,
        'Livello': livello_acqua,
        'Temperatura': temperatura,
        'Umidità': umidita,
        'Pressione': pressione
    })
    if len(st.session_state.storico_letture) > 60:
        st.session_state.storico_letture.pop(0)

    dataframe_storico = pd.DataFrame(st.session_state.storico_letture).reset_index()

    if not dataframe_storico.empty:
        c_acqua, c_temp, c_hum, c_press = st.columns(4)
        with c_acqua:
            st.altair_chart(crea_grafico(dataframe_storico, 'Livello', '#3b82f6', 'Livello Idrico (cm)', y_domain=[0, 10]), width="stretch")
        with c_temp:
            st.altair_chart(crea_grafico(dataframe_storico, 'Temperatura', '#ef4444', 'Temperatura (°C)', [-10, 50]), width="stretch")
        with c_hum:
            st.altair_chart(crea_grafico(dataframe_storico, 'Umidità', '#06b6d4', 'Umidità (%)', [0, 100]), width="stretch")
        with c_press:
            st.altair_chart(crea_grafico(dataframe_storico, 'Pressione', '#a855f7', 'Pressione (hPa)', [0, 1030]), width="stretch")

time.sleep(2)
st.rerun()