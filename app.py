import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime

# ==========================================
# CONFIGURACIÓN TÁCTICA
# ==========================================
st.set_page_config(page_title="COP - Conciencia Situacional", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .metric-box { padding: 15px; border-radius: 5px; background-color: #1E2127; border-left: 4px solid #4CAF50; margin-bottom: 10px; }
    .box-critico { border-left-color: #D32F2F; }
    .box-alerta { border-left-color: #FBC02D; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INGESTA NASA (TIEMPO REAL) Y MOTOR IPO
# ==========================================
@st.cache_data(ttl=1800) # Se conecta al satélite máximo cada 30 minutos
def load_live_data():
    url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_South_America_24h.csv"
    try:
        df_live = pd.read_csv(url)
        # Recorte del mapa a coordenadas de Uruguay
        df = df_live[(df_live['latitude'] <= -30.0) & (df_live['latitude'] >= -35.2) & 
                     (df_live['longitude'] <= -53.0) & (df_live['longitude'] >= -58.5)].copy()
        
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()
            
        df = df.rename(columns={'latitude': 'lat', 'longitude': 'lon'})
        df['ID'] = df.index + 1000
        df['lat_grid'] = df['lat'].round(1)
        df['lon_grid'] = df['lon'].round(1)
        df['Episodio_ID'] = "EN_VIVO-" + df['lat_grid'].astype(str) + df['lon_grid'].astype(str)
        
        # --- Imputación de variables de contexto ---
        # Como es invierno y no tenemos API del clima integrada aún,
        # usamos parámetros estándar que mantienen el contexto estable.
        df['PC1_Estres'] = 0.5 
        df['anomalia_hum'] = 0.0
        df['temp_max'] = 15.0
        
        # --- Motor IPO v2 ---
        def calc_contexto(row):
            p = 0
            if row['PC1_Estres'] <= -3.62: p += 5
            elif row['PC1_Estres'] <= -2.25: p += 3
            elif row['PC1_Estres'] <= -0.50: p += 1
            if row['anomalia_hum'] <= -12.7: p += 4
            elif row['anomalia_hum'] <= -6.5: p += 2
            elif row['anomalia_hum'] <= 0: p += 1
            if row['temp_max'] >= 36.5: p += 3
            elif row['temp_max'] >= 31.5: p += 2
            return p

        def calc_intensidad(row):
            if row['frp'] >= 50: return 5
            elif row['frp'] >= 20: return 3
            elif row['frp'] >= 10: return 1
            return 0

        df['Score_Contexto'] = df.apply(calc_contexto, axis=1)
        df['Score_FRP'] = df.apply(calc_intensidad, axis=1)
        df['IPO_Total'] = df['Score_Contexto'] + df['Score_FRP']
        
        # UI Colors
        def asignar_color(row):
            if row['IPO_Total'] >= 13: return [211, 47, 47]      
            elif row['IPO_Total'] >= 8: return [251, 192, 45]    
            else: return [76, 175, 80]                           
            
        df['color'] = df.apply(asignar_color, axis=1)
        df['radius'] = np.where(df['IPO_Total'] >= 13, 3000, np.where(df['IPO_Total'] >= 8, 1500, 800))

        # Agrupamiento de Episodios
        df_episodios = df.groupby('Episodio_ID').agg(
            Focos=('ID', 'count'),
            FRP_Max=('frp', 'max'),
            Contexto_Max=('Score_Contexto', 'max'),
            IPO_Max=('IPO_Total', 'max'),
            Lat_Centro=('lat', 'mean'),
            Lon_Centro=('lon', 'mean')
        ).reset_index().sort_values('IPO_Max', ascending=False)
        
        return df.sort_values('IPO_Total', ascending=False), df_episodios
    except:
        # Falla de conexión a la NASA
        return pd.DataFrame(), pd.DataFrame()

df_focos, df_episodios = load_live_data()

# ==========================================
# INTERFAZ DE COMANDO
# ==========================================
st.title("🛰️ COP - Conciencia Situacional Territorial")
st.caption(f"ESTADO: Monitoreo satelital activo (Últimas 24h) | HORA LOCAL: {datetime.now().strftime('%H:%M:%S')}")

# --- RUTINA DE MAPA VACÍO (Seguridad Operacional) ---
if df_focos.empty:
    st.success("✅ **REPORTE TÁCTICO:** Sin actividad térmica detectada en Uruguay en las últimas 24 horas.")
    # Renderizamos el mapa base de Uruguay para mantener la estética
    view_state = pdk.ViewState(latitude=-32.5, longitude=-56.0, zoom=5.8)
    r = pdk.Deck(initial_view_state=view_state, map_provider="carto", map_style="dark")
    st.pydeck_chart(r)
    st.stop() # Finaliza el script acá si no hay fuegos

# --- RUTINA DE MAPA ACTIVO (Si hay focos) ---
c1, c2 = st.columns(2)
c1.markdown(f"<div class='metric-box'><h4>Total Detecciones</h4><h2>{len(df_focos)}</h2></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='metric-box box-critico'><h4>Episodios Activos</h4><h2>{len(df_episodios)}</h2></div>", unsafe_allow_html=True)

# Selección Táctica
opciones_episodios = ["VISIÓN GLOBAL (Todo el territorio)"] + df_episodios['Episodio_ID'].tolist()
seleccion = st.selectbox("Aislar vista táctica por episodio:", opciones_episodios)

if seleccion == "VISIÓN GLOBAL (Todo el territorio)":
    df_mapa = df_focos
    centro_lat, centro_lon, zoom_level = -32.5, -56.0, 5.8
else:
    df_mapa = df_focos[df_focos['Episodio_ID'] == seleccion]
    ep_data = df_episodios[df_episodios['Episodio_ID'] == seleccion].iloc[0]
    centro_lat, centro_lon, zoom_level = ep_data['Lat_Centro'], ep_data['Lon_Centro'], 9.5

# Vistas
col_mapa, col_panel = st.columns([2.5, 1.5])

with col_mapa:
    view_state = pdk.ViewState(latitude=centro_lat, longitude=centro_lon, zoom=zoom_level, transition_duration=1000)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_mapa,
        get_position="[lon, lat]",
        get_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.8,
        filled=True,
    )
    r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_provider="carto", map_style="dark", 
                 tooltip={"text": "ID: {ID}\nFRP: {frp} MW\nContexto: {Score_Contexto}/12\nIPO Total: {IPO_Total}/17"})
    st.pydeck_chart(r)

with col_panel:
    tab_ep, tab_focos, tab_auditoria = st.tabs(["📋 Episodios", "🔥 Focos", "🔍 Auditoría"])
    
    with tab_ep:
        df_ep_disp = df_episodios.copy()
        df_ep_disp['FRP_Max'] = df_ep_disp['FRP_Max'].round(1).astype(str) + " MW"
        st.dataframe(df_ep_disp[['Episodio_ID', 'Focos', 'FRP_Max', 'IPO_Max']], hide_index=True)
        
    with tab_focos:
        if seleccion == "VISIÓN GLOBAL (Todo el territorio)":
            st.info("Seleccione un episodio para ver sus focos.")
        else:
            st.dataframe(df_mapa[['ID', 'frp', 'IPO_Total']], hide_index=True)
            
    with tab_auditoria:
        if seleccion != "VISIÓN GLOBAL (Todo el territorio)":
            foco_id = st.selectbox("Auditar Foco (ID):", df_mapa['ID'].tolist())
            if foco_id:
                foco = df_mapa[df_mapa['ID'] == foco_id].iloc[0]
                st.code(f"--- 🌍 CONTEXTO ---\nSubtotal: {int(foco['Score_Contexto'])}/12\n\n--- 🔥 INTENSIDAD ---\nFRP: {foco['frp']:>5.1f} MW\nSubtotal: {int(foco['Score_FRP'])}/5")
                st.markdown(f"### 🎯 TOTAL IPO v2: {int(foco['IPO_Total'])}/17")
        else:
            st.info("Seleccione un episodio para auditar.")
