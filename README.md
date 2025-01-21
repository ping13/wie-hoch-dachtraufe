# Roof Heights Analyzer

A Streamlit web application that analyzes and visualizes the heights of building roofs in Switzerland using Swisstopo data.

## Features

- Interactive map selection of areas in Switzerland
- 3D visualization of building roofs
- Height distribution analysis
- KML export for Google Earth viewing
- Automatic data fetching from Swisstopo

## Requirements

- Python 3.8+
- GDAL
- Various Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ping13/wie-hoch-dachtraufe.git
cd wie-hoch-dachtraufe
```

Make sure you have [`uv`](https://github.com/astral-sh/uv) installed.

## Usage

1. Run the Streamlit app:
```bash
make devserver
```

2. Select an area on the map (must be less than 100,000 m²)
3. Click "Calculate" to analyze the roof heights
4. View the 3D model and height distribution
5. Download the KML file for and drag it onto https://map.geo.admin.ch/ to
   click on roof components and get the individual roof heights

## Data Sources

This application uses data from:
- [Swisstopo Buildings 3D](https://www.swisstopo.admin.ch/en/geodata/landscape/buildings3d.html)
- [SwissALTI3D](https://www.swisstopo.admin.ch/en/geodata/height/alti3d.html)

## License

© 2025 [Stephan Heuel](https://blog.heuel.org/pages/contact)

## Acknowledgments

Based on the [Wo sind Briefkästen](https://wieviele-briefkaesten-gibt-es.streamlit.app) project.
