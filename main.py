import streamlit as st
import time
import random
import math
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Smart Underpass IoT",
    page_icon="🚸",
    layout="wide",
    initial_sidebar_state="expanded"
)


class SmartUnderpassSimulator:
    def __init__(self):
        self.scenario = "SERENO"
        self.water_level = 0.0
        self.campionamento = 1000
        self.sensore_livello_attivo = False

    def read_data(self):
        if random.random() < 0.05:
            self.scenario = "TEMPORALE" if self.scenario == "SERENO" else "SERENO"

        if self.scenario == "SERENO":
            temp = round(random.uniform(20.0, 28.0), 1)
            hum = round(random.uniform(30.0, 50.0), 1)
            press = round(random.uniform(1015.0, 1025.0), 1)
            lux = round(random.uniform(2000, 4500), 0)
            target_water = 0.0
        else:
            temp = round(random.uniform(15.0, 19.0), 1)
            hum = round(random.uniform(85.0, 99.0), 1)
            press = round(random.uniform(985.0, 1005.0), 1)
            lux = round(random.uniform(100, 800), 0)
            target_water = 8.0

        if self.water_level < target_water:
            self.water_level += 0.5
        elif self.water_level > target_water:
            self.water_level -= 0.5
        self.water_level = max(0.0, round(self.water_level, 1))

        return {
            "temperatura": temp,
            "umidita": hum,
            "pressione": press,
            "luminosita": lux,
            "livello_acqua": self.water_level,
            "scenario": self.scenario
        }


def calcola_dew_point(T, RH):
    a = 17.27
    b = 237.7
    try:
        alpha = ((a * T) / (b + T)) + math.log(RH / 100.0)
        tdp = (b * alpha) / (a - alpha)
        return round(tdp, 1)
    except:
        return 0.0


def get_stato_meteo(P, RH):
    if P < 1000 and RH > 90:
        return {"stato": "TEMPORALE / NUBIFRAGIO", "rischio": "ALTO", "colore": "rosso"}
    elif P < 1010:
        return {"stato": "PIOGGIA MODERATA", "rischio": "MEDIO", "colore": "arancione"}
    elif P < 1015:
        return {"stato": "NUVOLOSO", "rischio": "BASSO", "colore": "giallo"}
    else:
        return {"stato": "SERENO / STABILE", "rischio": "NULLO", "colore": "verde"}


def get_stato_sicurezza(h):
    if h >= 6.0:
        return {
            "motocicli": {"stato": "STOP", "led": "🔴"},
            "auto": {"stato": "STOP", "led": "🔴"},
            "suv": {"stato": "STOP", "led": "🔴"},
            "messaggio": "BARRIERA CHIUSA - GALLEGGIAMENTO",
            "colore_sfondo": "error",
            "barriera_attiva": True
        }
    elif h >= 5.0:
        return {
            "motocicli": {"stato": "STOP", "led": "🔴"},
            "auto": {"stato": "STOP", "led": "🔴"},
            "suv": {"stato": "CRITICO", "led": "🟠"},
            "messaggio": "ATTENZIONE SUV/CAMION/BUS - CRITICITA",
            "colore_sfondo": "warning",
            "barriera_attiva": False
        }
    elif h >= 3.0:
        return {
            "motocicli": {"stato": "STOP", "led": "🔴"},
            "auto": {"stato": "STOP", "led": "🔴"},
            "suv": {"stato": "SICURO", "led": "🟢"},
            "messaggio": "VIETATO AUTO E MOTOCICLI",
            "colore_sfondo": "warning",
            "barriera_attiva": False
        }
    elif h >= 2.0:
        return {
            "motocicli": {"stato": "STOP", "led": "🔴"},
            "auto": {"stato": "CRITICO", "led": "🟠"},
            "suv": {"stato": "SICURO", "led": "🟢"},
            "messaggio": "CRITICITA PER AUTO E MOTOCICLI",
            "colore_sfondo": "warning",
            "barriera_attiva": False
        }
    elif h >= 1.0:
        return {
            "motocicli": {"stato": "CRITICO", "led": "🟠"},
            "auto": {"stato": "SICURO", "led": "🟢"},
            "suv": {"stato": "SICURO", "led": "🟢"},
            "messaggio": "ATTENZIONE MOTOCICLI",
            "colore_sfondo": "info",
            "barriera_attiva": False
        }
    else:
        return {
            "motocicli": {"stato": "SICURO", "led": "🟢"},
            "auto": {"stato": "SICURO", "led": "🟢"},
            "suv": {"stato": "SICURO", "led": "🟢"},
            "messaggio": "SOTTOPASSO AGIBILE - TUTTI I VEICOLI",
            "colore_sfondo": "success",
            "barriera_attiva": False
        }


def get_livello_luci(lux):
    if lux >= 3921:
        return "100%"
    elif lux >= 980:
        return "70%"
    elif lux >= 196:
        return "40%"
    else:
        return "10%"


def get_campionamento_adattivo(stato_meteo):
    if stato_meteo["rischio"] in ["ALTO", "MEDIO"]:
        return 500
    else:
        return 1000


if 'simulator' not in st.session_state:
    st.session_state.simulator = SmartUnderpassSimulator()
if 'history' not in st.session_state:
    st.session_state.history = []

data = st.session_state.simulator.read_data()

dew_point = calcola_dew_point(data['temperatura'], data['umidita'])
stato_meteo = get_stato_meteo(data['pressione'], data['umidita'])
stato_sicurezza = get_stato_sicurezza(data['livello_acqua'])
livello_luci = get_livello_luci(data['luminosita'])
campionamento = get_campionamento_adattivo(stato_meteo)
sensore_attivo = stato_meteo['rischio'] != 'NULLO'

st.session_state.simulator.campionamento = campionamento
st.session_state.simulator.sensore_livello_attivo = sensore_attivo

# Header principale
st.title("Smart Underpass - IoT System")
st.markdown("**Monitoraggio Idraulico e Sicurezza Stradale - Prototipo TelosB**")

# Indicatori tempo reale
col_status1, col_status2 = st.columns(2)
with col_status1:
    st.metric("Campionamento", f"{campionamento}ms",
              "ADATTIVO" if campionamento == 500 else "NORMALE")
with col_status2:
    st.metric("Sensore Livello Acqua",
              "ATTIVO" if sensore_attivo else "STANDBY",
              "Pioggia prevista" if sensore_attivo else "")

st.divider()

# Stato sicurezza principale
if stato_sicurezza['colore_sfondo'] == "error":
    st.error(f"### {stato_sicurezza['messaggio']}")
    if stato_sicurezza['barriera_attiva']:
        st.error("### BARRIERA FISICA ATTIVATA")
elif stato_sicurezza['colore_sfondo'] == "warning":
    st.warning(f"### {stato_sicurezza['messaggio']}")
elif stato_sicurezza['colore_sfondo'] == "info":
    st.info(f"### {stato_sicurezza['messaggio']}")
else:
    st.success(f"### {stato_sicurezza['messaggio']}")

st.divider()

# Gestione accessi per categoria
st.subheader("Gestione Accessi Veicolare Differenziata")
col_moto, col_auto, col_suv = st.columns(3)

with col_moto:
    st.markdown("### Motocicli")
    st.markdown(f"<div style='text-align: center; font-size: 4rem;'>{stato_sicurezza['motocicli']['led']}</div>",
                unsafe_allow_html=True)
    st.write(f"**Stato:** {stato_sicurezza['motocicli']['stato']}")
    st.caption("Critico: 1cm | Stop: 2cm")

with col_auto:
    st.markdown("### Autovetture")
    st.markdown(f"<div style='text-align: center; font-size: 4rem;'>{stato_sicurezza['auto']['led']}</div>",
                unsafe_allow_html=True)
    st.write(f"**Stato:** {stato_sicurezza['auto']['stato']}")
    st.caption("Critico: 2cm | Stop: 3cm")

with col_suv:
    st.markdown("### SUV/Camion/Bus")
    st.markdown(f"<div style='text-align: center; font-size: 4rem;'>{stato_sicurezza['suv']['led']}</div>",
                unsafe_allow_html=True)
    st.write(f"**Stato:** {stato_sicurezza['suv']['stato']}")
    st.caption("Critico: 5cm | Stop: >6cm")

st.divider()

# Parametri ambientali
col_meteo, col_luce = st.columns(2)

with col_meteo:
    st.subheader("Monitoraggio Meteorologico")

    col_t, col_h = st.columns(2)
    col_t.metric("Temperatura", f"{data['temperatura']}°C", f"Dew Point: {dew_point}°C")
    col_h.metric("Umidita", f"{data['umidita']}%")

    st.metric("Pressione Atmosferica", f"{data['pressione']} hPa")

    if stato_meteo['colore'] == "rosso":
        st.error(f"**{stato_meteo['stato']}** - Rischio: {stato_meteo['rischio']}")
    elif stato_meteo['colore'] == "arancione":
        st.warning(f"**{stato_meteo['stato']}** - Rischio: {stato_meteo['rischio']}")
    elif stato_meteo['colore'] == "giallo":
        st.info(f"**{stato_meteo['stato']}** - Rischio: {stato_meteo['rischio']}")
    else:
        st.success(f"**{stato_meteo['stato']}** - Rischio: {stato_meteo['rischio']}")

with col_luce:
    st.subheader("Sistema Illuminazione Adattiva")
    st.metric("Luminosita Esterna", f"{data['luminosita']} lux")

    st.markdown(f"""
    <div style='background-color: #e3f2fd; padding: 30px; border-radius: 10px; text-align: center; margin: 20px 0;'>
        <p style='margin: 0; color: #666;'>Intensita Luci Sottopasso</p>
        <h1 style='font-size: 4rem; margin: 10px 0; color: #1976d2;'>{livello_luci}</h1>
        <p style='font-size: 0.8rem; color: #666;'>Conforme normativa Ministero Ambiente</p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Tabella Normativa"):
        st.markdown("""
        - L >= 3921 lux: **100%**
        - 980 - 3921 lux: **70%**
        - 196 - 980 lux: **40%**
        - L < 196 lux: **10%**
        """)

st.divider()

# Monitoraggio livello acqua
st.subheader("Monitoraggio Livello Acqua")

col_grafico, col_gauge = st.columns([2, 1])

with col_grafico:
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.history.append({
        'Tempo': timestamp,
        'Livello (cm)': data['livello_acqua']
    })

    if len(st.session_state.history) > 60:
        st.session_state.history.pop(0)

    df_history = pd.DataFrame(st.session_state.history)
    st.line_chart(df_history.set_index('Tempo'), height=300)

with col_gauge:
    livello_pct = min(data['livello_acqua'] / 10.0, 1.0)
    st.metric("Livello Attuale", f"{data['livello_acqua']} cm")
    st.progress(livello_pct)

    st.markdown("**Soglie:**")
    if data['livello_acqua'] >= 6.0:
        st.error("Galleggiamento (6cm) - RAGGIUNTO")
    else:
        st.info("Galleggiamento: 6cm")

    if data['livello_acqua'] >= 5.0:
        st.warning("Soglia SUV (5cm) - SUPERATA")
    else:
        st.info("Soglia SUV: 5cm")

    if data['livello_acqua'] >= 2.0:
        st.warning("Soglia Auto (2cm) - SUPERATA")
    else:
        st.info("Soglia Auto: 2cm")

# Footer
st.divider()
st.caption("Architettura: TelosB (Master) + Arduino (Slave) | Trasmissione: Media 10s / Invio immediato eventi critici")

# Auto-refresh
time.sleep(1)
st.rerun()