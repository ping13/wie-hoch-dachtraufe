import os
import subprocess
import plotly.express as px
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Polygon, box,MultiPolygon
import pyvista as pv
from i18n import _, update_translation

from swissbuildings3d_etl import download_data, process_buildings_from_zips
import folium
from folium.plugins import Draw

import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from streamlit_3d import threed_from_file
import utilities

from pathlib import Path
import tempfile

MAX_AREA=100000

# Language selector in sidebar
languages = {
    'Deutsch': 'de',
    'Français': 'fr',
    'Italiano': 'it',
    'English': 'en'
}

# Set page configuration
st.set_page_config(
    page_title=_('How high is the eaves height?'),
    layout="centered"              
)

# Initialize language on first load
if 'language' not in st.session_state:
    st.session_state['language'] = 'de'
    st.session_state['language_name'] = 'Deutsch'

# Language selector
selected_language = st.sidebar.selectbox(
    "Select Language",
    options=list(languages.keys()),
    index=list(languages.keys()).index(next(name for name, code in languages.items() 
                                          if code == st.session_state['language'])),
    key="language_selector"
)

# Update language if changed
new_language_code = languages[selected_language]
if st.session_state.get('language') != new_language_code:
    st.session_state['language'] = new_language_code
    st.session_state['language_name'] = selected_language
    update_translation()
    st.rerun()

st.title(_('How high is the eaves and ridge height of a roof?'))
st.markdown(_('Select an area (smaller than {max_area:,}m²) to analyze the [ridge eaves heights of building roofs](https://en.wikipedia.org/wiki/Eaves).').format(max_area=MAX_AREA))

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
output = st_folium(m, width=800, height=400)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)

# Render the calc button 
if st.button(_("Calculate")):
    if output["last_active_drawing"]:
        drawn_polygon = output["last_active_drawing"]["geometry"]["coordinates"][0]
        polygon = Polygon(drawn_polygon)

        # Convert polygon to Swiss coordinates
        swiss_coords = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
        swiss_polygon = Polygon(swiss_coords)

        # Check area size
        area = swiss_polygon.area
        if area > MAX_AREA:
            st.error(_("The selected area is too large ({area:.0f} m²). Please choose an area smaller than {MAX_AREA} m²."))
            st.stop()
            
        print(_("Downloading {swiss_polygon}"))
        filenames_tuples = download_data(swiss_polygon, "buildings")

        if len(filenames_tuples) == 0:
            st.error(_("Keine Daten bei Swisstopo gefunden."))
            st.stop()

        print(_("Now processing {','.join(filenames_tuples)}"))
        # Create a combined mesh for all buildings
        combined_mesh = pv.PolyData()

        # Create DataFrame to store building information
        traufen = pd.DataFrame(columns=['EntityHand', 'min_height', 'max_height', 'layer','descr'])
        all_meshes = [ ]
        for filename, filename_2d in filenames_tuples:
            result = process_buildings_from_zips(filename, swiss_polygon)

            for layer_type, meshes in result.items():
                for mesh in meshes:
                    all_meshes.append(mesh)
                    # add the "traufenhoehe"
                    z_coords = mesh.points[:, 2]
                    min_height = None
                    max_height = None
                    descr = "First und Höhe nicht verfügbar"
                    if z_coords.any():
                        min_height = np.min(mesh.points[:, 2])
                        max_height = np.max(mesh.points[:, 2])
                        descr = f"<b>Traufe:<b> {min_height:.1f}<br/><b>First:</b> {max_height:.1f}"
                    traufen.loc[len(traufen)] = {
                        'EntityHand': mesh.user_dict["id"],
                        'layer': mesh.user_dict["layer"],
                        'min_height': min_height,
                        'max_height': max_height,
                        'descr': descr 
                    }
                    
        if len(all_meshes) == 0:
            st.error(_("No buildings found, please draw a larger area."))
            st.stop()

        traufen.to_csv('buildings_attributes.csv',index=False)
        
        # Execute ogr2ogr commands to process the data
        try:
            # First ogr2ogr command - Create shapefile
            subprocess.run([
                'ogr2ogr',
                '-f', 'ESRI Shapefile',
                'output.shp.zip',
                filename_2d,
                '-sql',
                "SELECT * FROM entities JOIN 'buildings_attributes.csv'.buildings_attributes ON entities.EntityHand = buildings_attributes.EntityHand"
            ], check=True)

            # Second ogr2ogr command - Convert to KML
            subprocess.run([
                'ogr2ogr',
                '-f', 'KML',
                'buildings.kml',
                'output.shp.zip',
                '-t_srs', 'EPSG:4326',
                '-s_srs', 'EPSG:2056',
                '-sql', 'SELECT * FROM entities WHERE min_height IS NOT NULL',
                '-dsco', 'NameField=EntityHand',
                '-dsco', 'DescriptionField=descr'
            ], check=True)
        except subprocess.CalledProcessError as e:
            st.error(_("Error processing geographic data: ") + str(e))
            st.stop()

        # Replace in the KML file buildings.kml the text '<fill>0</fill>' with '<fill>1</fill><color>7f0000ff</color>'. AI!

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
            st.error(_("Failed to generate 3D model file"))

        # Create histogram of building heights
        z_coords = combined.points[:, 2]  # Get all z-coordinates

        fig = px.histogram(
            z_coords, 
            title=_('Distribution of z-coordinate values'),
            labels={'value': _('Point height (m)'), 'count': _('Number of points')},
            nbins=50,
            orientation='h'  # This switches to horizontal orientation
        )
        fig.update_layout(
            showlegend=False,
            yaxis_title=_('Point height(m)'),  # Switched from x to y
            xaxis_title=_('Number of points')     # Switched from y to x
        )
        st.plotly_chart(fig)

        print("done")

gh_release, gh_date = "--", "--" 
try:
    gh_release,gh_date=utilities.get_latest_release_date("https://github.com/ping13/wie-hoch-dachtraufe")
except:
    pass 
st.markdown("---")
st.markdown(f"© 2025 [Stephan Heuel](https://blog.heuel.org/pages/contact), App Version: {gh_release}, {gh_date}")
st.markdown(_("Based on [Wo sind Briefkästen](https://wieviele-briefkaesten-gibt-es.streamlit.app)"))
