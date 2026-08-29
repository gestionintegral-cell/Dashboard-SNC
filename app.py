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

def normalizar_nombre_servicio(nombre_hoja):
    """Estandariza los nombres de las hojas del Excel para que los filtros funcionen perfecto."""
    s = str(nombre_hoja).replace("_", " ").strip()
    s_lower = s.lower()
    if "servicio" in s_lower and "cliente" in s_lower: return "Servicio al cliente"
    elif "fonoaudiolog" in s_lower: return "Fonoaudiología"
    elif "laboratorio" in s_lower or "muestra" in s_lower: return "Laboratorio y toma de muestras"
    elif "optometr" in s_lower: return "Optometría"
    elif "espirometr" in s_lower: return "Espirometría"
    elif "psicolog" in s_lower: return "Psicología"
    elif "medicina" in s_lower: return "Medicina preventiva y laboral"
    elif "vacunac" in s_lower: return "Vacunación"
    elif "compras" in s_lower: return "Compras"
    elif "comercial" in s_lower: return "Comercial"
    elif "extramural" in s_lower: return "Extramurales"
    return s.title()

def parse_smart_dates(series):
    """Convierte cualquier formato de fecha a formato estándar, ignorando errores tipográficos."""
    s_dt = pd.to_datetime(series, errors="coerce")
    mask_nat = s_dt.isna() & series.notna()
    if mask_nat.any():
        cleaned_str = series[mask_nat].astype(str).str.replace("–", "-").str.replace("—", "-").str.strip()
        s_dt[mask_nat] = pd.to_datetime(cleaned_str, dayfirst=True, errors="coerce")
    return s_dt

def es_estado_cerrado(val):
    if pd.isna(val): return False
    val_str = str(val).strip().upper().replace("Í", "I").replace("Á", "A").replace("É", "E").replace("Ó", "O").replace("Ú", "U")
    return val_str in ["CERRADA", "CERRADO", "SI", "TRUE", "1"] or "CERRAD" in val_str

def es_afirmativo(val):
    if pd.isna(val): return False
    val_str = str(val).strip().upper().replace("Í", "I").replace("Á", "A").replace("É", "E").replace("Ó", "O").replace("Ú", "U")
    return val_str in ["SI", "S", "TRUE", "1", "YES"]

# ---------------------------------------------------------
# 3. ESTILOS CSS
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
# 4. CARGA DE DATOS CENTRALIZADA
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
        df_hoja["Servicio"] = normalizar_nombre_servicio(hoja) # Normaliza nombres
        registros.append(df_hoja)

    df_total = pd.concat(registros, ignore_index=True)

    # Identificación y parseo de Fechas
    col_fecha = [c for c in df_total.columns if "fecha" in c.lower() and "identificaci" in c.lower()]
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
    st.error(f"No fue posible conectar con la base de datos: {e}")
    st.stop()

# MAPEO DE COLUMNAS CLAVE
col_sede = [c for c in df.columns if "SEDE" in c.upper()]
col_estado = [c for c in df.columns if c.strip().lower() == "estado"]
col_coyuntural = [c for c in df.columns if "requiere acción coyuntural" in c.lower()]
col_incidente = [c for c in df.columns if "incidente" in c.lower()]
col_proceso = [c for c in df.columns if "proceso donde se identifica" in c.lower()]
col_colaborador = [c for c in df.columns if "colaborador que genera" in c.lower()]
col_momento = [c for c in df.columns if "momento de identificación" in c.lower()]
col_desc = [c for c in df.columns if "descripción de la salida no conforme" in c.lower()]

if not col_desc:
    col_desc = [c for c in df.columns if any(p in c.lower() for p in ["descripci", "hallazgo", "detalle", "motivo"]) and "tratamiento" not in c.lower() and "calidad" not in c.lower()]

# ---------------------------------------------------------
# 5. BARRA LATERAL (SIDEBAR) - EL ÚNICO LUGAR PARA FILTRAR
# ---------------------------------------------------------
ruta_logo = buscar_archivo_imagen("logo_colmedicos.png")
if ruta_logo:
    st.sidebar.image(ruta_logo, width=220)
else:
    st.sidebar.markdown("<h2 style='color: #1A2B6D; text-align: center;'>COLMEDICOS</h2>", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Filtros Globales Estratégicos")

# Preparar listas desplegables
sedes_disponibles = sorted(list(df[col_sede[0]].dropna().unique())) if col_sede else []
servicios_disponibles = sorted(list(df["Servicio"].dropna().unique()))
periodos_validos = sorted([str(p) for p in df["Periodo"].unique() if str(p) != "Sin Fecha"])

sedes_sel = st.sidebar.multiselect("🏥 Sede:", sedes_disponibles, placeholder="Mostrar todas...")
servicios_sel = st.sidebar.multiselect("🩺 Servicio / Área:", servicios_disponibles, placeholder="Mostrar todos...")
periodos_sel = st.sidebar.multiselect("📅 Período (Año-Mes):", periodos_validos, placeholder="Mostrar todo el histórico...")

if st.sidebar.button("🔄 Restablecer Filtros", use_container_width=True):
    st.rerun()

# Filtrar el DataFrame Principal
df_f = df.copy()
if sedes_sel and col_sede: df_f = df_f[df_f[col_sede[0]].isin(sedes_sel)]
if servicios_sel: df_f = df_f[df_f["Servicio"].isin(servicios_sel)]
if periodos_sel: df_f = df_f[df_f["Periodo"].astype(str).isin(periodos_sel)]

# Generación segura de texto para la IA
if not df_f.empty:
    df_f["_search_text"] = df_f.astype(str).fillna("").apply(lambda r: " ".join(r), axis=1)
else:
    df_f["_search_text"] = pd.Series(dtype=str)

# ---------------------------------------------------------
# 6. BANNER Y MÉTRICAS GLOBALES
# ---------------------------------------------------------
ruta_banner = buscar_archivo_imagen("banner_colmedicos.png")
banner_b64 = get_base64_image(ruta_banner)

if banner_b64:
    st.markdown(
        f"""
        <div style='background-image: linear-gradient(rgba(26, 43, 109, 0.75), rgba(26, 43, 109, 0.85)), url("data:image/png;base64,{banner_b64}");
        background-size: cover; background-position: center; padding: 30px; border-radius: 10px; color: white; margin-bottom: 25px; box-shadow: 0px 4px 10px rgba(0,0,0,0.15);'>
            <h1 style='font-size: 28px; font-weight: 700; color: #FFFFFF; margin: 0;'>Control de Salidas No Conformes (SNC)</h1>
            <p style='font-size: 15px; color: #FFFFFF; margin-top: 6px;'>Monitoreo del Sistema de Gestión de Calidad | <span style='color: #F58220; font-weight: 600; font-style: italic;'>Las personas son nuestra razón de ser</span></p>
        </div>
        """, unsafe_allow_html=True
    )

if df_f.empty:
    st.warning("⚠️ No se encontraron registros para esta combinación de filtros. Intenta eliminar alguno en la barra lateral.")
    st.stop()

# KPIs
total_eventos = len(df_f)
cerrados = len(df_f[df_f[col_estado[0]].apply(es_estado_cerrado)]) if col_estado else 0
pendientes = total_eventos - cerrados
coyunturales = len(df_f[df_f[col_coyuntural[0]].apply(es_afirmativo)]) if col_coyuntural else 0
incidentes = len(df_f[df_f[col_incidente[0]].apply(es_afirmativo)]) if col_incidente else 0
tasa_cierre = (cerrados / total_eventos * 100) if total_eventos > 0 else 0.0

m1, m2, m3, m4, m5 = st.columns(5)
m1.markdown(f'<div class="metric-card"><div class="metric-title">Total Registros</div><div class="metric-value">{total_eventos}</div></div>', unsafe_allow_html=True)
m2.markdown(f'<div class="metric-card metric-card-accent"><div class="metric-title">Efectividad Cierre</div><div class="metric-value">{tasa_cierre:.1f}%</div></div>', unsafe_allow_html=True)
m3.markdown(f'<div class="metric-card"><div class="metric-title">Pendientes (Abiertas)</div><div class="metric-value">{pendientes}</div></div>', unsafe_allow_html=True)
m4.markdown(f'<div class="metric-card"><div class="metric-title">Acción Coyuntural</div><div class="metric-value">{coyunturales}</div></div>', unsafe_allow_html=True)
m5.markdown(f'<div class="metric-card"><div class="metric-title">Incidentes</div><div class="metric-value">{incidentes}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Segmentación Interna Operacional (Botones de radio)
segmento = st.radio("Filtrar vista actual por estado operacional:", ["Todos los registros", "Pendientes (Abiertas)", "Cerrados", "Con acción coyuntural", "Incidentes"], horizontal=True)
df_v = df_f.copy()
if "Pendientes" in segmento and col_estado: df_v = df_f[~df_f[col_estado[0]].apply(es_estado_cerrado)]
elif segmento == "Cerrados" and col_estado: df_v = df_f[df_f[col_estado[0]].apply(es_estado_cerrado)]
elif segmento == "Con acción coyuntural" and col_coyuntural: df_v = df_f[df_f[col_coyuntural[0]].apply(es_afirmativo)]
elif segmento == "Incidentes" and col_incidente: df_v = df_f[df_f[col_incidente[0]].apply(es_afirmativo)]

if df_v.empty:
    st.info(f"No hay registros clasificados como '{segmento}'.")
    st.stop()

# ---------------------------------------------------------
# 7. NAVEGACIÓN EN PESTAÑAS (TABS)
# ---------------------------------------------------------
t_tiempo, t_procesos, t_personas, t_tabla = st.tabs([
    "📅 Evolución Temporal", 
    "⚠️ Causas y Procesos", 
    "👥 Gestión Colaboradores", 
    "📋 Base de Datos"
])

# ---- PESTAÑA 1: EVOLUCIÓN TEMPORAL ----
with t_tiempo:
    st.markdown("### Histórico de Salidas No Conformes")
    df_valid_time = df_v[df_v["Periodo"] != "Sin Fecha"].copy()
    
    if not df_valid_time.empty:
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            # Gráfico de Barras: Total Acumulado por Mes
            df_tot_mes = df_valid_time.groupby("Periodo").size().reset_index(name="Cantidad").sort_values("Periodo")
            fig_bar = px.bar(df_tot_mes, x="Periodo", y="Cantidad", text="Cantidad", color="Cantidad", color_continuous_scale=["#B3C5E7", "#1A2B6D"], title="Volumen Total por Mes")
            fig_bar.update_traces(textposition="outside")
            fig_bar.update_layout(xaxis_title="Mes / Año", yaxis_title="SNC Reportadas", coloraxis_showscale=False)
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_t2:
            # Gráfico de Líneas: Evolución Desglosada por Servicio
            df_serv_mes = df_valid_time.groupby(["Periodo", "Servicio"]).size().reset_index(name="Eventos").sort_values("Periodo")
            fig_line = px.line(df_serv_mes, x="Periodo", y="Eventos", color="Servicio", markers=True, title="Comportamiento por Área (Línea de Tiempo)")
            fig_line.update_traces(line_width=3, marker_size=8)
            fig_line.update_layout(xaxis_title="Mes / Año", yaxis_title="Eventos", legend_title="Servicio")
            st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No existen registros con una fecha válida para visualizar la evolución temporal.")

# ---- PESTAÑA 2: CAUSAS Y PROCESOS ----
with t_procesos:
    st.markdown("### Análisis Crítico de Fallas")
    col_p1, col_p2 = st.columns(2)

    with col_p1:
        if col_proceso:
            # Ranking de Procesos Críticos
            df_proc_valid = df_v[(df_v[col_proceso[0]].notna()) & (df_v[col_proceso[0]].str.strip() != "nan")]
            if not df_proc_valid.empty:
                df_p = df_proc_valid[col_proceso[0]].value_counts().reset_index().head(10)
                df_p.columns = ["Proceso", "Total SNC"]
                fig_p = px.bar(df_p, x="Total SNC", y="Proceso", orientation="h", text="Total SNC", color="Total SNC", color_continuous_scale=["#B3C5E7", "#1A2B6D"], title="Procesos con Mayor Incidencia")
                fig_p.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
                st.plotly_chart(fig_p, use_container_width=True)
            else:
                st.info("Datos de proceso no disponibles.")

    with col_p2:
        if col_desc:
            # Ranking de Descripciones / Hallazgos
            df_desc_valid = df_v[(df_v[col_desc[0]].notna()) & (df_v[col_desc[0]].str.strip() != "nan")]
            if not df_desc_valid.empty:
                df_d = df_desc_valid[col_desc[0]].value_counts().reset_index().head(8)
                df_d.columns = ["Hallazgo", "Frecuencia"]
                fig_d = px.bar(df_d, x="Frecuencia", y="Hallazgo", orientation="h", text="Frecuencia", color="Frecuencia", color_continuous_scale=["#FFE4C4", "#F58220"], title="Principales Causas / Hallazgos")
                fig_d.update_layout(yaxis={"autorange": "reversed"}, coloraxis_showscale=False)
                st.plotly_chart(fig_d, use_container_width=True)
            else:
                st.info("Descripciones de hallazgos no disponibles.")

# ---- PESTAÑA 3: GESTIÓN DE PERSONAL ----
with t_personas:
    st.markdown("### Impacto por Colaborador y Servicio")
    c1, c2 = st.columns(2)

    with c1:
        if col_colaborador:
            df_colab = df_v[(df_v[col_colaborador[0]].notna()) & (df_v[col_colaborador[0]].str.strip() != "nan")]
            if not df_colab.empty:
                df_c = df_colab[col_colaborador[0]].value_counts().reset_index().head(15)
                df_c.columns = ["Nombre del Colaborador", "Cantidad de SNC Generadas"]
                st.markdown("**Top 15 Colaboradores con más incidencias**")
                st.dataframe(df_c, use_container_width=True, hide_index=True)

    with c2:
        df_serv_dist = df_v["Servicio"].value_counts().reset_index()
        df_serv_dist.columns = ["Servicio", "Total"]
        fig_pie = px.pie(df_serv_dist, names="Servicio", values="Total", hole=0.4, title="Distribución de SNC por Servicio", color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig_pie, use_container_width=True)

# ---- PESTAÑA 4: BASE DE DATOS ----
with t_tabla:
    st.markdown("### Consolidado de Registros en Formato Tabla")
    df_export = df_v.drop(columns=["_search_text"], errors="ignore")
    csv = df_export.to_csv(index=False).encode("utf-8")
    st.download_button(label="📥 Descargar datos filtrados a Excel (CSV)", data=csv, file_name="snc_colmedicos.csv", mime="text/csv")
    st.dataframe(df_export, use_container_width=True)


# ---------------------------------------------------------
# 8. CHATBOT FLOTANTE DE IA
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

                palabras_ignorar = {"que", "del", "los", "las", "por", "con", "para", "documento", "cedula", "nit", "numero", "snc", "colmedicos", "hola", "como", "deberia", "tratar", "esta", "plan", "accion", "recomiendas", "genero", "generó", "este", "quien", "quienes", "mas", "incidencias", "usuarios", "colaboradores"}
                tokens = re.findall(r"\b[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+\b", user_prompt)
                terminos_busqueda = [t.lower() for t in tokens if t.lower() not in palabras_ignorar and len(t) >= 3]

                coincidencias = pd.DataFrame()
                if terminos_busqueda and not df_f.empty:
                    pattern = "|".join(terminos_busqueda)
                    coincidencias = df_f[df_f["_search_text"].str.contains(pattern, case=False, na=False)]

                resumen_colaboradores = ""
                if col_colaborador and not df_f.empty:
                    top_colab = df_f[col_colaborador[0]].value_counts().head(3).to_dict()
                    resumen_colaboradores = "\nTOP COLABORADORES CON MÁS CASOS:\n" + "\n".join([f"- {k}: {v}" for k, v in top_colab.items()])

                resumen_servicios = ""
                if not df_f.empty:
                    top_serv = df_f["Servicio"].value_counts().head(3).to_dict()
                    resumen_servicios = "\nTOP SERVICIOS CON MÁS CASOS:\n" + "\n".join([f"- {k}: {v}" for k, v in top_serv.items()])

                contexto_especifico = ""
                if not coincidencias.empty:
                    cols_limpias = [c for c in df_f.columns if c not in ["Fecha_DT", "Periodo", "_search_text"]]
                    registros_encontrados = coincidencias[cols_limpias].head(3).to_dict(orient="records")
                    contexto_especifico = "\n\nREGISTROS ENCONTRADOS:\n"
                    for idx, reg in enumerate(registros_encontrados, 1):
                        contexto_especifico += f"\n--- Caso #{idx} ---\n" + "\n".join([f"- {k}: {v}" for k, v in reg.items() if pd.notna(v) and str(v).strip() != ""])

                contexto_snc = f"""
                Eres el Asistente de Gestión de Calidad (SNC) de COLMEDICOS.
                Responde de forma concisa, directa y estructurada.
                DATOS DE LA SESIÓN:
                - Registros: {len(df_f)} | Tasa Cierre: {tasa_cierre:.1f}%
                - Pendientes: {pendientes} | Cerrados: {cerrados}
                {resumen_colaboradores}
                {resumen_servicios}
                {contexto_especifico}
                """

                try:
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    prompt_completo = f"{contexto_snc}\n\nPregunta: {user_prompt}"

                    with st.chat_message("assistant"):
                        response_stream = model.generate_content(prompt_completo, stream=True)
                        def stream_generator():
                            for chunk in response_stream: yield chunk.text
                        full_response = st.write_stream(stream_generator)

                    st.session_state.gemini_messages.append({"role": "assistant", "content": full_response})
                except Exception as err:
                    st.error(f"Error al procesar la respuesta con la IA: {err}")
        except Exception as e:
            st.error("API Key inválida o no configurada correctamente.")
