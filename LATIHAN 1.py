import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Polygon, Point
import numpy as np
import folium
from streamlit_folium import st_folium
from pyproj import Transformer
import json

# --- 1. FUNGSI UTILITI ---
def format_dms(angle):
    d = int(angle)
    m = int((angle - d) * 60)
    s = int(round(((angle - d) * 60 - m) * 60))
    if s == 60: m += 1; s = 0
    if m == 60: d += 1; m = 0
    return f"{d}°{m:02d}'{s:02d}\""

# --- 2. SISTEM LOGIN ---
def check_password():
    user_db = {"1": "Faseha", "2": "Farahani", "3": "Syuhadah"}
    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        st.title("🔐 Log Masuk Sistem Geo-Ukur")
        col1, col2 = st.columns([1, 2])
        with col1:
            u = st.text_input("Username (No. ID)")
            p = st.text_input("Password", type="password")
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Log Masuk", use_container_width=True):
                    if u in user_db and p == "hello123":
                        st.session_state["password_correct"] = True
                        st.session_state["current_user_name"] = user_db[u]
                        st.rerun()
                    else:
                        st.error("ID atau Password salah!")
            with btn_col2:
                if st.button("Lupa Kata Laluan?", use_container_width=True):
                    st.session_state["show_forgot"] = True
            if st.session_state.get("show_forgot"):
                st.info("ℹ️ Sila hubungi Admin.")
                if st.button("Tutup"):
                    st.session_state["show_forgot"] = False
                    st.rerun()
        return False
    return True

def logout():
    st.session_state["password_correct"] = False
    st.rerun()

# --- 3. ATURCARA UTAMA ---
if check_password():
    if "config_done" not in st.session_state:
        st.set_page_config(page_title="Sistem Pelan Lot Tanah", layout="wide")
        st.session_state["config_done"] = True
    
    st.markdown("""
        <style>
        .leaflet-control-layers-expanded {
            width: auto !important;
            min-width: 200px !important;
            padding: 10px !important;
            font-family: 'Arial', sans-serif !important;
            font-size: 14px !important;
            border-radius: 8px !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2) !important;
        }
        .leaflet-control-layers-list label {
            margin-bottom: 5px !important;
            display: block !important;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(f"### 📍 Geo-Ukur Pro\nSelamat datang, **{st.session_state['current_user_name']}**")
        
        with st.expander("🎨 TETAPAN VISUAL", expanded=True):
            point_size = st.slider("Saiz Titik Stesen", 10, 40, 25)
            text_size = st.slider("Saiz Tulisan Labels", 5, 15, 9)
            zoom_lv = st.slider("Tahap Zoom Peta", 15, 21, 19)
            map_choice = st.radio("Jenis Peta Utama:", ["Satelit", "Street"])
            poly_color = st.color_picker("Pilih Warna Poligon", "#FFFF00")

        st.markdown("---")
        no_lot_input = st.text_input("Masukkan No. Lot:", "LOT 1234")
        uploaded_file = st.file_uploader("Upload fail CSV (point.csv)", type=['csv'])

        if st.button("🚪 Log Keluar", use_container_width=True):
            logout()

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        if 'E' in df.columns and 'N' in df.columns:
            transformer = Transformer.from_crs("EPSG:4390", "EPSG:4326", always_xy=True)
            lons, lats = transformer.transform(df['E'].values, df['N'].values)
            df['lat'], df['lon'] = lats, lons
            
            poly_orig = Polygon(list(zip(df['E'], df['N'])))
            area_m2 = poly_orig.area 
            perimeter_m = poly_orig.length 
            centroid_orig = poly_orig.centroid
            
            c_lon, c_lat = transformer.transform(centroid_orig.x, centroid_orig.y)
            mean_lat, mean_lon = df['lat'].mean(), df['lon'].mean()

            data_list = []
            for i in range(len(df)):
                p1, p2 = df.iloc[i], df.iloc[(i + 1) % len(df)]
                dist = np.sqrt((p2['E']-p1['E'])**2 + (p2['N']-p1['N'])**2)
                bearing_deg = np.degrees(np.arctan2(p2['E']-p1['E'], p2['N']-p1['N'])) % 360
                
                latit = p2['N'] - p1['N']
                dipat = p2['E'] - p1['E']
                
                data_list.append({
                    "Dari STN": int(p1['STN']), "Ke STN": int(p2['STN']),
                    "Bearing": format_dms(bearing_deg), "Jarak (m)": round(dist, 3),
                    "Latit (ΔU)": round(latit, 3), "Dipat (ΔT)": round(dipat, 3),
                    "E1": p1['E'], "N1": p1['N'], "E2": p2['E'], "N2": p2['N'],
                    "lat1": p1['lat'], "lon1": p1['lon']
                })

            # --- BAHAGIAN EXPORT QGIS ---
            features = []
            # Feature Poligon dengan Data Luas & Perimeter
            poly_coords_list = [list(coord) for coord in zip(df.lon.tolist() + [df.lon.iloc[0]], df.lat.tolist() + [df.lat.iloc[0]])]
            features.append({
                "type": "Feature",
                "properties": {
                    "No_Lot": no_lot_input,
                    "Luas_m2": round(area_m2, 3),
                    "Perimeter_m": round(perimeter_m, 3),
                    "Jenis": "Sempadan Lot"
                },
                "geometry": {"type": "Polygon", "coordinates": [poly_coords_list]}
            })
            # Feature Points (Stesen)
            for _, row in df.iterrows():
                features.append({
                    "type": "Feature",
                    "properties": {"STN": int(row['STN']), "Timur_E": float(row['E']), "Utara_N": float(row['N'])},
                    "geometry": {"type": "Point", "coordinates": [row['lon'], row['lat']]}
                })
            
            geojson_data = json.dumps({"type": "FeatureCollection", "features": features})
            
            with st.sidebar:
                st.download_button(label="📥 Export ke QGIS (.geojson)", data=geojson_data, file_name=f"{no_lot_input}_survey.geojson", use_container_width=True)

            tab1, tab2, tab3 = st.tabs(["📉 Pelan Lot Teknikal", "🛰️ Imej Satelit", "📋 Jadual Data"])

            with tab1:
                fig, ax = plt.subplots(figsize=(10, 10))
                gpd.GeoDataFrame(geometry=[poly_orig]).plot(ax=ax, facecolor='none', edgecolor='black', linewidth=2)
                
                # Tambah Grid Paksi U/S dan T/B
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.set_xlabel("Timur (T) / Easting", fontsize=10)
                ax.set_ylabel("Utara (U) / Northing", fontsize=10)
                
                for item in data_list:
                    mid_e = (item['E1'] + item['E2']) / 2
                    mid_n = (item['N1'] + item['N2']) / 2
                    dx, dy = item['E2'] - item['E1'], item['N2'] - item['N1']
                    angle = np.degrees(np.arctan2(dy, dx))
                    if angle > 90: angle -= 180
                    elif angle < -90: angle += 180
                    
                    ve, vn = mid_e - centroid_orig.x, mid_n - centroid_orig.y
                    v_norm = np.sqrt(ve**2 + vn**2)
                    off = 0.6
                    
                    ax.text(mid_e + (ve/v_norm * off), mid_n + (vn/v_norm * off), item["Bearing"], 
                            fontsize=text_size, rotation=angle, ha='center', va='center', fontweight='bold')
                    ax.text(mid_e - (ve/v_norm * off), mid_n - (vn/v_norm * off), f"{item['Jarak (m)']}m", 
                            fontsize=text_size, rotation=angle, ha='center', va='center', color='blue')

                    ax.scatter(item['E1'], item['N1'], color='red', s=point_size*4, zorder=5)
                    ax.text(item['E1'], item['N1'] + 0.3, str(item['Dari STN']), color='red', 
                            fontsize=text_size+3, ha='center', va='bottom', fontweight='bold')

                ax.set_title(f"Pelan Teknikal {no_lot_input}", fontweight='bold')
                ax.set_aspect('equal')
                st.pyplot(fig)

            with tab2:
                m = folium.Map(location=[mean_lat, mean_lon], zoom_start=zoom_lv, max_zoom=21)
                google_sat = 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}'
                osm = 'OpenStreetMap'
                
                if map_choice == "Satelit":
                    folium.TileLayer(tiles=google_sat, attr='Google', name='Google Satellite', max_zoom=21).add_to(m)
                    folium.TileLayer(osm, name='OpenStreetMap').add_to(m)
                else:
                    folium.TileLayer(osm, name='OpenStreetMap').add_to(m)
                    folium.TileLayer(tiles=google_sat, attr='Google', name='Google Satellite', max_zoom=21).add_to(m)

                fg_poly = folium.FeatureGroup(name="Sempadan Lot (Poligon)").add_to(m)
                fg_points = folium.FeatureGroup(name="Titik Stesen (Points)").add_to(m)

                poly_popup_html = f"""<div style="width: 250px; font-family: Arial;"><b>LOT:</b> {no_lot_input}<br><b>Luas:</b> {area_m2:.2f} m²</div>"""
                poly_coords = [[r.lat, r.lon] for _, r in df.iterrows()]
                folium.Polygon(locations=poly_coords, color=poly_color, weight=3, fill=True, fill_opacity=0.2,
                                popup=folium.Popup(poly_popup_html, max_width=300)).add_to(fg_poly)

                folium.Marker([c_lat, c_lon], icon=folium.DivIcon(html=f'<div style="color:white; font-weight:bold; text-shadow:2px 2px 4px black;">{no_lot_input}</div>')).add_to(fg_poly)

                for item in data_list:
                    point_popup_html = f"""<div style="width: 200px; font-family: Arial;"><b style="color:red;">STN: {item['Dari STN']}</b><br><b>U:</b> {item['N1']:.3f}<br><b>B:</b> {item['E1']:.3f}</div>"""
                    icon_html = f'<div style="background-color:red; border:1px solid white; border-radius:50%; width:{point_size}px; height:{point_size}px; color:white; display:flex; align-items:center; justify-content:center; font-size:{text_size-2}pt; font-weight:bold;">{item["Dari STN"]}</div>'
                    folium.Marker(location=[item['lat1'], item['lon1']], icon=folium.DivIcon(html=icon_html),
                                  popup=folium.Popup(point_popup_html, max_width=250)).add_to(fg_points)

                folium.LayerControl(collapsed=False, position='topright').add_to(m)
                st_folium(m, width=1200, height=700, returned_objects=[])

            with tab3:
                st.subheader("📋 Jadual Cerapan & Koordinat")
                st.dataframe(pd.DataFrame(data_list)[["Dari STN", "Ke STN", "Bearing", "Jarak (m)", "Latit (ΔU)", "Dipat (ΔT)"]], 
                             use_container_width=True, hide_index=True)
                
                c1, c2 = st.columns(2)
                c1.metric("Luas (m²)", f"{area_m2:.3f}")
                c2.metric("Perimeter (m)", f"{perimeter_m:.3f}")