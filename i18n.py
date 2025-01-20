import gettext
import streamlit as st
from pathlib import Path
import subprocess

def compile_translations():
    """Compile .po files to .mo files"""
    locale_dir = Path(__file__).parent / 'locale'
    for lang in ['de', 'fr', 'it']:
        po_file = locale_dir / lang / 'LC_MESSAGES' / 'messages.po'
        mo_file = locale_dir / lang / 'LC_MESSAGES' / 'messages.mo'
        if po_file.exists():
            try:
                subprocess.run(['msgfmt', str(po_file), '-o', str(mo_file)], check=True)
                print(f"Successfully compiled translations for {lang}")
            except Exception as e:
                print(f"Failed to compile translations for {lang}: {e}")

def get_translation():
    """Get translation function for current language"""
    # Always setup translation to ensure we have the latest
    setup_translation()
    return st.session_state._translation_func

def setup_translation():
    """Setup translation for current language"""
    language = st.session_state.get('language', 'de')
    localedir = Path(__file__).parent / 'locale'
    
    try:
        # Recompile translations
        compile_translations()
        
        # Clear gettext cache
        gettext._translations.clear()
        
        # First try with the specific language
        try:
            translation = gettext.translation(
                'messages', 
                localedir=localedir, 
                languages=[language]
            )
            st.session_state._translation_func = translation.gettext
            print(f"Successfully loaded translations for {language}")
        except FileNotFoundError:
            # Fallback to default language
            print(f"No translations found for {language}, falling back to default")
            st.session_state._translation_func = gettext.gettext
            
    except Exception as e:
        print(f"Translation setup error: {e}")
        st.session_state._translation_func = gettext.gettext

def _(text):
    """Translation function that always gets current language"""
    return get_translation()(text)

def update_translation():
    """Update translation when language changes"""
    setup_translation()
    # Force Streamlit to rerun
    st.rerun()
