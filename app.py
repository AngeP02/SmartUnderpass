import streamlit as st
import time
import random
import math
import pandas as pd
from datetime import datetime
import altair as alt

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Smart Underpass | Dashboard",
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

    /* Veicoli Cards */
    .vehicle-card {
        background-color: #1f2937;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #374151;
        transition: all 0.3s ease;
    }
    .vehicle-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
    }
    .vehicle-icon {
        font-size: 3.5rem;
        margin-bottom: 10px;
        display: block;
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

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Titoli */
    h3, h4, h6 { color: #ffffff !important; }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1f2937;
        border-radius: 5px;
        color: white;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)


# --- SIMULATORE E LOGICA ---
class SmartUnderpassSimulator:
    def __init__(self):
        self.scenario = "SERENO"
        self.water_level = 0.0
        self.campionamento = 1000

    def read_data(self):
        # Cambio scenario casuale
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

        # Dinamica livello acqua
        if self.water_level < target_water:
            self.water_level += 0.5
        elif self.water_level > target_water:
            self.water_level -= 0.5
        self.water_level = max(0.0, round(self.water_level, 1))

        return {
            "temperatura": temp, "umidita": hum, "pressione": press,
            "luminosita": lux, "livello_acqua": self.water_level, "scenario": self.scenario
        }


def calcola_dew_point(T, RH):
    a, b = 17.27, 237.7
    try:
        alpha = ((a * T) / (b + T)) + math.log(RH / 100.0)
        return round((b * alpha) / (a - alpha), 1)
    except:
        return 0.0


def get_stato_sicurezza(h):
    # [cite_start]Logica Tabella 5 [cite: 216]
    if h >= 6.0: return {"status": "CHIUSURA TOTALE", "color": "#ef4444",
                         "bg": "linear-gradient(90deg, #7f1d1d, #ef4444)", "moto": "STOP", "auto": "STOP",
                         "suv": "STOP"}
    if h >= 5.0: return {"status": "CRITICITÀ ELEVATA", "color": "#f97316",
                         "bg": "linear-gradient(90deg, #7c2d12, #f97316)", "moto": "STOP", "auto": "STOP",
                         "suv": "CRITICO"}
    if h >= 3.0: return {"status": "STOP AUTO/MOTO", "color": "#f97316",
                         "bg": "linear-gradient(90deg, #7c2d12, #f97316)", "moto": "STOP", "auto": "STOP", "suv": "OK"}
    if h >= 2.0: return {"status": "CRITICITÀ MODERATA", "color": "#eab308",
                         "bg": "linear-gradient(90deg, #713f12, #eab308)", "moto": "STOP", "auto": "CRITICO",
                         "suv": "OK"}
    if h >= 1.0: return {"status": "ATTENZIONE", "color": "#3b82f6", "bg": "linear-gradient(90deg, #1e3a8a, #3b82f6)",
                         "moto": "CRITICO", "auto": "OK", "suv": "OK"}
    return {"status": "SISTEMA AGIBILE", "color": "#10b981", "bg": "linear-gradient(90deg, #064e3b, #10b981)",
            "moto": "OK", "auto": "OK", "suv": "OK"}


# --- HELPER PER HTML ---
def kpi_card(label, value, sub="", icon=""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{icon} {label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def vehicle_card(tipo, icon, stato, soglia):
    color = "#10b981"  # Verde
    if "CRITICO" in stato: color = "#f59e0b"  # Arancio
    if "STOP" in stato: color = "#ef4444"  # Rosso

    st.markdown(f"""
    <div class="vehicle-card" style="border-top: 4px solid {color};">
        <span class="vehicle-icon">{icon}</span>
        <h3 style="margin:0; color:#e5e7eb;">{tipo}</h3>
        <div style="background-color:{color}; color:white; padding:5px 10px; border-radius:20px; margin:10px auto; display:inline-block; font-weight:bold; font-size:0.9rem;">
            {stato}
        </div>
        <div style="color:#9ca3af; font-size:0.8rem; margin-top:5px;">Soglia: {soglia}</div>
    </div>
    """, unsafe_allow_html=True)


# --- INIT SESSION STATE ---
if 'simulator' not in st.session_state: st.session_state.simulator = SmartUnderpassSimulator()
if 'history' not in st.session_state: st.session_state.history = []

# --- LETTURA DATI ---
data = st.session_state.simulator.read_data()
dew_point = calcola_dew_point(data['temperatura'], data['umidita'])
sicurezza = get_stato_sicurezza(data['livello_acqua'])
campionamento = 500 if sicurezza["status"] != "SISTEMA AGIBILE" else 1000

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚇 Smart Underpass")
    st.markdown("### Monitoraggio Idraulico")
    st.caption(f"Ultimo aggiornamento: {datetime.now().strftime('%H:%M:%S')}")
    st.divider()
    st.markdown("**Dettagli Progetto:**")
    st.markdown("👤 **Studente:** Angelica Porco")
    st.markdown("🎓 **Matricola:** 264034")
    st.markdown("📡 **Nodo Master:** TelosB")
    st.markdown("⚙️ **Attuatore:** Arduino Uno")
    st.divider()
    st.markdown("**Stato Sistema:**")
    st.markdown(f"📶 Connessione: **Ottima** (-54 dBm)")
    st.markdown(f"🔋 Batteria Nodo: **87%**")
    st.markdown(f"⏱️ Freq. Campionamento: **{campionamento}ms**")

# --- MAIN LAYOUT ---

# 1. HEADER
st.markdown(f"""
<div class="status-banner" style="background: {sicurezza['bg']};">
    <div style="font-size: 1.2rem; opacity: 0.8;">STATO SOTTOPASSO</div>
    <div style="font-size: 2.5rem;">{sicurezza['status']}</div>
    <div>Livello Acqua: {data['livello_acqua']} cm</div>
</div>
""", unsafe_allow_html=True)

# 2. KPI METEO
col1, col2, col3, col4 = st.columns(4)
with col1: kpi_card("Temperatura", f"{data['temperatura']}°", f"Dew Point: {dew_point}°", "🌡️")
with col2: kpi_card("Umidità", f"{data['umidita']}%", "Relativa", "💧")
with col3: kpi_card("Pressione", f"{data['pressione']}", "hPa", "⏲️")
lux_pct = "100%" if data['luminosita'] >= 3921 else (
    "70%" if data['luminosita'] >= 980 else ("40%" if data['luminosita'] >= 196 else "10%"))
with col4: kpi_card("Luci", lux_pct, f"{int(data['luminosita'])} Lux", "💡")

st.markdown("### :orange[Controllo Accessi (Real-Time)]")

# 3. VEICOLI
c_moto, c_auto, c_suv = st.columns(3)
with c_moto: vehicle_card("Motocicli", "🛵", sicurezza['moto'], "Stop > 2cm")
with c_auto: vehicle_card("Autovetture", "🚗", sicurezza['auto'], "Stop > 3cm")
with c_suv:  vehicle_card("Mezzi Pesanti", "🚛", sicurezza['suv'], "Stop > 6cm")


# --- SEZIONE GRAFICI E DIAGNOSTICA (MODIFICATA) ---
st.markdown("#### Diagnostica")

# Box Diagnostica (Stile Control Room)
border_color = "#ef4444" if data['livello_acqua'] > 4 else "#10b981"
status_pompe = "🟢  ON (80%)" if data['livello_acqua'] > 4 else "🔴 OFF"
status_sensore = "🟢 ATTIVO" if data['scenario'] == 'TEMPORALE' else "🔴 SLEEP"

st.markdown(f"""
<div style="
    background-color: #98b9c5;
    border-left: 5px solid {border_color};
    padding: 15px;
    border-radius: 5px;
    font-size: 0.9rem;
    line-height: 1.8;
    color: #1f2937;
    margin-bottom: 20px;
">
    <div> Scenario: <b>{data['scenario']}</b></div>
    <div> Sensore: <b>{status_sensore}</b></div>
    <div> Pompe: <b>{status_pompe}</b></div>
</div>
""", unsafe_allow_html=True)

# Creo due colonne: Grafici (Larga) e Dettagli/Luce (Stretta)
# Aggiornamento Storico Dati (Aggiungo TUTTI i parametri per i grafici)
timestamp = datetime.now().strftime('%H:%M:%S')
st.session_state.history.append({
    'Time': timestamp,
    'Livello': data['livello_acqua'],
    'Temperatura': data['temperatura'],
    'Umidità': data['umidita'],
    'Pressione': data['pressione'],
    'Luminosità': data['luminosita']
})
# Mantengo solo ultimi 60 punti
if len(st.session_state.history) > 60: st.session_state.history.pop(0)
df_history = pd.DataFrame(st.session_state.history)


# --- NUOVO GRAFICO LUMINOSITÀ ("SUN METER") ---
st.markdown("#### Intensità Solare")

# Calcolo percentuale per la barra grafica (Max stimato 5000 lux)
lux_val = data['luminosita']
width_pct = min((lux_val / 5000) * 100, 100)

# Creazione della barra personalizzata HTML/CSS
st.markdown(f"""
<div style="
    background-color: #374151;
    width: 100%;
    height: 25px;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
">
    <div style="
        width: {width_pct}%;
        height: 100%;
        background: linear-gradient(90deg, #f59e0b, #fbbf24, #fef3c7);
        transition: width 0.5s ease-in-out;
        box-shadow: 0 0 10px #fbbf24;
    "></div>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #9ca3af; margin-top: 5px;">
    <span>🌑 Buio</span>
    <span>{int(lux_val)} lux</span>
    <span>☀️ Pieno Sole</span>
</div>
""", unsafe_allow_html=True)

st.divider()

timestamp = datetime.now().strftime('%H:%M:%S')
st.session_state.history.append({
    'Time': timestamp,
    'Livello': data['livello_acqua'],
    'Temperatura': data['temperatura'],
    'Umidità': data['umidita'],
    'Pressione': data['pressione'],
    'Luminosità': data['luminosita']
})
if len(st.session_state.history) > 60: st.session_state.history.pop(0)

# Creiamo il DataFrame e aggiungiamo un indice numerico per far scorrere il grafico fluido
df_history = pd.DataFrame(st.session_state.history).reset_index()


def make_smooth_chart(data, y_col, color, title, y_domain=None):
    # Base del grafico
    base = alt.Chart(data).encode(
        x=alt.X('index', axis=alt.Axis(labels=False, tickOpacity=0, title=None)),
        tooltip=['Time', y_col]
    )

    # Area sfumata
    area = base.mark_area(
        line={'color': color, 'strokeWidth': 2},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color=color, offset=0),
                   alt.GradientStop(color='rgba(255,255,255,0)', offset=1)],  # Sfumatura verso trasparente
            x1=1, x2=1, y1=1, y2=0
        ),
        interpolate='monotone',
        opacity=0.3
    ).encode(
        y=alt.Y(y_col,
                scale=alt.Scale(domain=y_domain) if y_domain else alt.Scale(zero=False),
                axis=alt.Axis(title=None, labelColor='#9ca3af', gridColor='#374151', domainColor='#374151'))
    )

    # CONFIGURAZIONE CRUCIALE PER LA TRASPARENZA
    final_chart = area.properties(
        height=180,
        title=alt.TitleParams(text=title, color='white', anchor='start', fontSize=14)
    ).configure_view(
        stroke=None,  # Rimuove il bordo quadrato attorno al grafico
        fill='transparent'  # Sfondo interno trasparente
    ).configure(
        background='transparent'  # Sfondo esterno trasparente
    ).configure_axis(
        grid=True,
        gridColor='#374151'  # Griglia grigio scuro appena visibile
    )

    return final_chart

# Layout: Acqua (Grande) sopra, Meteo (Piccoli) sotto
if not df_history.empty:
    # 1. GRAFICO PRINCIPALE: LIVELLO IDRICO
    # Dominio fisso 0-10cm per vedere bene quando sale
    chart_water = make_smooth_chart(df_history, 'Livello', '#3b82f6', '🌊 Livello Idrico (cm)', y_domain=[0, 10])
    st.altair_chart(chart_water.properties(height=250), use_container_width=True)

    st.divider()

    # 2. GRAFICI METEO (3 Colonne)
    c_temp, c_hum, c_press = st.columns(3)

    with c_temp:
        chart_t = make_smooth_chart(df_history, 'Temperatura', '#ef4444', 'Temperatura (°C)', y_domain=[10, 40])
        st.altair_chart(chart_t, use_container_width=True)

    with c_hum:
        chart_h = make_smooth_chart(df_history, 'Umidità', '#06b6d4', 'Umidità (%)', y_domain=[0, 100])
        st.altair_chart(chart_h, use_container_width=True)

    with c_press:
        # Pressione ha valori alti, non partiamo da 0 altrimenti la linea sembra piatta
        chart_p = make_smooth_chart(df_history, 'Pressione', '#a855f7', 'Pressione (hPa)', y_domain=[980, 1030])
        st.altair_chart(chart_p, use_container_width=True)
# Refresh automatico
time.sleep(2)
st.rerun()