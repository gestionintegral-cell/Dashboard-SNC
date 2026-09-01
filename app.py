import base64
import os
import re
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA (WIDE + COLLAPSED SIDEBAR)
# ---------------------------------------------------------
st.set_page_config(
    page_title="COLMEDICOS | Quality Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# 2. CSS PARA LAYOUT Y COMPONENTES TABLER SAAS GRID
# ---------------------------------------------------------
st.markdown("""
    <style>
    /* Ocultar elementos predeterminados de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Contenedor principal con fondo oscuro Slate */
    .stApp {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }
    
    /* Barra Superior de Navegación (Top Navbar) */
    .top-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #1E293B;
        padding: 12px 28px;
        border-bottom: 1px solid #334155;
        margin-bottom: 20px;
        border-radius: 0 0 12px 12px;
    }
    .top-navbar .brand {
        font-size: 18px;
        font-weight: 800;
        color: #60A5FA;
        letter-spacing: 0.5px;
    }

    /* Cards estilo Tabler Grid */
    .tabler-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        height: 100%;
    }
    .tabler-card-header {
        font-size: 11px;
        font-weight: 700;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
    }
    .tabler-card-val {
        font-size: 28px;
        font-weight: 800;
        color: #F8FAFC;
    }
    .tabler-card-sub {
        font-size: 12px;
        color: #10B981;
        font-weight: 600;
    }
    
    /* Ajuste de Tabs horizontales superiores */
    div[data-baseweb="tab-list"] {
        background-color: #1E293B;
        padding: 6px;
        border-radius: 10px;
        border: 1px solid #334155;
        gap: 8px;
    }
    button[data-baseweb="tab"] {
        color: #94A3B8 !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
    }
    
    /* Floating Popover Chatbot */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 25px !important;
        right: 25px !important;
        z-index: 999999 !important;
    }
    div[data-testid="stPopover"] > button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        border-radius: 50px !important;
        padding: 12px 24px !important;
        box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. TOP NAVBAR Y ENCABEZADO SUPERIOR
# ---------------------------------------------------------
st.markdown("""
    <div class="top-navbar">
        <div class="brand">🏥 COLMEDICOS &nbsp;|&nbsp; <span style="font-size: 13px; color: #94A3B8; font-weight: 400;">Control de Salidas No Conformes (SNC)</span></div>
        <div style="font-size: 13px; color: #F97316; font-weight: 600;">Las personas son nuestra razón de ser</div>
    </div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 4. CARGA DE DATOS
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def cargar_base_datos():
    url = "https://docs.google.com/spreadsheets/d/1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0/export?format=xlsx"
    xls = pd.ExcelFile(url)
    registros = []

    for hoja in xls.sheet_names:
        if "matriz" in hoja.lower():
            continue
        df_hoja = pd.read_excel(xls, sheet_name=hoja)
        df_hoja.columns = [str(col).strip() for col in df_hoja.columns]
        col_fecha_check = [c for c in df_hoja.columns if "fecha" in c.lower() and "identificaci" in c.lower()]
        if not col_fecha_check or df_hoja.empty:
            continue
        df_hoja = df_hoja.dropna(subset=col_fecha_check, how="all")
        df_hoja["Servicio"] = hoja.replace("_", " ").strip()
        registros.append(df_hoja)

    df_total = pd.concat(registros, ignore_index=True)
    col_fecha = [c for c in df_total.columns if "fecha" in c.lower() and "identificaci" in c.lower()]
    if col_fecha:
        df_total["Fecha_DT"] = pd.to_datetime(df_total[col_fecha[0]], errors="coerce")
        df_total["Periodo"] = df_total["Fecha_DT"].dt.to_period("M").astype(str)
        df_total["Periodo"] = df_total["Periodo"].replace("NaT", "SIN FECHA")
        df_total[col_fecha[0]] = df_total["Fecha_DT"].dt.strftime("%Y-%m-%d").fillna("")
    return df_total

try:
    df = cargar_base_datos()
except Exception as e:
    st.error(f"Error al cargar datos: {e}")
    st.stop()

col_estado = [c for c in df.columns if c.strip().lower() == "estado"]
col_coyuntural = [c for c in df.columns if "requiere acción coyuntural" in c.lower()]
col_incidente = [c for c in df.columns if "incidente" in c.lower()]
col_proceso = [c for c in df.columns if "proceso donde se identifica" in c.lower()]
col_colaborador = [c for c in df.columns if "colaborador que genera" in c.lower()]
col_desc = [c for c in df.columns if "descripción de la salida no conforme" in c.lower()]

def es_estado_cerrado(val):
    if pd.isna(val): return False
    v = str(val).strip().upper()
    return v in ["CERRADA", "CERRADO", "SI", "TRUE", "1"] or "CERRAD" in v

def es_afirmativo(val):
    if pd.isna(val): return False
    return str(val).strip().upper() in ["SI", "S", "TRUE", "1", "YES"]

# ---------------------------------------------------------
# 5. FILTROS HORIZONTALES SUPERIORES (TOP CONTROL BAR)
# ---------------------------------------------------------
f_col1, f_col2, f_col3, f_col4 = st.columns(4)
with f_col1:
    sedes = sorted(list(df['SEDE'].dropna().unique())) if 'SEDE' in df.columns else []
    sel_sedes = st.multiselect("Sede:", sedes, default=sedes)
with f_col2:
    servicios = sorted(list(df['Servicio'].dropna().unique()))
    sel_servicios = st.multiselect("Servicio / Área:", servicios, default=servicios)
with f_col3:
    periodos = sorted([p for p in df['Periodo'].unique() if p != "SIN FECHA"])
    sel_periodos = st.multiselect("Período:", periodos, default=periodos)
with f_col4:
    segmento = st.selectbox("Estado Operacional:", ["Todos los registros", "Pendientes (Abiertas)", "Cerrados", "Con acción coyuntural", "Incidentes"])

df_f = df.copy()
if sel_sedes and 'SEDE' in df_f.columns:
    df_f = df_f[df_f['SEDE'].isin(sel_sedes)]
if sel_servicios:
    df_f = df_f[df_f['Servicio'].isin(sel_servicios)]
if sel_periodos:
    df_f = df_f[df_f['Periodo'].isin(sel_periodos)]

if "Pendientes" in segmento and col_estado:
    df_v = df_f[~df_f[col_estado[0]].apply(es_estado_cerrado)]
elif segmento == "Cerrados" and col_estado:
    df_v = df_f[df_f[col_estado[0]].apply(es_estado_cerrado)]
else:
    df_v = df_f.copy()

df_f["_search_text"] = df_f.astype(str).fillna("").agg(" ".join, axis=1)

# ---------------------------------------------------------
# 6. FILA DE HERO & KPIS AL ESTILO TABLER SAAS
# ---------------------------------------------------------
total_eventos = len(df_f)
cerrados = len(df_f[df_f[col_estado[0]].apply(es_estado_cerrado)]) if col_estado else 0
pendientes = total_eventos - cerrados
tasa_cierre = (cerrados / total_eventos * 100) if total_eventos > 0 else 0.0

hero_col1, hero_col2, hero_col3 = st.columns([2, 1.2, 1.2])

with hero_col1:
    st.markdown(f"""
        <div class="tabler-card" style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <div style="font-size: 20px; font-weight: 800; color: #F8FAFC;">Bienvenido al Panel de Calidad</div>
                <div style="font-size: 13px; color: #94A3B8; margin-top: 4px;">Monitoreo en tiempo real de salidas no conformes.</div>
                <div style="margin-top: 16px; display:flex; gap: 20px;">
                    <div><span style="font-size: 11px; color:#94A3B8;">REGISTROS</span><br><b style="font-size:18px; color:#60A5FA;">{total_eventos}</b></div>
                    <div><span style="font-size: 11px; color:#94A3B8;">EFECTIVIDAD</span><br><b style="font-size:18px; color:#10B981;">{tasa_cierre:.1f}%</b></div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

with hero_col2:
    # Gráfico de dona de Efectividad Cierre compacto estilo Tabler
    fig_gauge = px.pie(
        values=[cerrados, pendientes],
        names=["Cerradas", "Pendientes"],
        hole=0.7,
        color_discrete_sequence=["#10B981", "#334155"]
    )
    fig_gauge.update_layout(
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(text=f"<b>{tasa_cierre:.0f}%</b>", x=0.5, y=0.5, font_size=20, showarrow=False, font_color="#F8FAFC")]
    )
    st.markdown('<div class="tabler-card"><div class="tabler-card-header">TASA DE CIERRE</div>', unsafe_allow_html=True)
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with hero_col3:
    st.markdown(f"""
        <div class="tabler-card">
            <div class="tabler-card-header">ESTADO OPERACIONAL</div>
            <div style="margin-top: 10px;">
                <div style="display:flex; justify-content:space-between;"><span style="color:#94A3B8;">Cerrados:</span><b style="color:#10B981;">{cerrados}</b></div>
                <div style="display:flex; justify-content:space-between; margin-top:8px;"><span style="color:#94A3B8;">Pendientes:</span><b style="color:#F97316;">{pendientes}</b></div>
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 7. GRID DE ANÁLISIS ESTRUCTURADO (PESTAÑAS TABLER)
# ---------------------------------------------------------
t1, t2, t3, t4 = st.tabs(["📊 Análisis por Proceso", "📈 Evolución Temporal", "👥 Gestión por Personal", "📋 Consolidado"])

with t1:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Incidencias por Área / Proceso")
        if col_proceso:
            df_p = df_v[col_proceso[0]].value_counts().reset_index().head(8)
            df_p.columns = ["Proceso", "Eventos"]
            fig_p = px.bar(df_p, x="Eventos", y="Proceso", orientation="h", text="Eventos", color_discrete_sequence=["#2563EB"])
            fig_p.update_layout(template="plotly_dark", yaxis={"autorange": "reversed"}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_p, use_container_width=True)
    with c2:
        st.markdown("##### Causales Recurrentes")
        if col_desc:
            df_d = df_v[col_desc[0]].value_counts().reset_index().head(8)
            df_d.columns = ["Descripción", "Frecuencia"]
            fig_d = px.bar(df_d, x="Frecuencia", y="Descripción", orientation="h", text="Frecuencia", color_discrete_sequence=["#F97316"])
            fig_d.update_layout(template="plotly_dark", yaxis={"autorange": "reversed"}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_d, use_container_width=True)

with t2:
    st.markdown("##### Comportamiento Mensual de Registros")
    if "Periodo" in df_v.columns and not df_v[df_v["Periodo"] != "SIN FECHA"].empty:
        df_t = df_v[df_v["Periodo"] != "SIN FECHA"].groupby("Periodo").size().reset_index(name="Frecuencia")
        fig_t = px.line(df_t, x="Periodo", y="Frecuencia", markers=True)
        fig_t.update_traces(line_color="#60A5FA", line_width=3)
        fig_t.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_t, use_container_width=True)

with t3:
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("##### Eventos por Colaborador")
        if col_colaborador:
            df_c = df_v[col_colaborador[0]].value_counts().reset_index()
            df_c.columns = ["Colaborador", "Registros"]
            st.dataframe(df_c, use_container_width=True, hide_index=True)
    with p2:
        st.markdown("##### Distribución por Servicio")
        df_pie = df_v["Servicio"].value_counts().reset_index()
        df_pie.columns = ["Servicio", "Registros"]
        fig_pie = px.pie(df_pie, names="Servicio", values="Registros", hole=0.45)
        fig_pie.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

with t4:
    cols_validas = [c for c in df_v.columns if c not in ["Fecha_DT", "Periodo", "_search_text"] and not c.startswith("Unnamed")]
    st.dataframe(df_v[cols_validas], use_container_width=True)

# ---------------------------------------------------------
# 8. CHATBOT FLOTANTE INTEGRADOR CON IA
# ---------------------------------------------------------
gemini_key = st.secrets.get("GEMINI_API_KEY", "")

with st.popover("💬 Asistente IA SNC"):
    st.markdown("### 🤖 Asistente Virtual SNC")
    if not gemini_key:
        gemini_key = st.text_input("Ingresa tu Gemini API Key:", type="password")

    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)
            if "gemini_messages" not in st.session_state:
                st.session_state.gemini_messages = []

            for msg in st.session_state.gemini_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_prompt := st.chat_input("Escribe tu pregunta..."):
                st.session_state.gemini_messages.append({"role": "user", "content": user_prompt})
                with st.chat_message("user"):
                    st.markdown(user_prompt)

                contexto_snc = f"Registros: {len(df_f)} | Tasa Cierre: {tasa_cierre:.1f}% | Pendientes: {pendientes} | Cerrados: {cerrados}"
                model = genai.GenerativeModel("gemini-3.6-flash")
                prompt_completo = f"{contexto_snc}\n\nPregunta: {user_prompt}"

                with st.chat_message("assistant"):
                    response_stream = model.generate_content(prompt_completo, stream=True)
                    def stream_generator():
                        for chunk in response_stream:
                            yield chunk.text
                    full_response = st.write_stream(stream_generator)

                st.session_state.gemini_messages.append({"role": "assistant", "content": full_response})
        except Exception as err:
            st.error(f"Error: {err}")
