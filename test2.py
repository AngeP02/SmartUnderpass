import streamlit as st
import time
import math
import pandas as pd
from datetime import datetime
import altair as alt
import socket
import threading
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Smart Underpass | Dashboard",
    page_icon="🚇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: #284451; font-family: 'Segoe UI', sans-serif; }
    .kpi-card {
        background-color: #1f2937; border: 1px solid #374151; border-radius: 10px;
        padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .kpi-value { font-size: 2rem; font-weight: 700; color: #f3f4f6; }
    .kpi-label { font-size: 0.9rem; color: #9ca3af; text-transform: uppercase; }
    .status-banner {
        padding: 20px; border-radius: 10px; text-align: center;
        color: white; font-weight: bold; margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .vehicle-card {
        background-color: #1f2937; border-radius: 12px; padding: 20px;
        text-align: center; border: 1px solid #374151;
    }
    h3, h4, h6 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


# --- LETTORE DI RETE (VERSIONE TESTUALE) ---
class NetworkReader:
    def __init__(self, vm_ip, vm_port=65432):
        self.ip = vm_ip
        self.port = vm_port
        self.sock = None
        self.running = True

        # Dati condivisi (Default)
        self.current_data = {
            "temperatura": 0.0, "umidita": 0.0, "pressione": 0.0,
            "luminosita": 0.0, "livello_acqua": 0.0, "livello_stato": 0,
            "scenario": "ATTESA DATI..."
        }

        self.thread = threading.Thread(target=self._background_reader)
        self.thread.daemon = True
        self.thread.start()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0)
            self.sock.connect((self.ip, self.port))
            self.current_data["scenario"] = "CONNESSO VM"
            return True
        except Exception:
            self.current_data["scenario"] = "DISCONNESSO"
            return False

    def _background_reader(self):
        buffer = ""
        while self.running:
            if not self.sock:
                if not self._connect():
                    time.sleep(2)
                    continue

            try:
                # 1. Ricevi dati grezzi
                chunk = self.sock.recv(1024)
                if not chunk:
                    self.sock.close();
                    self.sock = None;
                    continue

                # 2. Decodifica testo (ignora caratteri strani)
                text_chunk = chunk.decode('utf-8', errors='ignore')
                buffer += text_chunk

                # 3. Processa riga per riga
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self._parse_line(line.strip())

            except socket.timeout:
                continue
            except Exception as e:
                # print(f"Errore: {e}")
                self.sock = None;
                time.sleep(1)

    def _parse_line(self, line):
        # Parsing basato sulle tue printf in SmartUnderpassC.nc

        # CASO 1: METEO
        # Format: "METEO: %s | P: %lu hPa | T: %d C | RH: %d %%"
        if "METEO:" in line:
            try:
                # Estrai numeri con Regex
                p = re.search(r'P:\s*(\d+)', line)
                t = re.search(r'T:\s*(-?\d+)', line)
                rh = re.search(r'RH:\s*(\d+)', line)

                if p: self.current_data["pressione"] = int(p.group(1))
                if t: self.current_data["temperatura"] = int(t.group(1))
                if rh: self.current_data["umidita"] = int(rh.group(1))

                # Scenario
                if "TEMPORALE" in line:
                    self.current_data["scenario"] = "TEMPORALE"
                elif "PIOGGIA" in line:
                    self.current_data["scenario"] = "PIOGGIA"
                elif "SERENO" in line:
                    self.current_data["scenario"] = "SERENO"
                else:
                    self.current_data["scenario"] = "METEO ATTIVO"
            except:
                pass

        # CASO 2: LUCI
        # Format: "Luci Sottopasso: ... | LUX: %lu ..."
        elif "LUX:" in line:
            try:
                lux = re.search(r'LUX:\s*(\d+)', line)
                if lux: self.current_data["luminosita"] = int(lux.group(1))
            except:
                pass

        # CASO 3: ACQUA
        # Format: "ACQUA: ... Misura=%lu cm -> Livello=%lu"
        elif "Livello=" in line:
            try:
                lev = re.search(r'Livello=(\d+)', line)
                if lev:
                    livello = int(lev.group(1))
                    self.current_data["livello_stato"] = livello

                    # Converti Livello (0-4) in cm visuali per il grafico
                    if livello == 0:
                        self.current_data["livello_acqua"] = 0.0
                    elif livello == 1:
                        self.current_data["livello_acqua"] = 2.0
                    elif livello == 2:
                        self.current_data["livello_acqua"] = 5.0
                    elif livello == 3:
                        self.current_data["livello_acqua"] = 8.0
                    elif livello == 4:
                        self.current_data["livello_acqua"] = 12.0
            except:
                pass

    def read_data(self):
        return self.current_data


# --- INIZIALIZZAZIONE ---
if 'reader' not in st.session_state:
    # >>>>> INSERISCI QUI IL TUO IP DELLA VM <<<<<
    # (Quello che hai trovato con ifconfig, es: 192.168.172.141)
    IP_VM = '192.168.172.141'
    st.session_state.reader = NetworkReader(vm_ip=IP_VM)

if 'history' not in st.session_state: st.session_state.history = []

# --- LETTURA DATI ---
data = st.session_state.reader.read_data()


# --- LOGICA DASHBOARD ---
def get_sicurezza(h):
    # h è il livello stimato in cm
    if h >= 8.0: return {"status": "CHIUSURA TOTALE", "bg": "#ef4444", "moto": "STOP", "auto": "STOP"}
    if h >= 5.0: return {"status": "STOP AUTO/MOTO", "bg": "#f97316", "moto": "STOP", "auto": "STOP"}
    if h >= 2.0: return {"status": "CRITICITÀ MODERATA", "bg": "#eab308", "moto": "STOP", "auto": "CRITICO"}
    return {"status": "SISTEMA AGIBILE", "bg": "#10b981", "moto": "OK", "auto": "OK"}


sicurezza = get_sicurezza(data['livello_acqua'])

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚇 Smart Underpass")
    st.caption(f"Update: {datetime.now().strftime('%H:%M:%S')}")
    st.divider()
    st.markdown(f"📡 **Stato:** `{data['scenario']}`")
    st.markdown(f"💧 **Livello Allerta:** `{data.get('livello_stato', 0)}`")

# --- HEADER ---
st.markdown(f"""
<div class="status-banner" style="background: {sicurezza['bg']};">
    <div style="font-size: 1.2rem; opacity: 0.8;">STATO SOTTOPASSO</div>
    <div style="font-size: 2.5rem;">{sicurezza['status']}</div>
    <div>Livello Acqua Stimato: {data['livello_acqua']} cm</div>
</div>
""", unsafe_allow_html=True)

# --- KPI METEO ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(
    f"<div class='kpi-card'><div class='kpi-label'>🌡️ Temp</div><div class='kpi-value'>{data['temperatura']}°</div></div>",
    unsafe_allow_html=True)
with c2: st.markdown(
    f"<div class='kpi-card'><div class='kpi-label'>💧 Umidità</div><div class='kpi-value'>{data['umidita']}%</div></div>",
    unsafe_allow_html=True)
with c3: st.markdown(
    f"<div class='kpi-card'><div class='kpi-label'>⏲️ Press</div><div class='kpi-value'>{data['pressione']}</div></div>",
    unsafe_allow_html=True)
with c4: st.markdown(
    f"<div class='kpi-card'><div class='kpi-label'>💡 Luci</div><div class='kpi-value'>{data['luminosita']}</div></div>",
    unsafe_allow_html=True)

# --- CONTROLLO ACCESSI ---
st.markdown("### :orange[Controllo Accessi]")
c_moto, c_auto = st.columns(2)
with c_moto:
    st.markdown(
        f"<div class='vehicle-card'><h3>🛵 Moto</h3><div style='background:{'#ef4444' if 'STOP' in sicurezza['moto'] else '#10b981'}; padding:5px; border-radius:10px;'>{sicurezza['moto']}</div></div>",
        unsafe_allow_html=True)
with c_auto:
    st.markdown(
        f"<div class='vehicle-card'><h3>🚗 Auto</h3><div style='background:{'#ef4444' if 'STOP' in sicurezza['auto'] else '#10b981'}; padding:5px; border-radius:10px;'>{sicurezza['auto']}</div></div>",
        unsafe_allow_html=True)

# --- GRAFICI ---
st.session_state.history.append({
    'Time': datetime.now().strftime('%H:%M:%S'),
    'Livello': data['livello_acqua'],
    'Temp': data['temperatura']
})
if len(st.session_state.history) > 60: st.session_state.history.pop(0)
df = pd.DataFrame(st.session_state.history).reset_index()

if not df.empty:
    chart = alt.Chart(df).mark_area(
        line={'color': '#3b82f6'},
        color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color='#3b82f6', offset=0),
                                                     alt.GradientStop(color='rgba(255,255,255,0)', offset=1)], x1=1,
                           x2=1, y1=1, y2=0)
    ).encode(
        x=alt.X('index', axis=None),
        y=alt.Y('Livello', scale=alt.Scale(domain=[0, 15])),
        tooltip=['Time', 'Livello']
    ).properties(height=200, title="Andamento Livello Acqua")
    st.altair_chart(chart, use_container_width=True)

time.sleep(1)
st.rerun()