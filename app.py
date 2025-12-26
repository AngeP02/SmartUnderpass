import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
import threading
import math
import pandas as pd
import altair as alt
from datetime import datetime

# --- CONFIGURAZIONE MQTT ---
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "angelica/iot/data"
CLIENT_ID = "dashboard_angelica_final_v2"

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Smart Underpass | Real-Time",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZZATO ---
st.markdown("""
<style>
    /* Sfondo generale e font */
    .stApp {
        background-color: #284451;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* KPI Cards */
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

    /* Banner di Stato */
    .status-banner {
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }

    /* Titoli */
    h3, h4, h6 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


# --- STORAGE GLOBALE THREAD-SAFE ---
class MQTTDataStore:
    def __init__(self):
        self.last_data = None
        self.last_update = None
        self.message_count = 0
        self.lock = threading.Lock()


if 'data_store' not in st.session_state:
    st.session_state.data_store = MQTTDataStore()

if 'history' not in st.session_state:
    st.session_state.history = []

data_store = st.session_state.data_store


# --- FUNZIONI MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC)
    else:
        st.error(f"Connessione fallita codice: {rc}")


def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        data = json.loads(payload)
        with data_store.lock:
            data_store.last_data = data
            data_store.last_update = time.time()
            data_store.message_count += 1
    except Exception as e:
        print(f"Errore parsing: {e}")


@st.cache_resource
def start_mqtt():
    client = mqtt.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_start()
        return client
    except Exception as e:
        return None


client = start_mqtt()


# --- HELPER FUNZIONI ---
def calcola_dew_point(T, RH):
    a, b = 17.27, 237.7
    try:
        alpha = ((a * T) / (b + T)) + math.log(RH / 100.0)
        return round((b * alpha) / (a - alpha), 1)
    except:
        return 0.0


def get_stato_sicurezza(h):
    if h >= 4.0: return {"status": "CHIUSURA TOTALE", "bg": "linear-gradient(90deg, #7f1d1d, #ef4444)"}
    if h >= 3.0: return {"status": "STOP AUTO/MOTO", "bg": "linear-gradient(90deg, #7c2d12, #f97316)"}
    if h >= 2.0: return {"status": "CRITICITÀ MODERATA", "bg": "linear-gradient(90deg, #713f12, #eab308)"}
    if h >= 1.0: return {"status": "ATTENZIONE", "bg": "linear-gradient(90deg, #1e3a8a, #3b82f6)"}
    return {"status": "SISTEMA AGIBILE", "bg": "linear-gradient(90deg, #064e3b, #10b981)"}


def kpi_card(label, value, sub="", icon=""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# --- FUNZIONE SEMAFORO (RIPRISTINATA) ---
def draw_traffic_light(vehicle_type, state_dict=None, risk_level=0):
    """
    Disegna il semaforo.
    - state_dict: Dizionario opzionale {rosso: bool, giallo: bool...} da MQTT
    - risk_level: Intero (0=Verde, 1=Giallo, 2=Rosso) usato se state_dict manca
    """

    # Colori spenti (dark)
    off_red = "#440000"
    off_yellow = "#443300"
    off_green = "#003311"

    # Colori accesi
    on_red = "#ff4b4b"
    on_yellow = "#ffaa00"
    on_green = "#00cc44"

    # Determina stato colori
    r, y, g = off_red, off_yellow, off_green

    if state_dict:
        # Usa dati MQTT
        if state_dict.get('rosso'):
            r = on_red
        elif state_dict.get('giallo'):
            y = on_yellow
        else:
            g = on_green
    else:
        # Fallback su logica locale
        if risk_level == 2:
            r = on_red
        elif risk_level == 1:
            y = on_yellow
        else:
            g = on_green

    # HTML Semaforo (Stile Card Scuro)
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
        <h4 style="margin-bottom: 15px; color: #e5e7eb; font-size: 1rem;">{vehicle_type}</h4>
        <div style="background-color: {r}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {r if r == on_red else 'transparent'}; border: 2px solid #111;"></div>
        <div style="background-color: {y}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {y if y == on_yellow else 'transparent'}; border: 2px solid #111;"></div>
        <div style="background-color: {g}; width: 50px; height: 50px; border-radius: 50%; margin: 8px auto; box-shadow: 0 0 10px {g if g == on_green else 'transparent'}; border: 2px solid #111;"></div>
    </div>
    """, unsafe_allow_html=True)


# Grafici Altair Trasparenti
def make_smooth_chart(data, y_col, color, title, y_domain=None):
    base = alt.Chart(data).encode(
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
    # Rimosso use_container_width deprecato dall'oggetto chart, gestito da st.altair_chart
    return area.properties(height=180, title=alt.TitleParams(text=title, color='white')).configure_view(stroke=None,
                                                                                                        fill='transparent').configure(
        background='transparent').configure_axis(grid=True, gridColor='#374151')


# 1. Recupero Dati
with data_store.lock:
    mqtt_data = data_store.last_data

if mqtt_data is None:
    st.info("📡 **In attesa di dati dal sensore IoT...**")
    st.caption("Assicurati che il gateway seriale sia attivo e il nodo TelosB stia trasmettendo.")
    time.sleep(2)
    st.rerun()

else:
    # 2. Parsing Variabili
    temp = mqtt_data.get('temperatura_celsius', 0.0)
    hum = mqtt_data.get('umidita_percentuale', 0.0)
    press = mqtt_data.get('pressione_hpa', 1013.0)
    lux = mqtt_data.get('luminosita_lux', 0)
    level = mqtt_data.get('livello_acqua_cm', 0.0)
    sem = mqtt_data.get('semafori', {})  # Dizionario semafori
    # Nel parsing variabili
    is_drastic = mqtt_data.get('cambio_drastico', 0) == 1



    dew_point = calcola_dew_point(temp, hum)
    sicurezza = get_stato_sicurezza(level)

    # 3. HEADER
    st.markdown(f"""
    <div class="status-banner" style="background: {sicurezza['bg']};">
        <div style="font-size: 1.2rem; opacity: 0.8;">STATO SOTTOPASSO</div>
        <div style="font-size: 2.5rem;">{sicurezza['status']}</div>
        <div>Livello Acqua: {level} cm</div>
    </div>
    """, unsafe_allow_html=True)
    # Nella UI (magari vicino al timestamp o nel banner)
    if is_drastic:
        kpi_card("️AGGIORNAMENTO: Rilevato un cambio importante dei valori!", "")
    # 4. KPI METEO
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card("Temperatura", f"{temp}°")
    with col2:
        kpi_card("Umidità", f"{hum}%")
    with col3:
        kpi_card("Pressione [hPa]", f"{press}")

    duty_cycle = mqtt_data.get('duty_cycle_luci', 0)
    with col4:
        kpi_card(f"Luci - {int(lux)} Lux", f"{duty_cycle}%")

    st.divider()
    # 5. SEMAFORI (Versione Grafica a Cerchi)
    c_moto, c_auto, c_suv = st.columns(3)

    # Determina livelli di rischio fallback se mancano dati semaforo
    # 0=Verde, 1=Giallo, 2=Rosso
    risk_moto = 2 if level >= 2 else (1 if level >= 1 else 0)
    risk_auto = 2 if level >= 3 else (1 if level >= 2 else 0)
    risk_suv = 2 if level >= 6 else (1 if level >= 5 else 0)

    with c_moto:
        # Passiamo l'oggetto sem['moto'] se esiste, altrimenti usa il risk_level calcolato
        draw_traffic_light("Moto", sem.get('moto'), risk_moto)

    with c_auto:
        draw_traffic_light("Auto", sem.get('auto'), risk_auto)

    with c_suv:
        # Nota: nel JSON potresti avere 'camion' o 'mezzi_pesanti', verifica la chiave
        draw_traffic_light("Camion", sem.get('camion'), risk_suv)

    st.divider()
    # Definiamo un'etichetta testuale basata sui Lux per dare contesto
    if lux < 100:
        lux_label = "NOTTE 🌑"
        lux_color = "#6b7280"  # Grigio
    elif lux < 1000:
        lux_label = "NUUVOLOSO / CREPUSCOLO ☁️"
        lux_color = "#9ca3af"  # Grigio chiaro
    elif lux < 3000:
        lux_label = "LUCE GIORNO ⛅"
        lux_color = "#fbbf24"  # Giallo scuro
    else:
        lux_label = "PIENO SOLE ☀️"
        lux_color = "#f59e0b"  # Arancio/Oro vivo

    # Sun Meter "Card Style" (Accattivante e Professionale)
    width_pct = min((lux / 4000) * 100, 100)

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
            filter: drop-shadow(0 0 10px {lux_color});
        ">☀️</div>
        <div style="width: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 5px;">
                <span style="color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">Sensore Lux</span>
                <span style="color: {lux_color}; font-weight: bold; font-size: 1.1rem;">{lux_label}</span>
            </div>
            <div style="background-color: #374151; width: 100%; height: 12px; border-radius: 6px; position: relative; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.6);">
                <div style="
                    width: {width_pct}%; 
                    height: 100%; 
                    background: linear-gradient(90deg, #4b5563, #f59e0b, #fbbf24, #fffbeb); 
                    border-radius: 6px;
                    box-shadow: 0 0 15px #fbbf24;
                    transition: width 0.8s ease-in-out;
                "></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 5px; font-size: 0.8rem; color: #6b7280;">
                <span>0 Lux</span>
                <span style="color: #e5e7eb; font-weight: bold;">{int(lux)} Lux Rilevati</span>
                <span>5000 Lux</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # 7. GRAFICI STORICI
    timestamp = datetime.now().strftime('%H:%M:%S')
    st.session_state.history.append({
        'Time': timestamp,
        'Livello': level,
        'Temperatura': temp,
        'Umidità': hum,
        'Pressione': press
    })
    if len(st.session_state.history) > 60: st.session_state.history.pop(0)

    df_history = pd.DataFrame(st.session_state.history).reset_index()

    if not df_history.empty:
        c_acqua, c_temp, c_hum, c_press = st.columns(4)
        with c_acqua:
            st.altair_chart(make_smooth_chart(df_history, 'Livello', '#3b82f6', '🌊 Livello Idrico (cm)', y_domain=[0, 10]),width="stretch")
        with c_temp:
            st.altair_chart(make_smooth_chart(df_history, 'Temperatura', '#ef4444', 'Temperatura (°C)', [-10, 50]),width="stretch")
        with c_hum:
            st.altair_chart(make_smooth_chart(df_history, 'Umidità', '#06b6d4', 'Umidità (%)', [0, 100]),width="stretch")
        with c_press:
            st.altair_chart(make_smooth_chart(df_history, 'Pressione', '#a855f7', 'Pressione (hPa)', [0, 1030]),width="stretch")

time.sleep(2)
st.rerun()