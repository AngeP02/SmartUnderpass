import streamlit as st
import time
import math
import pandas as pd
from datetime import datetime
import altair as alt
import socket
import struct
import threading

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
    .stApp { background-color: #284451; font-family: 'Segoe UI', sans-serif; }
    .kpi-card {
        background-color: #1f2937; border: 1px solid #374151; border-radius: 10px;
        padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .kpi-value { font-size: 2rem; font-weight: 700; color: #f3f4f6; }
    .kpi-label { font-size: 0.9rem; color: #9ca3af; text-transform: uppercase; }
    .kpi-sub { font-size: 0.8rem; color: #6b7280; }
    .vehicle-card {
        background-color: #1f2937; border-radius: 12px; padding: 20px;
        text-align: center; border: 1px solid #374151;
    }
    .status-banner {
        padding: 20px; border-radius: 10px; text-align: center;
        color: white; font-weight: bold; margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    h3, h4, h6 { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)


# --- LETTORE DI RETE (NETWORK READER) ---
class NetworkReader:
    def __init__(self, vm_ip, vm_port=65432):
        self.ip = vm_ip
        self.port = vm_port
        self.sock = None
        self.running = True

        # Dati condivisi (default)
        self.current_data = {
            "temperatura": 0.0, "umidita": 0.0, "pressione": 0.0,
            "luminosita": 0.0, "livello_acqua": 0.0, "livello_stato": 0,
            "scenario": "DISCONNESSO"
        }

        # Thread in background
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
            self.current_data["scenario"] = "CERCO VM..."
            return False

    def _background_reader(self):
        buffer = bytearray()
        while self.running:
            if not self.sock:
                if not self._connect():
                    time.sleep(2)
                    continue

            try:
                chunk = self.sock.recv(1024)
                if not chunk:
                    self.sock.close();
                    self.sock = None;
                    continue

                for byte in chunk:
                    b = byte  # In Python 3 byte è int
                    if b == 0x7E:  # Inizio pacchetto
                        if len(buffer) > 0: self._parse_packet(buffer)
                        buffer = bytearray()
                    else:
                        buffer.append(b)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Errore rete: {e}")
                self.sock = None;
                time.sleep(1)

    def _parse_packet(self, raw_buffer):
        # 1. DE-ESCAPING
        packet = bytearray()
        i = 0
        while i < len(raw_buffer):
            b = raw_buffer[i]
            if b == 0x7D and i + 1 < len(raw_buffer):
                packet.append(raw_buffer[i + 1] ^ 0x20);
                i += 2
            else:
                packet.append(b);
                i += 1

        # 2. VALIDAZIONE (AM_ID = 6)
        if len(packet) < 14: return
        payload_start = len(packet) - 14
        if packet[payload_start - 1] != 6: return
        payload = packet[payload_start: payload_start + 12]

        # 3. DECODIFICA
        try:
            p_raw, t_raw, h_raw, l_raw, lev_raw, stat_raw = struct.unpack('>LhHHBB', payload)

            # Mappatura Livello -> CM
            cm_stimati = 0.0
            if lev_raw == 1:
                cm_stimati = 1.5
            elif lev_raw == 2:
                cm_stimati = 2.5
            elif lev_raw == 3:
                cm_stimati = 4.0
            elif lev_raw == 4:
                cm_stimati = 7.0

            self.current_data = {
                "pressione": p_raw,
                "temperatura": t_raw / 100.0,
                "umidita": h_raw,
                "luminosita": l_raw,
                "livello_acqua": cm_stimati,
                "livello_stato": lev_raw,
                "scenario": "DATI LIVE"
            }
        except Exception:
            pass

    def read_data(self):
        return self.current_data


# --- INIZIALIZZAZIONE ---
if 'reader' not in st.session_state:
    # >>>>> MODIFICA QUI L'IP DELLA TUA MACCHINA VIRTUALE <<<<<
    IP_VM = '192.168.172.141'
    st.session_state.reader = NetworkReader(vm_ip=IP_VM)

if 'history' not in st.session_state: st.session_state.history = []

# --- LETTURA DATI ---
data = st.session_state.reader.read_data()


# Calcolo Dew Point
def calc_dew_point(T, RH):
    a, b = 17.27, 237.7
    try:
        alpha = ((a * T) / (b + T)) + math.log(RH / 100.0)
        return round((b * alpha) / (a - alpha), 1)
    except:
        return 0.0


dew_point = calc_dew_point(data['temperatura'], data['umidita'])


# Logica Sicurezza
def get_sicurezza(h):
    if h >= 6.0: return {"status": "CHIUSURA TOTALE", "bg": "#ef4444", "moto": "STOP", "auto": "STOP"}
    if h >= 3.0: return {"status": "STOP AUTO/MOTO", "bg": "#f97316", "moto": "STOP", "auto": "STOP"}
    if h >= 2.0: return {"status": "CRITICITÀ MODERATA", "bg": "#eab308", "moto": "STOP", "auto": "CRITICO"}
    if h >= 1.0: return {"status": "ATTENZIONE", "bg": "#3b82f6", "moto": "CRITICO", "auto": "OK"}
    return {"status": "SISTEMA AGIBILE", "bg": "#10b981", "moto": "OK", "auto": "OK"}


sicurezza = get_sicurezza(data['livello_acqua'])

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚇 Smart Underpass")
    st.caption(f"Update: {datetime.now().strftime('%H:%M:%S')}")
    st.divider()
    st.markdown(f"📡 **Stato:** `{data['scenario']}`")
    st.markdown(f"🌐 **Bridge IP:** `{st.session_state.reader.ip}`")
    st.divider()
    st.markdown(f"Livello Rilevato (0-4): **{data.get('livello_stato', 0)}**")

# --- UI PRINCIPALE ---
st.markdown(f"""
<div class="status-banner" style="background: {sicurezza['bg']};">
    <div style="font-size: 1.2rem; opacity: 0.8;">STATO SOTTOPASSO</div>
    <div style="font-size: 2.5rem;">{sicurezza['status']}</div>
    <div>Acqua Stimata: {data['livello_acqua']} cm</div>
</div>
""", unsafe_allow_html=True)

# KPI
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

# GRAFICI
st.session_state.history.append({
    'Time': datetime.now().strftime('%H:%M:%S'),
    'Livello': data['livello_acqua'],
    'Temp': data['temperatura'],
    'Umidità': data['umidita']
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
        y=alt.Y('Livello', scale=alt.Scale(domain=[0, 10])),
        tooltip=['Time', 'Livello']
    ).properties(height=200, title="Andamento Livello Acqua")
    st.altair_chart(chart, use_container_width=True)

time.sleep(2)
st.rerun()