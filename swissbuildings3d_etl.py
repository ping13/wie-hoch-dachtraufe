import math
import zipfile
import os
import sys
from typing import Dict, Optional
import requests
from shapely import geometry
from shapely.geometry import shape, Polygon
import numpy as np
import fiona
import logging
import pyvista as pv
import json
import tempfile
import subprocess

import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# log GDAL version AI!

# Constants
DOWNLOADS_DIR = "downloads/"

def make_swisstopo_request(
    swiss_polygon: 'Polygon', filetype: str = "buildings"
) -> Optional[Dict]:
    """Make a request to SwissTopo API for DEM or building data.

    Args:
        swiss_polygon: Shapely Polygon object defining the area of interest, LV95 coords
        filetype: Type of data to request ("dem" or "buildings")

    Returns:
        JSON response from API or None if request fails
    """

    # Get bounds directly from the polygon
    minx, miny, maxx, maxy = swiss_polygon.bounds

    if filetype == "dem":
        url = "https://ogd.swisstopo.admin.ch/services/swiseld/services/assets/ch.swisstopo.swissalti3d/search"
        params = {
            "format": "image/tiff; application=geotiff; profile=cloud-optimized",
            "resolution": "0.5",
            "srid": "2056",
            "state": "current",
            "xMin": minx,
            "xMax": maxx,
            "yMin": miny,
            "yMax": maxy,
        }
    elif filetype == "buildings":
        url = "https://ogd.swisstopo.admin.ch/services/swiseld/services/assets/ch.swisstopo.swissbuildings3d_2/search"
        params = {
            "format": "application/x.dxf+zip",
            "srid": "2056",
            "state": "current",
            "xMin": minx,
            "xMax": maxx,
            "yMin": miny,
            "yMax": maxy,
        }
    else:
        print(f"Unknown filetype {filetype}")
        raise

    # Common additional headers
    headers = {
        "User-Agent": "curl/7.84.0",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
    }

    try:
        response = requests.get(url, params=params, headers=headers)

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        raise 

@st.cache_data
def download_tile(url, folder):
    try:
        file_name = os.path.join(folder, url.split("/")[-1])

        # Create folder if it doesn't exist
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        
        if not os.path.exists(file_name):
            print(f"Download  {url}")
            # Add no-cache headers
            headers = {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                with open(file_name, "wb") as f:
                    f.write(response.content)
            else:
                print(f"Download problames with {url}")
                sys.exit(-1)
        else:
            print(f"file {file_name} already exists for {url}")

    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        sys.exit(-1)

    if "dxf.zip" not in file_name:
        return file_name
    else:
        # Extract zip containing DXF
        with zipfile.ZipFile(file_name, "r") as zip_ref:
            dxf_file = zip_ref.namelist()[0]  # Get first/only file

            # Get the expected shapefile zip name
            f_shpzip = dxf_file.replace(".dxf", ".shp.zip")
            shp_zip_path = f"{folder}/{f_shpzip}"

            print(f"unzipping {file_name} and converting to a Shapefile")
            zip_ref.extractall(folder)

            print("Running ogr2ogr")
            # Convert DXF to Shapefile
            command = [
                "ogr2ogr",
                "-f",
                "ESRI Shapefile",
                shp_zip_path,
                f"{folder}/{dxf_file}",
            ]
            subprocess.call(command)            

            # remove dxf_file
            os.remove(f"{folder}/{dxf_file}")

        # create a dissolved 2D shapefile: first create a 2D shapefile from the MultiPatch file
        tmpshz_path = "converted_2d.shp.zip"
        command = ["ogr2ogr", "-f", "ESRI Shapefile", tmpshz_path, shp_zip_path, "-skipfailures", "-dim", "2", "-nlt", "MULTIPOLYGON"]
        subprocess.call(command)
            
        # now dissolve according to entityhand
        f2d_shpzip = shp_zip_path.replace(".shp.zip", "_2D.shp.zip")
        command = ["ogr2ogr", "-f", "ESRI Shapefile", f2d_shpzip, tmpshz_path, "-dialect", "sqlite", "-sql", "SELECT ST_Union(geometry) as geometry, EntityHand FROM entities GROUP BY EntityHand", "-nln", "entities"]
        subprocess.call(command)

        # remove temp shapefile
        os.remove(tmpshz_path)

        
        # return zipped Shapefile
        return shp_zip_path, f2d_shpzip


def process_buildings_from_zips(
        input_path, mask_multi_polygons, layer_types=None, entity_handles=None
):
    logger.info(f"Processing buildings from {input_path}")
    building_counter = 0  # Initialize counter for unique IDs
    layer_lut: Dict[str, int] = {}  # Track counts of each layer type

    shp_zip = input_path
    logger.info(f"Processing {shp_zip}")
    skip_count = 0
    
    # Create progress bar
    progress_bar = st.progress(0)
    
    # Get total features count using len()
    with fiona.open(shp_zip, "r") as src:
        total_features = len(src)
    
    # Process features in a separate open operation
    with fiona.open(shp_zip, "r") as src:
        for idx, feature in enumerate(src):
            # Update progress
            progress = (idx + 1) / total_features
            progress_bar.progress(progress, f"Analyzing building {idx + 1} of {total_features} from the data tile")

            properties = feature["properties"]
            feature_layer_type = properties.get("Layer", "n/a")

            if layer_types and all(feature_layer_type != lt for lt in layer_types):
                continue
            if entity_handles and all(
                properties.get("EntityHand") != h for h in entity_handles
            ):
                continue

            geom = feature["geometry"]
            if geom["type"] not in [
                "Polygon",
                "MultiPolygon",
                "GeometryCollection",
            ]:
                continue

            if mask_multi_polygons:
                geom_shape = geometry.shape(geom)
                geom_bounds = geom_shape.bounds
                mask_bounds = mask_multi_polygons.bounds

                # Skip if geometry's bounding box is completely outside mask's bounding box
                if (
                    geom_bounds[2] < mask_bounds[0]
                    or geom_bounds[0] > mask_bounds[2]  # max_x < mask_min_x
                    or geom_bounds[3] < mask_bounds[1]  # min_x > mask_max_x
                    or geom_bounds[1] > mask_bounds[3]  # max_y < mask_min_y
                ):  # min_y > mask_max_y
                    skip_count += 1
                    continue

            polygons = []
            if geom["type"] == "GeometryCollection":
                for single_geom in geom["geometries"]:
                    if single_geom["type"] == "MultiPolygon":
                        polygons.extend(single_geom["coordinates"])
                    elif single_geom["type"] == "Polygon":
                        polygons.append(single_geom["coordinates"])
            elif geom["type"] == "MultiPolygon":
                polygons = geom["coordinates"]
            else:
                polygons = [geom["coordinates"]]

            # check if building is inside the mask, only collect valid polygons
            if mask_multi_polygons is not None:
                valid_polygons = []
                found_points_outside = False
                for p in polygons:
                    poly = geometry.Polygon([(pt[0], pt[1]) for pt in p[0]])
                    if poly.is_valid:
                        if poly.within(mask_multi_polygons):
                            valid_polygons.append(p)
                        else:
                            found_points_outside = True
                polygons = valid_polygons

                if not polygons:
                    continue
                if found_points_outside:
                    continue

            # retrieve the minimum z coordinate
            min_elevation_feature = 9999
            for polygon in polygons:
                for point in polygon[0]:
                    if point[2] < min_elevation_feature:
                        min_elevation_feature = point[2]
                    
            feature_mesh = pv.PolyData()
            for polygon in polygons:
                
                exterior = polygon[0]
                n_points = len(exterior)

                # Create bottom and top vertices for this polygon
                points = []
                for point in exterior:
                    x, y, z = (
                        point[0],
                        point[1],
                        point[2],
                    )
                    assert math.fabs(x) + math.fabs(y) + math.fabs(z) > 1
                    points.append([x, y, z])  # top vertex

                # Create faces for this polygon
                faces = [ [n_points] + list(range(0, n_points)) ]

                # Create a new polydata for this polygon
                polygon_mesh = (
                    pv.PolyData(np.array(points), np.array(faces))
                )

                # Filter some faces
                face_normals = polygon_mesh.compute_normals(cell_normals=True).cell_normals
                if face_normals is not None and len(face_normals) > 0:  # Check if we have any faces
                    z_components = np.abs(face_normals[:, 2])  # Get z component of normals

                    # filter vertical walls (happens sometimes)
                    if np.all(z_components < 0.1):  # Threshold for "vertical"
                        continue  # Skip this polygon if all faces are vertical

                    # Filter "footprint faces"
                    if np.any(z_components > 0.95):  # Check for horizontal faces (z component close to 1)
                        # Get z coordinates of all points in the mesh
                        z_coords = np.array(points)[:, 2]
                        # Check if all points are close to min_elevation_feature
                        if np.all(np.abs(z_coords - min_elevation_feature) < 0.1):  # 10cm threshold
                            continue  # Skip this polygon if it's a horizontal face near ground level
                        
                if feature_mesh.n_points == 0:
                    feature_mesh = polygon_mesh
                else:
                    if polygon_mesh.n_points > 0:
                        feature_mesh = feature_mesh + polygon_mesh

            # Store building properties directly in user_dict
            building_id = feature["properties"].get("EntityHand")
            if not building_id:
                building_id = f"building_{building_counter}"
                building_counter += 1
            feature_mesh.user_dict["id"] = building_id
            feature_mesh.user_dict["layer"] = feature["properties"].get(
                "Layer", "unknown"
            )
            feature_mesh.user_dict["height"] = feature["properties"].get(
                "Height", 0
            )


            # Store building mesh in our list
            # count layer types
            if layer_lut.get(feature_layer_type):
                layer_lut[feature_layer_type].append(feature_mesh)
            else:
                layer_lut[feature_layer_type] = [ feature_mesh ]

    logger.info(f"Skipped buildings: {skip_count}")
    
    # Log counts for each layer type
    for layer_type, meshes in layer_lut.items():
        logger.info(f"Layer {layer_type}: {len(meshes)} buildings")
    
    # Clear progress bar
    progress_bar.empty()
    
    return layer_lut

def download_data(polygon, filetype="buildings", save_dir = DOWNLOADS_DIR):

    result = make_swisstopo_request(polygon, filetype=filetype)

    filenames = []
    if result:
        if len(result.get("items", [])) == 0:
            print("No TIF files found")
            all_downloads_successful = False
        else:
            all_downloads_successful = True

        os.makedirs(f"{save_dir}/{filetype}", exist_ok=True)
        with open(f"{save_dir}/{filetype}/files.txt", "w") as txtfile:
            for item in result["items"]:
                filename, filename_2d = download_tile(
                    item["ass_asset_href"], f"{save_dir}{filetype}"
                )
                if not filename:
                    all_downloads_successful = False
                txtfile.write(f"{filename}\n")
                filenames.append( (filename, filename_2d) )
        if not all_downloads_successful:
            print("Not all downloads have been successful!")
            return filenames
    else:
        print("Some problems here with the result")
        return filenames
    return filenames
    
def test(filetype="buildings"):
    save_dir = DOWNLOADS_DIR

    print(f"Downloading {filetype}")
    os.makedirs(f"{save_dir}/{filetype}", exist_ok=True)

    # Create example polygon from coordinates
    coords = [
        (8.647624, 47.290619),
        (8.649223, 47.290604),
        (8.649298, 47.290459),
        (8.647828, 47.290379),
        (8.647646, 47.290415),
        (8.647624, 47.290619)
    ]
    polygon = Polygon(coords)
    download_data(polygon)
    print("Thank you")


if __name__ == "__main__":
    test()
