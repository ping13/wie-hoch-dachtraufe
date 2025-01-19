import os
import shutil
import atexit
import tempfile
from typing import Literal
import streamlit.components.v1 as components


parent_dir = os.path.dirname(os.path.abspath(__file__))

class ThreeDComponent:
    def __init__(self):
        """Initialize the ThreeDComponent class and set up the environment."""
        self.has_setup = False
        self.temp_folder = None
        self.current_temp_files = []  # List to track created temporary files
        self.setup()  # Automatically call setup upon initialization

    def setup(self):
        """Set up the necessary directories for the Streamlit_3d component."""
        if not self.has_setup:

            ### Create a unique temporary directory for the component
            if self.temp_folder and os.path.exists(self.temp_folder):
                shutil.rmtree(self.temp_folder)
            self.temp_folder = tempfile.mkdtemp(suffix='_st_3d')
            
            ### Copy the current component directory to the temporary folder
            for file in os.listdir(parent_dir):
                src = parent_dir + os.sep + file
                dst = self.temp_folder + os.sep + file
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy(src, dst)

            ### Mark setup as complete to prevent re-initialization
            self.has_setup = True  

    def threed_from_text(self, 
                         text: str,
                         suffix: str,
                         **kwargs):
        """
        Create a 3D ThreeD viewer component in Streamlit using a text-based ThreeD file.

        Parameters:
        ----------
        text : str
            The text content of the ThreeD file to render.
        **kwargs :
            Additional arguments passed to the Streamlit component.

        Returns:
        -------
        bool
            True if the component is successfully created, False otherwise.
        """
        self.setup()  # Ensure the environment is set up
        file_path = []  # The path of the created temporary file
        if text is not None:
            
            ### Create a temporary file in the temporary 3d folder
            try:
                with tempfile.NamedTemporaryFile(dir=self.temp_folder, suffix=suffix, delete=False) as temp_file:
                    if isinstance(text, bytes):
                        temp_file.write(text)
                    elif isinstance(text, str):
                        # Write the text content to the file
                        temp_file.write(text.encode("utf-8"))  
                    else:
                        raise ValueError(f"Invalid text type for the 3d file")
                    # Ensure all data is written to disk
                    temp_file.flush()  
                    # Store the relative path
                    file_path = temp_file.name.split(os.sep)[-1]  
                    # Keep track of the file for cleanup
                    self.current_temp_files.append(temp_file.name)  

            except Exception as e:
                print(f"Error processing the 3d file: {e}")
                _component_func(files_text='', height=height **kwargs)
                return False

        ### Call the 3d component with the list of file paths and their types
        _component_func(file_path=file_path, 
                        **kwargs)
        return True

    def threed_from_file(self, 
                         file_path: str,
                         suffix: str,
                         **kwargs):
        """
        Render a 3D ThreeD file in Streamlit using a file path.

        Parameters:
        ----------
        file_path : str
            The path to the ThreeD file to render.
        **kwargs :
            Additional arguments passed to the Streamlit component.

        Returns:
        -------
        bool
            True if the component is successfully created, False otherwise.
        """

        file_text = None

        ### Read the file content and add it to the list
        if file_path is not None:
            with open(file_path, "rb") as f:
                file_text = f.read()  
        
        ### Pass the file content to threed_from_text
        return self.threed_from_text(text=file_text,
                                     suffix=suffix,
                                     **kwargs)

    def cleanup_temp_files(self):
        """Clean up temporary files and directories created during the session."""
        ### Remove the entire temporary directory
        try:
            if os.path.exists(self.temp_folder):
                shutil.rmtree(self.temp_folder)  

        except Exception as e:
            print(f"Error deleting temporary streamlit-3d folder {self.temp_folder}: {e}")
            # If the directory can't be deleted, try to delete each file individually
            for temp_file in self.current_temp_files:
                try: # Remove individual temporary files
                    os.unlink(temp_file)  
                except Exception as e:
                    print(f"Error deleting temp file {temp_file}: {e}")

# Instantiate the ThreeDComponent class to set up the environment and handle resources
threed_component = ThreeDComponent()
# Register the cleanup function to be called automatically when the program exits
atexit.register(threed_component.cleanup_temp_files)


### Declare the functions to be used in the Streamlit script
threed_from_text = threed_component.threed_from_text
threed_from_file = threed_component.threed_from_file

# Declare the Streamlit component and link it to the temporary directory
_component_func = components.declare_component(
    "streamlit_3d",
    path=threed_component.temp_folder,
)
