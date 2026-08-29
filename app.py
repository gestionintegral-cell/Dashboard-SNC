import base64
import os
import re
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


def parse_smart_dates(series):
    """Parsea inteligentemente fechas mixtas en formato YYYY-MM-DD o DD-MM-YYYY."""
    s_dt = pd.to_datetime(series, errors="coerce")
    mask_nat = s_dt.isna() & series.notna()
    if mask_nat.any():
        cleaned_str = (
            series[mask_nat]
            .astype(str)
            .str.replace("–", "-")
            .str.replace("—", "-")
            .str.strip()
        )
        s_dt[mask_nat] = pd.to_datetime(cleaned_str, dayfirst=True, errors="coerce")
    return s_dt


def es_estado_cerrado(val):
    if pd.isna(val):
        return False
    val_str = (
        str(val)
        .strip()
        .upper()
        .replace("Í", "I")
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )
    return val_str in ["CERRADA", "CERRADO", "SI", "TRUE", "1"] or "CERRAD" in val_str


def es_afirmativo(val):
    if pd.isna(val):
        return False
    val_str = (
        str(val)
        .strip()
        .upper()
        .replace("Í", "I")
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Ó", "O")
        .replace("Ú", "U")
    )
    return val_str in ["SI", "S", "TRUE", "1", "YES"]


# ---------------------------------------------------------
# 3. ESTILOS CSS PERSONALIZADOS Y BOTÓN CHAT FLOTANTE
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    /* Tarjetas de métricas */
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

    /* Fijar contenedor del Popover flotante a la derecha abajo */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 30px !important;
        right: 30px !important;
        width: auto !important;
        z-index: 999999 !important;
    }

    div[data-testid="stPopover"] > button {
        width: auto !important;
        min-width: 180px !important;
        background-color: #1A2B6D !important;
        color: white !important;
        border-radius: 30px !important;
        padding: 12px 24px !important;
        font-weight: bold !important;
        box-shadow: 0px 4px 14px rgba(0,0,0,0.3) !important;
        border: 2px solid #FFFFFF !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid="stPopover"] > button:hover {
        background-color: #F58220 !important;
        color: white !important;
        border-color: #FFFFFF !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 4. LOGO EN LA BARRA LATERAL
# ---------------------------------------------------------
ruta_logo = buscar_archivo_imagen("logo_colmedicos.png")
if ruta_logo:
    st.sidebar.image(ruta_logo, width=220)
else:
    st.sidebar.markdown(
        "<h2 style='color: #1A2B6D; text-align: center;'>COLMEDICOS</h2>",
        unsafe_allow_html=True,
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filtros Globales")


# ---------------------------------------------------------
# 5. CARGA Y CONSOLIDACIÓN DINÁMICA DE DATOS
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
        df_hoja["Servicio"] = hoja
        registros.append(df_hoja)

    df_total = pd.concat(registros, ignore_index=True)

    col_fecha = [
        c
        for c in df_total.columns
        if "fecha" in c.lower() and "identificaci" in c.lower()
    ]
    if col_fecha:
        df_total["Fecha_DT"] = parse_smart_dates(df_total[col_fecha[0]])
        df_total["Periodo"] = df_total["Fecha_DT"].dt.strftime("%Y-%m").fillna("Sin Fecha")
    else:
        df_total["Periodo"] = "Sin Fecha"

    for col in df_total.columns:
        if df_total[col].dtype == "object":
            df_total[col] = df_total[col].astype(str)

    return df_total


try:
    df = cargar_base_datos()
except Exception as e:
    st.error(f"No fue posible conectar con la base de datos de Google Sheets: {e}")
    st.stop()

# ---------------------------------------------------------
# 6. MAPEO PRECISO DE COLUMNAS
# ---------------------------------------------------------
col_sede = [c for c in df.columns if "SEDE" in c.upper()]
col_estado = [c for c in df.columns if c.strip().lower() == "estado"]
col_coyuntural = [
    c for c in df.columns if "requiere acción coyuntural" in c.lower()
]
col_incidente = [c for c in df.columns if "incidente" in c.lower()]
col_proceso = [c for c in df.columns if "proceso donde se identifica" in c.lower()]
col_colaborador = [c for c in df.columns if "colaborador que genera" in c.lower()]
col_momento = [c for c in df.columns if "momento de identificación" in c.lower()]

col_desc = [c for c in df.columns if "descripción de la salida no conforme" in c.lower()]
if not col_desc:
    col_desc = [
        c
        for c in df.columns
        if any(p in c.lower() for p in ["descripci", "hallazgo", "detalle", "motivo"])
        and "tratamiento" not in c.lower()
        and "calidad" not in c.lower()
    ]

# ---------------------------------------------------------
# 7. FILTROS GLOBALES UNIFICADOS EN SIDEBAR
# ---------------------------------------------------------
sedes_disponibles = sorted(list(df[col_sede[0]].dropna().unique())) if col_sede else []
servicios_disponibles = sorted(list(df["Servicio"].dropna().unique()))
periodos_validos = sorted([str(p) for p in df["Periodo"].unique() if str(p) != "Sin Fecha"])

sedes_seleccionadas = st.sidebar.multiselect(
    "Sede", sedes_disponibles, default=[], placeholder="Todas las sedes"
)
servicios_seleccionados = st.sidebar.multiselect(
    "Servicio / Área", servicios_disponibles, default=[], placeholder="Todos los servicios"
)
periodos_seleccionados = st.sidebar.multiselect(
    "📅 Período (Año-Mes)", periodos_validos, default=[], placeholder="Todos los meses"
)

if st.sidebar.button("🔄 Restablecer Filtros", use_container_width=True):
    st.rerun()

df_f = df.copy()

# Si el usuario no selecciona ninguna opción en un multiselect, se asume VER TODO.
if sedes_seleccionadas and col_sede:
    df_f = df_f[df_f[col_sede[0]].isin(sedes_seleccionadas)]
if servicios_seleccionados:
    df_f = df_f[df_f["Servicio"].isin(servicios_seleccionados)]
if periodos_seleccionados:
    df_f = df_f[df_f["Periodo"].astype(str).isin(periodos_seleccionados)]

# Asignación segura del texto de búsqueda para el bot IA
if not df_f.empty:
    df_f["_search_text"] = df_f.astype(str).fillna("").apply(lambda r: " ".join(r), axis=1)
else:
    df_f["_search_text"] = pd.Series(dtype=str)

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
# 9. MÉTRICAS Y KPIS PRINCIPALES
# ---------------------------------------------------------
total_eventos = len(df_f)
cerrados = (
    len(df_f[df_f[col_estado[0]].apply(es_estado_cerrado)])
    if col_estado and not df_f.empty
    else 0
)
pendientes = total_eventos - cerrados
coyunturales = (
    len(df_f[df_f[col_coyuntural[0]].apply(es_afirmativo)])
    if col_coyuntural and not df_f.empty
    else 0
)
incidentes = (
    len(df_f[df_f[col_incidente[0]].apply(es_afirmativo)])
    if col_incidente and not df_f.empty
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
        f'<div class="metric-card"><div class="metric-title">Pendientes (Abiertas)</div><div class="metric-value">{pendientes}</div></div>',
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

if df_f.empty:
    st.info("💡 No hay registros para la combinación de filtros seleccionada. Ajusta los filtros en la barra lateral para ver datos.")
    st.stop()

# ---------------------------------------------------------
# 10. SEGMENTACIÓN DE REGISTROS POR ESTADO OPERACIONAL
# ---------------------------------------------------------
segmento = st.radio(
    "Filtrar por estado operacional:",
    [
        "Todos los registros",
        "Pendientes (Abiertas)",
        "Cerrados",
        "Con acción coyuntural",
        "Incidentes",
    ],
    horizontal=True,
)

if "Pendientes" in segmento and col_estado:
    df_v = df_f[~df_f[col_estado[0]].apply(es_estado_cerrado)]
elif segmento == "Cerrados" and col_estado:
    df_v = df_f[df_f[col_estado[0]].apply(es_estado_cerrado)]
elif segmento == "Con acción coyuntural" and col_coyuntural:
    df_v = df_f[df_f[col_coyuntural[0]].apply(es_afirmativo)]
elif segmento == "Incidentes" and col_incidente:
    df_v = df_f[df_f[col_incidente[0]].apply(es_afirmativo)]
else:
    df_v = df_f.copy()

st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 11. PESTAÑAS ESTRUCTURADAS DE NAVEGACIÓN
# ---------------------------------------------------------
t_tiempo, t_procesos, t_personas, t_tabla = st.tabs(
    [
        "📅 Comportamiento Mensual",
        "⚠️ Análisis de Causas y Procesos",
        "👥 Gestión por Colaborador",
        "📋 Consolidado de Registros",
    ]
)

# ---------------------------------------------------------
# PESTAÑA 1: COMPORTAMIENTO MENSUAL (EJE X = MESES YYYY-MM)
# ---------------------------------------------------------
with t_tiempo:
    df_valid_time = df_v[df_v["Periodo"].astype(str) != "Sin Fecha"].copy()
    
    if not df_valid_time.empty:
        col_t1, col_t2 = st.columns(2)

        # Gráfico 1: Total de SNC Mes a Mes
        with col_t1:
            st.markdown("##### Total de Salidas No Conformes Mes a Mes")
            df_tot_mes = (
                df_valid_time.groupby("Periodo")
                .size()
                .reset_index(name="Cantidad")
                .sort_values(by="Periodo")
            )
            fig_tot_mes = px.bar(
                df_tot_mes,
                x="Periodo",
                y="Cantidad",
                text="Cantidad",
                color="Cantidad",
                color_continuous_scale=["#B3C5E7", "#1A2B6D"],
            )
            fig_tot_mes.update_traces(textposition="outside", cliponaxis=False)
            fig_tot_mes.update_layout(
                xaxis_title="Mes / Período",
                yaxis_title="Cantidad de Eventos",
                margin=dict(l=20, r=20, t=20, b=20),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_tot_mes, use_container_width=True)

        # Gráfico 2: Evolución Mensual por Servicio
        with col_t2:
            st.markdown("##### Evolución Mensual Comparativa por Servicio")
            df_serv_mes = (
                df_valid_time.groupby(["Periodo", "Servicio"])
                .size()
                .reset_index(name="Frecuencia")
                .sort_values(by="Periodo")
            )
            fig_serv_mes = px.line(
                df_serv_mes,
                x="Periodo",
                y="Frecuencia",
                color="Servicio",
                markers=True,
                line_shape="linear",
                color_discrete_sequence=px.colors.qualitative.Bold,
            )
            fig_serv_mes.update_traces(line_width=3, marker_size=8)
            fig_serv_mes.update_layout(
                xaxis_title="Mes / Período",
                yaxis_title="Cantidad de Registros",
                legend_title_text="Servicio / Área",
                margin=dict(l=20, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_serv_mes, use_container_width=True)
    else:
        st.info("No hay registros con fecha válida para la selección de filtros actual.")

# ---------------------------------------------------------
# PESTAÑA 2: ANÁLISIS DE CAUSAS Y PROCESOS
# ---------------------------------------------------------
with t_procesos:
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### Top Causas / Hallazgos Recurrentes")
        if col_desc:
            df_d_data = df_v[
                (df_v[col_desc[0]].astype(str).str.strip() != "")
                & (df_v[col_desc[0]].notna())
                & (df_v[col_desc[0]].astype(str) != "nan")
            ].copy()

            if not df_d_data.empty:
                df_d = (
                    df_d_data[col_desc[0]]
                    .value_counts()
                    .reset_index()
                    .head(8)
                )
                df_d.columns = ["Descripción", "Frecuencia"]

                fig_d = px.bar(
                    df_d,
                    x="Frecuencia",
                    y="Descripción",
                    orientation="h",
                    text="Frecuencia",
                    color="Frecuencia",
                    color_continuous_scale=["#FFE4C4", "#F58220"],
                )
                fig_d.update_traces(textposition="outside", cliponaxis=False)
                fig_d.update_layout(
                    yaxis={"autorange": "reversed", "title": ""},
                    xaxis={"title": "Frecuencia Total"},
                    margin=dict(l=20, r=40, t=20, b=20),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_d, use_container_width=True)
            else:
                st.info("No hay descripciones de hallazgos para la selección actual.")
        else:
            st.warning("No se encontró la columna de Descripción de SNC.")

    with col_right:
        st.markdown("##### Incidencias por Proceso / Área")
        if col_proceso:
            df_p_data = df_v[
                (df_v[col_proceso[0]].astype(str).str.strip() != "")
                & (df_v[col_proceso[0]].notna())
                & (df_v[col_proceso[0]].astype(str) != "nan")
            ].copy()

            if not df_p_data.empty:
                df_p = (
                    df_p_data[col_proceso[0]]
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
                    text="Eventos",
                    color="Eventos",
                    color_continuous_scale=["#B3C5E7", "#1A2B6D"],
                )
                fig_p.update_traces(textposition="outside", cliponaxis=False)
                fig_p.update_layout(
                    yaxis={"autorange": "reversed", "title": ""},
                    xaxis={"title": "Cantidad de Eventos"},
                    margin=dict(l=20, r=40, t=20, b=20),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_p, use_container_width=True)
            else:
                st.info("No hay datos registrados para los procesos.")
        else:
            st.warning("No se encontró la columna de Proceso/Área.")

    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
    if col_momento and not df_v.empty:
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

# ---------------------------------------------------------
# PESTAÑA 3: GESTIÓN POR COLABORADOR
# ---------------------------------------------------------
with t_personas:
    p_col1, p_col2 = st.columns(2)

    with p_col1:
        st.markdown("##### Ranking de Eventos por Colaborador")
        if col_colaborador:
            df_c_data = df_v[
                df_v[col_colaborador[0]].notna()
                & (df_v[col_colaborador[0]].astype(str).str.strip() != "")
                & (df_v[col_colaborador[0]].astype(str).str.lower() != "nan")
            ]
            df_c = (
                df_c_data[col_colaborador[0]]
                .value_counts()
                .reset_index()
            )
            df_c.columns = ["Colaborador", "Registros"]

            if not df_c.empty:
                st.dataframe(df_c, use_container_width=True, hide_index=True)
            else:
                st.info("No hay colaboradores registrados para la selección.")
        else:
            st.warning("No se encontró la columna de Colaboradores.")

    with p_col2:
        st.markdown("##### Distribución Porcentual por Servicio")
        if not df_v.empty:
            df_pie_serv = (
                df_v["Servicio"]
                .value_counts()
                .reset_index()
            )
            df_pie_serv.columns = ["Servicio", "Registros"]

            fig_s = px.pie(
                df_pie_serv,
                names="Servicio",
                values="Registros",
                hole=0.4,
                color_discrete_sequence=[
                    "#1A2B6D",
                    "#F58220",
                    "#2A3F90",
                    "#E2E8F0",
                    "#38A169",
                    "#DD6B20",
                ],
            )
            fig_s.update_layout(margin=dict(l=0, r=0, t=20, b=20))
            st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("No hay registros para mostrar.")

# ---------------------------------------------------------
# PESTAÑA 4: TABLA CONSOLIDADA
# ---------------------------------------------------------
with t_tabla:
    st.markdown(f"##### Registros Consolidados ({segmento})")
    df_export = df_v.drop(columns=["_search_text"], errors="ignore")
    csv = df_export.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Exportar vista actual a CSV",
        data=csv,
        file_name="snc_colmedicos.csv",
        mime="text/csv",
    )
    st.dataframe(df_export, use_container_width=True)

# ---------------------------------------------------------
# 12. CHATBOT FLOTANTE INTEGRADOR
# ---------------------------------------------------------
gemini_key = st.secrets.get("GEMINI_API_KEY", "")

with st.popover("💬 Asistente IA SNC"):
    st.markdown("### 🤖 Asistente Virtual SNC")

    if not gemini_key:
        gemini_key = st.text_input(
            "Ingresa tu Gemini API Key:", type="password"
        )

    if gemini_key:
        try:
            genai.configure(api_key=gemini_key)

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

                palabras_ignorar = {
                    "que", "del", "los", "las", "por", "con", "para", "documento",
                    "cedula", "nit", "numero", "snc", "colmedicos", "hola", "como",
                    "deberia", "tratar", "esta", "plan", "accion", "recomiendas",
                    "genero", "generó", "este", "quien", "quienes", "mas", "incidencias",
                    "usuarios", "colaboradores"
                }

                tokens = re.findall(r"\b[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+\b", user_prompt)
                terminos_busqueda = [
                    t.lower()
                    for t in tokens
                    if t.lower() not in palabras_ignorar and len(t) >= 3
                ]

                coincidencias = pd.DataFrame()

                if terminos_busqueda and not df_f.empty:
                    pattern = "|".join(terminos_busqueda)
                    coincidencias = df_f[
                        df_f["_search_text"].str.contains(
                            pattern, case=False, na=False
                        )
                    ]

                resumen_colaboradores = ""
                if col_colaborador and not df_f.empty:
                    top_colab = (
                        df_f[col_colaborador[0]]
                        .value_counts()
                        .head(3)
                        .to_dict()
                    )
                    resumen_colaboradores = "\nTOP COLABORADORES CON MÁS CASOS:\n"
                    for colab, cant in top_colab.items():
                        resumen_colaboradores += f"- {colab}: {cant}\n"

                resumen_servicios = ""
                if not df_f.empty:
                    top_serv = df_f["Servicio"].value_counts().head(3).to_dict()
                    resumen_servicios = "\nTOP SERVICIOS CON MÁS CASOS:\n"
                    for serv, cant in top_serv.items():
                        resumen_servicios += f"- {serv}: {cant}\n"

                contexto_especifico = ""
                if not coincidencias.empty:
                    cols_limpias = [
                        c
                        for c in df_f.columns
                        if c not in ["Fecha_DT", "Periodo", "_search_text"]
                    ]
                    registros_encontrados = coincidencias[cols_limpias].head(
                        3
                    ).to_dict(orient="records")

                    contexto_especifico = "\n\nREGISTROS ENCONTRADOS:\n"
                    for idx, reg in enumerate(registros_encontrados, 1):
                        contexto_especifico += f"\n--- Caso #{idx} ---\n"
                        for k, v in reg.items():
                            if pd.notna(v) and str(v).strip() != "":
                                contexto_especifico += f"- {k}: {v}\n"

                contexto_snc = f"""
                Eres el Asistente de Gestión de Calidad (SNC) de COLMEDICOS.
                Responde de forma concisa, directa y estructurada.
                
                DATOS DE LA SESIÓN:
                - Registros: {len(df_f)} | Tasa Cierre: {tasa_cierre:.1f}%
                - Pendientes (Abiertas): {pendientes} | Cerrados: {cerrados} | Coyunturales: {coyunturales} | Incidentes: {incidentes}
                {resumen_colaboradores}
                {resumen_servicios}
                {contexto_especifico}
                """

                try:
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    prompt_completo = (
                        f"{contexto_snc}\n\nPregunta: {user_prompt}"
                    )

                    with st.chat_message("assistant"):
                        response_stream = model.generate_content(
                            prompt_completo, stream=True
                        )

                        def stream_generator():
                            for chunk in response_stream:
                                yield chunk.text

                        full_response = st.write_stream(stream_generator)

                    st.session_state.gemini_messages.append(
                        {"role": "assistant", "content": full_response}
                    )
                except Exception as err:
                    st.error(f"Error al procesar la respuesta con la IA: {err}")
        except Exception as e:
            st.error("API Key inválida o no configurada correctamente.")
