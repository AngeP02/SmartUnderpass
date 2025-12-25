import streamlit as st
import pandas as pd
import json
import time
import os

# Configurazione pagina
st.set_page_config(
    page_title="Smart Underpass Monitor",
    page_icon="🚦",
    layout="wide"
)

# File dove serial_to_mqtt.py salva i dati
DATA_FILE = "underpass_data.json"


def load_data():
    """Legge il file JSON generato dallo script seriale"""
    if not os.path.exists(DATA_FILE):
        return None

    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def draw_traffic_light(vehicle_type, state):
    """Disegna un semaforo stilizzato"""
    # Determina i colori attivi
    color_red = "#ff4b4b" if state['rosso'] else "#440000"
    color_yellow = "#ffaa00" if state['giallo'] else "#443300"
    # Il verde è acceso se nessuno degli altri è acceso (logica dedotta)
    is_green = not (state['rosso'] or state['giallo'])
    color_green = "#00cc44" if is_green else "#003311"

    st.markdown(f"""
    <div style="text-align: center; background-color: #333; padding: 10px; border-radius: 10px; width: 80px; margin: auto;">
        <div style="color: white; font-weight: bold; margin-bottom: 5px;">{vehicle_type}</div>
        <div style="background-color: {color_red}; width: 40px; height: 40px; border-radius: 50%; margin: 5px auto; border: 2px solid #555;"></div>
        <div style="background-color: {color_yellow}; width: 40px; height: 40px; border-radius: 50%; margin: 5px auto; border: 2px solid #555;"></div>
        <div style="background-color: {color_green}; width: 40px; height: 40px; border-radius: 50%; margin: 5px auto; border: 2px solid #555;"></div>
    </div>
    """, unsafe_allow_html=True)


# --- TITOLO ---
st.title("🚦 Smart Underpass Dashboard")

# Contenitore per aggiornamento automatico
placeholder = st.empty()

while True:
    data = load_data()

    with placeholder.container():
        if data is None:
            st.warning("⏳ In attesa di dati dal sensore... (Assicurati che serial_to_mqtt.py sia in esecuzione)")
        else:
            # --- HEADER: STATO E TIMESTAMP ---
            col_stat, col_time = st.columns([2, 1])
            with col_time:
                st.caption(f"Ultimo aggiornamento: {data.get('timestamp', '---')}")
            with col_stat:
                livello = data.get('livello_acqua_cm', 0)
                if livello == 0:
                    st.success("✅ SOTTOPASSO AGIBILE")
                elif livello <= 2:
                    st.warning(f"⚠️ ATTENZIONE: ACQUA {livello} cm")
                else:
                    st.error(f"⛔ ALLAGAMENTO: {livello} cm - CHIUSO")

            st.markdown("---")

            # --- METRICHE SENSORI ---
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("🌡️ Temperatura", f"{data.get('temperatura_celsius', 0)} °C")
            kpi2.metric("💧 Umidità", f"{data.get('umidita_percentuale', 0)} %")
            kpi3.metric("hPa Pressione", f"{data.get('pressione_hpa', 0)}")

            # Mostra anche stato luci
            lux = data.get('luminosita_lux', 0)
            duty = data.get('duty_cycle_luci', 0)
            kpi4.metric("💡 Luminosità", f"{lux} Lux", delta=f"Luci al {duty}%")

            st.markdown("### 🚦 Controllo Traffico")

            # --- SEMAFORI ---
            sem = data.get('semafori', {})
            c1, c2, c3 = st.columns(3)

            if 'moto' in sem:
                with c1: draw_traffic_light("MOTO", sem['moto'])
            if 'auto' in sem:
                with c2: draw_traffic_light("AUTO", sem['auto'])
            if 'camion' in sem:
                with c3: draw_traffic_light("CAMION", sem['camion'])

            # --- GRAFICO LIVELLO ACQUA (Simulato/Singolo valore per ora) ---
            st.markdown("### 🌊 Livello Acqua")
            st.progress(min(livello * 10, 100))  # Scala grafica: 10cm = 100%
            st.text(f"Livello attuale rilevato dagli ultrasuoni: {livello} cm")

    # Aggiorna ogni secondo
    time.sleep(1)