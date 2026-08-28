import re
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import google.generativeai as genai

# ---------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA STREAMLIT
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dashboard SNC - COLMEDICOS",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Dashboard de Gestión de Calidad (SNC) - COLMEDICOS")

# ---------------------------------------------------------
# 2. CARGA Y CONSOLIDACIÓN DE PESTAÑAS (EXCEL / GOOGLE SHEETS)
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def cargar_datos():
    sheet_id = "1N9So7ddadDxy2TPhpZZUsnqlLUn6my-FvByFg3dOYf0"
    
    try:
        excel_path = "F-CAL-08 Control de salidas no conformes - SNC (1).xlsx"
        xls = pd.ExcelFile(excel_path)
        sheet_names = xls.sheet_names
    except Exception:
        url_excel = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        xls = pd.ExcelFile(url_excel)
        sheet_names = xls.sheet_names

    dfs = []
    for sheet in sheet_names:
        if "matriz" in sheet.lower():
            continue
            
        df_sheet = pd.read_excel(xls, sheet_name=sheet)
        df_sheet.columns = [str(c).strip() for c in df_sheet.columns]
        
        if not df_sheet.empty and len(df_sheet.columns) > 1:
            clean_name = sheet.replace('_', ' ').strip()
            df_sheet["Servicio"] = clean_name
            dfs.append(df_sheet)
            
    if not dfs:
        raise ValueError("No se encontraron pestañas de datos válidas.")

    df_combined = pd.concat(dfs, ignore_index=True)
    return df_combined

try:
    df_raw = cargar_datos()
except Exception as e:
    st.error(f"Error al cargar la base de datos: {e}")
    st.stop()

df = df_raw.copy()

# ---------------------------------------------------------
# 3. NORMALIZACIÓN DE CAMPOS Y COLUMNAS
# ---------------------------------------------------------
# Normalizar Estado
col_estado = next((c for c in df.columns if "estado" in c.lower()), None)
if col_estado:
    df.rename(columns={col_estado: 'Estado'}, inplace=True)
    df['Estado'] = df['Estado'].fillna('SIN REGISTRAR').astype(str).str.strip().str.upper()
    df.loc[df['Estado'] == '', 'Estado'] = 'SIN REGISTRAR'

# Normalizar Sede
col_sede = next((c for c in df.columns if "sede" in c.lower()), None)
if col_sede:
    df['SEDE'] = df[col_sede].fillna('NO ESPECIFICADA').astype(str).str.strip().str.title()

# Normalizar Incidente
col_inc = next((c for c in df.columns if "incidente" in c.lower()), None)
if col_inc:
    df['Incidente'] = df[col_inc].fillna('NO').astype(str).str.strip().str.upper()

# Búsqueda rápida
df['_search_text'] = df.apply(lambda row: ' '.join(row.values.astype(str)), axis=1)
col_colaborador = [c for c in df.columns if 'colaborador' in c.lower() or 'usuario' in c.lower()]

# ---------------------------------------------------------
# 4. FILTROS LATERALES (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("🔍 Filtros de Datos")

servicios_disponibles = sorted(list(df['Servicio'].unique()))
servicio_seleccionado = st.sidebar.multiselect(
    "Filtrar por Servicio / Área:",
    options=servicios_disponibles,
    default=servicios_disponibles
)

estados_disponibles = list(df['Estado'].unique())
estado_seleccionado = st.sidebar.multiselect(
    "Filtrar por Estado:",
    options=estados_disponibles,
    default=estados_disponibles
)

df_f = df[
    (df['Servicio'].isin(servicio_seleccionado)) &
    (df['Estado'].isin(estado_seleccionado))
].copy()

# ---------------------------------------------------------
# 5. CÁLCULO Y MOSTRADO DE MÉTRICAS
# ---------------------------------------------------------
total_registros = len(df_f)
cerrados = (df_f['Estado'] == 'CERRADA').sum()
pendientes = (df_f['Estado'].isin(['ABIERTA', 'SIN REGISTRAR'])).sum()
tasa_cierre = (cerrados / total_registros * 100) if total_registros > 0 else 0.0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Registros", total_registros)
with col2:
    st.metric("Pendientes / Abiertas", pendientes)
with col3:
    st.metric("Cerradas", cerrados)
with col4:
    st.metric("Tasa de Cierre", f"{tasa_cierre:.1f}%")

st.markdown("---")

# ---------------------------------------------------------
# 6. SECCIÓN DE GRÁFICOS E INTERACTIBA (NUEVA SECCIÓN)
# ---------------------------------------------------------
if not df_f.empty:
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("📌 Registros por Servicio")
        df_serv = df_f['Servicio'].value_counts().reset_index()
        df_serv.columns = ['Servicio', 'Cantidad']
        fig_serv = px.bar(
            df_serv, 
            x='Cantidad', 
            y='Servicio', 
            orientation='h',
            text='Cantidad',
            color='Cantidad',
            color_continuous_scale='Blues'
        )
        fig_serv.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_serv, use_container_width=True)

    with col_g2:
        st.subheader("🍩 Distribución por Estado de Gestión")
        df_est = df_f['Estado'].value_counts().reset_index()
        df_est.columns = ['Estado', 'Cantidad']
        fig_est = px.pie(
            df_est, 
            names='Estado', 
            values='Cantidad', 
            hole=0.4,
            color='Estado',
            color_discrete_map={'CERRADA': '#2ca02c', 'SIN REGISTRAR': '#d62728', 'ABIERTA': '#ff7f0e'}
        )
        st.plotly_chart(fig_est, use_container_width=True)

    col_g3, col_g4 = st.columns(2)

    with col_g3:
        st.subheader("⚠️ Top 5 Causales de Salidas No Conformes")
        col_desc = next((c for c in df_f.columns if "descripción" in c.lower() or "descripcion" in c.lower()), None)
        if col_desc:
            top_causas = df_f[col_desc].value_counts().head(5).reset_index()
            top_causas.columns = ['Descripción', 'Cantidad']
            fig_causas = px.bar(
                top_causas, 
                x='Cantidad', 
                y='Descripción', 
                orientation='h',
                text='Cantidad',
                color_discrete_sequence=['#e377c2']
            )
            fig_causas.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_causas, use_container_width=True)

    with col_g4:
        st.subheader("🏢 Registros por Sede")
        if 'SEDE' in df_f.columns:
            df_sede = df_f['SEDE'].value_counts().reset_index()
            df_sede.columns = ['Sede', 'Cantidad']
            fig_sede = px.bar(
                df_sede, 
                x='Sede', 
                y='Cantidad', 
                text='Cantidad',
                color_discrete_sequence=['#1f77b4']
            )
            st.plotly_chart(fig_sede, use_container_width=True)

    # Tabla de datos detallados
    st.markdown("---")
    st.subheader("📋 Detalle de Registros de Salidas No Conformes")
    cols_mostrar = [c for c in df_f.columns if c not in ['_search_text']]
    st.dataframe(df_f[cols_mostrar], use_container_width=True, height=350)

# ---------------------------------------------------------
# 7. CHATBOT FLOTANTE CON IA
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

                palabras_ignorar = {
                    "que", "del", "los", "las", "por", "con", "para", "documento",
                    "cedula", "nit", "numero", "snc", "colmedicos", "hola", "como",
                    "deberia", "tratar", "esta", "plan", "accion", "recomiendas"
                }

                tokens = re.findall(r"\b[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]+\b", user_prompt)
                terminos_busqueda = [t.lower() for t in tokens if t.lower() not in palabras_ignorar and len(t) >= 3]

                coincidencias = pd.DataFrame()
                if terminos_busqueda:
                    pattern = "|".join(terminos_busqueda)
                    coincidencias = df_f[df_f["_search_text"].str.contains(pattern, case=False, na=False)]

                contexto_snc = f"""
                Eres el Asistente de Gestión de Calidad (SNC) de COLMEDICOS.
                DATOS ACTUALES:
                - Total Registros: {total_registros} | Tasa Cierre: {tasa_cierre:.1f}%
                - Pendientes: {pendientes} | Cerradas: {cerrados}
                """

                try:
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
                    st.error(f"Error en la IA: {err}")
        except Exception:
            st.error("API Key no válida.")
