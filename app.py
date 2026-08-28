import base64
import os
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------
# 1. CONFIGURACIÓN PRINCIPAL DE LA INTERFAZ
# ---------------------------------------------------------
st.set_page_config(
    page_title="COLMEDICOS | Control de SNC",
    page_icon="🏥",
    layout="wide",
)


# ---------------------------------------------------------
# 2. FUNCIONES DE APOYO (HELPERS)
# ---------------------------------------------------------
def buscar_archivo_imagen(nombre_base):
    posibles_rutas = [
        nombre_base,
        f".devcontainer/{nombre_base}",
        f"{nombre_base}.png",
        f".devcontainer/{nombre_base}.png",
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            return ruta
    return None


def get_base64_image(ruta_archivo):
    if ruta_archivo and os.path.exists(ruta_archivo):
        with open(ruta_archivo, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""


# ---------------------------------------------------------
# 3. ESTILOS CSS PERSONALIZADOS (IDENTIDAD COLMEDICOS)
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #FFFFFF;
        border-left: 4px solid #1A2B6D;
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0px 2px 6px rgba(0,0,0,0.05);
    }
    .metric-card-accent {
        border-left: 4px solid #F58220 !important;
    }
    .metric-title {
        font-size: 11px;
        color: #64748B;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    .metric-value {
        font-size: 24px;
        color: #1A2B6D;
        font-weight: 800;
        margin-top: 2px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 4. CARGA DEL LOGO EN EL PANEL LATERAL
# ---------------------------------------------------------
ruta_logo = buscar_archivo_imagen("logo_colmedicos.png")
if ruta_logo:
    st.sidebar.image(ruta_logo, use_container_width=True)
else:
    st.sidebar.markdown(
        "<h2 style='color: #1A2B6D; text-align: center;'>COLMEDICOS</h2>",
        unsafe_allow_html=True,
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### Filtros Operativos")


# ---------------------------------------------------------
# 5. CARGA Y CONSOLIDACIÓN DINÁMICA (GOOGLE SHEETS)
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def cargar_base_datos():
    url = "https://docs.google.com/spreadsheets/d/1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0/export?format=xlsx"
    xls = pd.ExcelFile(url)
    registros = []

    for hoja in xls.sheet_names:
        df_hoja = pd.read_excel(xls, sheet_name=hoja)
        df_hoja["Servicio"] = hoja
        registros.append(df_hoja)

    df_total = pd.concat(registros, ignore_index=True)

    # Procesamiento de columna de fechas
    col_fecha = [
        c
        for c in df_total.columns
        if "fecha" in c.lower() and "identificaci" in c.lower()
    ]
    if col_fecha:
        df_total["Fecha_DT"] = pd.to_datetime(
            df_total[col_fecha[0]], errors="coerce"
        )
        df_total["Periodo"] = df_total["Fecha_DT"].dt.to_period("M")

    return df_total


try:
    df = cargar_base_datos()
except Exception as e:
    st.error(f"No fue posible conectar con la base de datos de Google Sheets: {e}")
    st.stop()

# ---------------------------------------------------------
# 6. MAPEO AUTOMÁTICO DE COLUMNAS
# ---------------------------------------------------------
col_sede = [c for c in df.columns if c.upper() == "SEDE"]
col_estado = [
    c for c in df.columns if "estado" in c.lower() or "cerrad" in c.lower()
]
col_coyuntural = [
    c for c in df.columns if "coyuntural" in c.lower() and "Nº" not in c
]
col_incidente = [c for c in df.columns if "incidente" in c.lower()]
col_proceso = [
    c for c in df.columns if "proceso" in c.lower() or "área" in c.lower()
]
col_colaborador = [c for c in df.columns if "colaborador" in c.lower()]
col_momento = [c for c in df.columns if "momento" in c.lower()]
col_desc = [
    c for c in df.columns if "descripci" in c.lower() and "snc" in c.lower()
]

# ---------------------------------------------------------
# 7. FILTROS DINÁMICOS
# ---------------------------------------------------------
sedes_disponibles = list(df[col_sede[0]].dropna().unique()) if col_sede else []
servicios_disponibles = list(df["Servicio"].dropna().unique())

sedes_seleccionadas = st.sidebar.multiselect(
    "Sede", sedes_disponibles, default=sedes_disponibles
)
servicios_seleccionados = st.sidebar.multiselect(
    "Servicio / Área", servicios_disponibles, default=servicios_disponibles
)

df_f = df.copy()
if sedes_seleccionadas and col_sede:
    df_f = df_f[df_f[col_sede[0]].isin(sedes_seleccionadas)]
if servicios_seleccionados:
    df_f = df_f[df_f["Servicio"].isin(servicios_seleccionados)]

# ---------------------------------------------------------
# 8. BANNER INSTITUCIONAL
# ---------------------------------------------------------
ruta_banner = buscar_archivo_imagen("banner_colmedicos.png")
banner_b64 = get_base64_image(ruta_banner)

if banner_b64:
    st.markdown(
        f"""
        <style>
        .custom-banner {{
            background-image: linear-gradient(rgba(26, 43, 109, 0.75), rgba(26, 43, 109, 0.85)), url("data:image/png;base64,{banner_b64}");
            background-size: cover;
            background-position: center;
            padding: 30px;
            border-radius: 10px;
            color: white;
            margin-bottom: 25px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.15);
        }}
        .banner-title {{ font-size: 28px; font-weight: 700; color: #FFFFFF; margin: 0; }}
        .banner-subtitle {{ font-size: 15px; color: #FFFFFF; margin-top: 6px; }}
        .banner-highlight {{ color: #F58220; font-weight: 600; font-style: italic; }}
        </style>
        
        <div class="custom-banner">
            <div class="banner-title">Control de Salidas No Conformes (SNC)</div>
            <div class="banner-subtitle">Monitoreo del Sistema de Gestión de Calidad | <span class="banner-highlight">Las personas son nuestra razón de ser</span></div>
        </div>
    """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="background-color: #1A2B6D; padding: 25px; border-radius: 10px; color: white; margin-bottom: 25px;">
            <h2 style="margin: 0; font-weight: 700;">Control de Salidas No Conformes (SNC)</h2>
            <p style="margin: 6px 0 0 0; color: #FFFFFF;">Monitoreo del Sistema de Gestión de Calidad | <span style="color: #F58220; font-weight: 600; font-style: italic;">Las personas son nuestra razón de ser</span></p>
        </div>
    """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# 9. METRICAS Y KPIS CLAVE
# ---------------------------------------------------------
total_eventos = len(df_f)
cerrados = (
    len(df_f[df_f[col_estado[0]].astype(str).str.upper() == "SÍ"])
    if col_estado
    else 0
)
pendientes = total_eventos - cerrados
coyunturales = (
    len(df_f[df_f[col_coyuntural[0]].astype(str).str.upper() == "SÍ"])
    if col_coyuntural
    else 0
)
incidentes = (
    len(df_f[df_f[col_incidente[0]].astype(str).str.upper() == "SÍ"])
    if col_incidente
    else 0
)
tasa_cierre = (cerrados / total_eventos * 100) if total_eventos > 0 else 0.0

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-title">Total Registros</div><div class="metric-value">{total_eventos}</div></div>',
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f'<div class="metric-card metric-card-accent"><div class="metric-title">Efectividad Cierre</div><div class="metric-value">{tasa_cierre:.1f}%</div></div>',
        unsafe_allow_html=True,
    )
with m3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-title">Pendientes</div><div class="metric-value">{pendientes}</div></div>',
        unsafe_allow_html=True,
    )
with m4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-title">Acción Coyuntural</div><div class="metric-value">{coyunturales}</div></div>',
        unsafe_allow_html=True,
    )
with m5:
    st.markdown(
        f'<div class="metric-card"><div class="metric-title">Incidentes</div><div class="metric-value">{incidentes}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 10. SEGMENTACIÓN DE REGISTROS
# ---------------------------------------------------------
segmento = st.radio(
    "Filtrar por estado operacional:",
    [
        "Todos los registros",
        "Pendientes",
        "Cerrados",
        "Con acción coyuntural",
        "Incidentes",
    ],
    horizontal=True,
)

if segmento == "Pendientes" and col_estado:
    df_v = df_f[df_f[col_estado[0]].astype(str).str.upper() != "SÍ"]
elif segmento == "Cerrados" and col_estado:
    df_v = df_f[df_f[col_estado[0]].astype(str).str.upper() == "SÍ"]
elif segmento == "Con acción coyuntural" and col_coyuntural:
    df_v = df_f[df_f[col_coyuntural[0]].astype(str).str.upper() == "SÍ"]
elif segmento == "Incidentes" and col_incidente:
    df_v = df_f[df_f[col_incidente[0]].astype(str).str.upper() == "SÍ"]
else:
    df_v = df_f.copy()

st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 11. PESTAÑAS DE ANÁLISIS
# ---------------------------------------------------------
t_procesos, t_tiempo, t_personas, t_tabla = st.tabs(
    [
        "Análisis por Proceso / Área",
        "Evolución Temporal",
        "Gestión por Personal",
        "Consolidado de Registros",
    ]
)

with t_procesos:
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("##### Incidencias por Área / Proceso Específico")
        servicio_focal = st.selectbox(
            "Seleccionar servicio a detallar:",
            options=["Todos los servicios"] + list(df_v["Servicio"].unique()),
        )
        df_proc_view = (
            df_v[df_v["Servicio"] == servicio_focal]
            if servicio_focal != "Todos los servicios"
            else df_v.copy()
        )

        if col_proceso:
            df_p = (
                df_proc_view[col_proceso[0]]
                .value_counts()
                .reset_index()
                .head(10)
            )
            df_p.columns = ["Proceso / Área", "Eventos"]
            fig_p = px.bar(
                df_p,
                x="Eventos",
                y="Proceso / Área",
                orientation="h",
                color="Eventos",
                color_continuous_scale=["#B3C5E7", "#1A2B6D"],
            )
            fig_p.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=0, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    with col_right:
        st.markdown("##### Descripción de Hallazgos Recurrentes")
        if col_desc:
            df_d = df_v[col_desc[0]].value_counts().reset_index().head(8)
            df_d.columns = ["Descripción", "Frecuencia"]
            fig_d = px.bar(
                df_d,
                x="Frecuencia",
                y="Descripción",
                orientation="h",
                color="Frecuencia",
                color_continuous_scale=["#FFE4C4", "#F58220"],
            )
            fig_d.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(l=0, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_d, use_container_width=True)

    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
    if col_momento:
        st.markdown("##### Detección del Evento por Etapa del Servicio")
        fig_m = px.histogram(
            df_v,
            x="Servicio",
            color=col_momento[0],
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_m.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_m, use_container_width=True)

with t_tiempo:
    st.markdown("##### Comportamiento Mensual de Registros")
    if "Periodo" in df_v.columns and not df_v["Periodo"].dropna().empty:
        df_t = df_v.groupby("Periodo").size().reset_index(name="Frecuencia")
        df_t["Periodo"] = df_t["Periodo"].astype(str)
        fig_t = px.line(
            df_t,
            x="Periodo",
            y="Frecuencia",
            markers=True,
            line_shape="linear",
        )
        fig_t.update_traces(line_color="#1A2B6D", line_width=3)
        fig_t.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info("No hay suficientes datos temporales cargados.")

with t_personas:
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.markdown("##### Eventos por Colaborador")
        if col_colaborador:
            df_c = (
                df_v[col_colaborador[0]].value_counts().reset_index().head(10)
            )
            df_c.columns = ["Colaborador", "Registros"]
            st.dataframe(df_c, use_container_width=True)

    with p_col2:
        st.markdown("##### Distribución por Servicio")
        fig_s = px.pie(
            df_v,
            names="Servicio",
            hole=0.4,
            color_discrete_sequence=[
                "#1A2B6D",
                "#F58220",
                "#2A3F90",
                "#E2E8F0",
            ],
        )
        fig_s.update_layout(margin=dict(l=0, r=0, t=20, b=20))
        st.plotly_chart(fig_s, use_container_width=True)

with t_tabla:
    st.markdown(f"##### Registros ({segmento})")
    csv = df_v.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Exportar vista a CSV",
        data=csv,
        file_name="snc_colmedicos.csv",
        mime="text/csv",
    )
    st.dataframe(df_v, use_container_width=True)

# ---------------------------------------------------------
# 12. CHATBOT CON IA GRATUITO (Google Gemini)
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🤖 Asistente Virtual SNC")

gemini_key = st.secrets.get("GEMINI_API_KEY", "")

if not gemini_key:
    gemini_key = st.sidebar.text_input(
        "Ingresa tu Gemini API Key:", type="password"
    )

if gemini_key:
    try:
        genai.configure(api_key=gemini_key)

        with st.sidebar.expander("💬 Abrir Chat de Consultas", expanded=False):

            if "gemini_messages" not in st.session_state:
                st.session_state.gemini_messages = []

            for msg in st.session_state.gemini_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_prompt := st.chat_input("Escribe tu pregunta..."):
                st.session_state.gemini_messages.append(
                    {"role": "user", "content": user_prompt}
                )
                with st.chat_message("user"):
                    st.markdown(user_prompt)

                contexto_snc = f"""
                Eres el asistente oficial de Gestión de Calidad de COLMEDICOS.
                Responde únicamente con base en la información consolidada del sistema de Salidas No Conformes (SNC) provista a continuación:
                
                METRICAS GENERALES ACTUALES (FILTRADAS):
                - Total de eventos registrados: {len(df_f)}
                - Efectividad de cierre: {tasa_cierre:.1f}%
                - Casos pendientes por cerrar: {pendientes}
                - Casos cerrados adecuadamente: {cerrados}
                - Acciones coyunturales implementadas: {coyunturales}
                - Incidentes reportados: {incidentes}
                
                MUESTRA REPRESENTATIVA DE REGISTROS ACTUALES:
                {df_f[['Servicio', col_proceso[0] if col_proceso else 'Servicio', col_desc[0] if col_desc else 'Servicio']].head(30).to_string()}
                """

                try:
                    # Se utiliza el identificador universal del modelo para evitar errores 404
                    model = genai.GenerativeModel("gemini-pro")
                    prompt_completo = (
                        f"{contexto_snc}\n\nPregunta del usuario: {user_prompt}"
                    )

                    with st.chat_message("assistant"):
                        response = model.generate_content(prompt_completo)
                        st.markdown(response.text)

                    st.session_state.gemini_messages.append(
                        {"role": "assistant", "content": response.text}
                    )
                except Exception as err:
                    st.error(f"Error al procesar la respuesta con la IA: {err}")
    except Exception as e:
        st.sidebar.error("API Key inválida o no configurada correctamente.")
else:
    st.sidebar.info(
        "💡 Guarda la API Key en Secrets para activar el chat de manera automática."
    )
