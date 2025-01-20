import os
import plotly.express as px
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon, box,MultiPolygon
import pyvista as pv

from swissbuildings3d_etl import download_data, process_buildings_from_zips
import folium
from folium.plugins import Draw

import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from streamlit_3d import threed_from_file

from pathlib import Path
import tempfile

MAX_AREA=50000

# Set page configuration
st.set_page_config(
    page_title='Wie hoch ist die Dachtraufe?',
    layout="centered"              
)

st.title('Wie hoch ist die Dachtraufe?')
st.markdown(f'Wählen Sie ein Gebiet aus (kleiner als {MAX_AREA:,}m²), um die [Traufenhöhen der Gebäude](https://de.wikipedia.org/wiki/Dachtraufe) zu analysieren.')

def create_map(center, zoom):
    """Erstellt eine interaktive Karte mit Zeichentools.

    Args:
        center (list): Mittelpunkt der Karte [Breitengrad, Längengrad].
        zoom (int): Zoomstufe der Karte.

    Returns:
        folium.Map: Eine Folium-Karte mit Zeichentools.
    """
    m = folium.Map(location=center,
        zoom_start=zoom,
        control_scale=True,
        tiles="https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-farbe/default/current/3857/{z}/{x}/{y}.jpeg",
        attr='Map data: &copy; <a href="https://www.swisstopo.ch" target="_blank" rel="noopener noreferrer">swisstopo</a>, <a href="https://www.housing-stat.ch/" target="_blank" rel="noopener noreferrer">BFS</a>',
        )

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "rectangle": False,
            "circle": False,
            "marker": False,
            "circlemarker": False,
            "polygon": {
                "shapeOptions": {
                    "color": "#ff0000"
                },
            },
        },
        edit_options={
            "edit": False
        }
    ).add_to(m)
    return m



# Create the map and display it in the placeholder
m = create_map(center=[46.8182, 8.2275], zoom=8)  # Centered on Switzerland
output = st_folium(m, width=700)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)

if st.button("Berechne"):
    if output["last_active_drawing"]:
        drawn_polygon = output["last_active_drawing"]["geometry"]["coordinates"][0]
        polygon = Polygon(drawn_polygon)

        # Convert polygon to Swiss coordinates
        swiss_coords = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
        swiss_polygon = Polygon(swiss_coords)

        # Check area size
        area = swiss_polygon.area
        if area > MAX_AREA:
            st.error(f"Die ausgewählte Fläche ist zu gross ({area:.0f} m²). Bitte wählen Sie eine Fläche kleiner als {MAX_AREA} m².")
            st.stop()
            
        print(f"Downloading {swiss_polygon}")
        filenames = download_data(swiss_polygon, "buildings")

        if len(filenames) == 0:
            st.error(f"Keine Daten bei Swisstopo gefunden.")
            st.stop()

        print(f"Now processing {','.join(filenames)}")
        # Create a combined mesh for all buildings
        combined_mesh = pv.PolyData()

        # Create DataFrame to store building information
        traufen = pd.DataFrame(columns=['name', 'min_height'])
        all_meshes = [ ]
        for filename in filenames:
            result = process_buildings_from_zips(filename, swiss_polygon)

            for layer_type, meshes in result.items():
                for mesh in meshes:
                    all_meshes.append(mesh)
                    # add the "traufenhoehe"
                    traufen.loc[len(traufen)] = {
                        'name': mesh.user_dict["id"],
                        'min_height': np.min(mesh.points[:, 2])
                    }

        if len(all_meshes) == 0:
            st.error(f"Keine Gebäude gefunden, zeichne eine grössere Fläche.")
            st.stop()

        # Display building heights table
        st.write("Traufenhöhen der Gebäude:")
        st.dataframe(
            traufen.sort_values('min_height'),
            column_config={
                "name": "Gebäude ID",
                "min_height": st.column_config.NumberColumn(
                    "Traufenhöhe (m)",
                    format="%.1f"
                )
            }
        )

        # Show 3D object
        output_file = "buildings.ply"            
        # Combine all meshes
        combined = all_meshes[0].copy()
        for mesh in all_meshes[1:]:
            combined = combined.merge(mesh)
            
        combined.save(output_file)        
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:            
            threed_from_file(file_path='buildings.ply',
                             suffix=".ply",
                             key='your roofs')                
        else:
            st.error("Failed to generate 3D model file")

        # Create histogram of building heights
        z_coords = combined.points[:, 2]  # Get all z-coordinates

        fig = px.histogram(
            z_coords, 
            title='Verteilung der z-Koordinatenwerte',
            labels={'value': 'Höhe (m)', 'count': 'Anzahl'},
            nbins=50,
            orientation='h'  # This switches to horizontal orientation
        )
        fig.update_layout(
            showlegend=False,
            yaxis_title='Höhe (m)',  # Switched from x to y
            xaxis_title='Anzahl'     # Switched from y to x
        )
        st.plotly_chart(fig)

        print("done")
