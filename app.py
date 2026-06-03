import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime

# ==========================================
# CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="COP - Conciencia Situacional", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    .metric-box { padding: 15px; border-radius: 5px; background-color: #1E2127; border-left: 4px solid #4CAF50; margin-bottom: 10px; }
    .box-critico { border-color: #D32F2F; }
    .box-alerta { border-color: #FBC02D; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# SIMULACIÓN DE DATOS (UX VALIDATION)
# ==========================================
@st.cache_data
def load_mock_data():
    np.random.seed(42)
    n_focos = 200
    
    # 1. Simulación de Focos Individuales
    df_focos = pd.DataFrame({
        'ID': range(1000, 1000 + n_focos),
        'lat': np.random.uniform(-34.9, -30.0, n_focos),
        'lon': np.random.uniform(-58.4, -53.5, n_focos),
        'frp': np.random.exponential(15, n_focos) + 5,
        'PC1_Estres': np.random.normal(-1, 2, n_focos),
        'anomalia_hum': np.random.normal(-5, 8, n_focos),
        'temp_max': np.random.normal(30, 5, n_focos),
        'Episodio_ID': np.random.choice([f"EP-{str(i).zfill(3)}" for i in range(1, 25)], n_focos) # 24 episodios simulados
    })
    
    # 2. Desacople del Motor Lógico
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

    df_focos['Score_Contexto'] = df_focos.apply(calc_contexto, axis=1)
    df_focos['Score_FRP'] = df_focos.apply(calc_intensidad, axis=1)
    df_focos['IPO_Total'] = df_focos['Score_Contexto'] + df_focos['Score_FRP']
    
    # Categorización 2D
    df_focos['Cat_Contexto'] = pd.cut(df_focos['Score_Contexto'], bins=[-1, 3, 7, 13], labels=['Benigno', 'Moderado', 'Severo'])
    df_focos['Cat_FRP'] = pd.cut(df_focos['frp'], bins=[-1, 10, 20, np.inf], labels=['Bajo', 'Medio', 'Alto'])
    
    # Lógica de Color (Basada en Matriz 2D simplificada)
    def asignar_color(row):
        if row['IPO_Total'] >= 13: return [211, 47, 47]      # Rojo (Crítico)
        elif row['IPO_Total'] >= 8: return [251, 192, 45]    # Amarillo (Alerta)
        else: return [76, 175, 80]                           # Verde (Rutina)
        
    df_focos['color'] = df_focos.apply(asignar_color, axis=1)
    df_focos['radius'] = np.where(df_focos['IPO_Total'] >= 13, 5000, np.where(df_focos['IPO_Total'] >= 8, 3000, 1000))
    
    # 3. Agrupamiento de Episodios
    df_episodios = df_focos.groupby('Episodio_ID').agg(
        Focos=('ID', 'count'),
        FRP_Max=('frp', 'max'),
        Contexto_Max=('Score_Contexto', 'max'),
        IPO_Max=('IPO_Total', 'max')
    ).reset_index().sort_values('IPO_Max', ascending=False)
    
    return df_focos.sort_values('IPO_Total', ascending=False), df_episodios

df_focos, df_episodios = load_mock_data()

# ==========================================
# BARRA SUPERIOR
# ==========================================
st.title("🛰️ COP - Plataforma de Conciencia Situacional")

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f"<div class='metric-box'><h4>Focos Detectados</h4><h2>{len(df_focos)}</h2></div>", unsafe_allow_html=True)
c2.markdown(f"<div class='metric-box box-critico'><h4>Alertas Críticas (IPO ≥ 13)</h4><h2>{len(df_focos[df_focos['IPO_Total'] >= 13])}</h2></div>", unsafe_allow_html=True)
c3.markdown(f"<div class='metric-box box-alerta'><h4>Episodios Activos</h4><h2>{len(df_episodios)}</h2></div>", unsafe_allow_html=True)
c4.markdown(f"<div class='metric-box'><h4>Última Actualización</h4><h2>{datetime.now().strftime('%H:%M:%S')}</h2></div>", unsafe_allow_html=True)

# ==========================================
# INTERFAZ TÁCTICA (MAPA + TABS)
# ==========================================
col_mapa, col_panel = st.columns([2.5, 1.5])

with col_mapa:
    # carto-darkmatter no requiere API key de Mapbox
    view_state = pdk.ViewState(latitude=-32.5, longitude=-56.0, zoom=5.8)
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_focos,
        get_position="[lon, lat]",
        get_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.8,
        filled=True,
    )
    r = pdk.Deck(layers=[layer], initial_view_state=view_state, map_provider="carto", map_style="dark", tooltip={"text": "ID: {ID}\nEpisodio: {Episodio_ID}\nFRP: {frp} MW\nContexto: {Score_Contexto}/12\nIPO Total: {IPO_Total}/17"})
    st.pydeck_chart(r)

with col_panel:
    tab1, tab2, tab3 = st.tabs(["🗺️ Episodios", "🔥 Focos", "🔍 Transparencia IPO"])
    
    with tab1:
        st.markdown("### Ranking de Episodios")
        df_ep_disp = df_episodios.copy()
        df_ep_disp['FRP_Max'] = df_ep_disp['FRP_Max'].round(1).astype(str) + " MW"
        st.dataframe(df_ep_disp[['Episodio_ID', 'Focos', 'FRP_Max', 'Contexto_Max', 'IPO_Max']], use_container_width=True, hide_index=True)
        
    with tab2:
        st.markdown("### Focos Individuales")
        df_foc_disp = df_focos[['ID', 'Episodio_ID', 'Score_Contexto', 'Score_FRP', 'IPO_Total']].copy()
        st.dataframe(df_foc_disp, use_container_width=True, hide_index=True)
        
    with tab3:
        st.markdown("### Auditoría de Decisión")
        foco_id = st.selectbox("Seleccione un ID de Foco:", df_focos['ID'].tolist())
        
        if foco_id:
            foco = df_focos[df_focos['ID'] == foco_id].iloc[0]
            st.markdown(f"**ID Detección:** `{foco_id}` | **Pertenece a:** `{foco['Episodio_ID']}`")
            st.markdown(f"**Ubicación:** {foco['lat']:.3f}, {foco['lon']:.3f}")
            
            st.markdown("---")
            st.markdown("#### 🌍 CONTEXTO AMBIENTAL")
            st.code(f"""
PC1 Estrés:   {foco['PC1_Estres']:>6.2f}  (+{5 if foco['PC1_Estres'] <= -3.62 else 3 if foco['PC1_Estres'] <= -2.25 else 1 if foco['PC1_Estres'] <= -0.50 else 0})
Anom Humedad: {foco['anomalia_hum']:>6.1f}% (+{4 if foco['anomalia_hum'] <= -12.7 else 2 if foco['anomalia_hum'] <= -6.5 else 1 if foco['anomalia_hum'] <= 0 else 0})
Temp Máxima:  {foco['temp_max']:>6.1f}°C (+{3 if foco['temp_max'] >= 36.5 else 2 if foco['temp_max'] >= 31.5 else 0})

Subtotal Contexto: {int(foco['Score_Contexto'])}/12 ({foco['Cat_Contexto']})
            """)
            
            st.markdown("#### 🔥 INTENSIDAD OBSERVADA")
            st.code(f"""
FRP Detectado: {foco['frp']:>5.1f} MW (+{int(foco['Score_FRP'])})

Subtotal Intensidad: {int(foco['Score_FRP'])}/5 ({foco['Cat_FRP']})
            """)
            
            st.markdown(f"### 🎯 TOTAL IPO v2: {int(foco['IPO_Total'])}/17")