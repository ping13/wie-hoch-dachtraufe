import gettext
import streamlit as st
from pathlib import Path

def get_translation():
    """Get translation function for current language"""
    if not hasattr(st.session_state, '_translation_func'):
        setup_translation()
    return st.session_state._translation_func

def setup_translation():
    """Setup translation for current language"""
    language = st.session_state.get('language', 'de')
    localedir = Path(__file__).parent / 'locale'
    
    try:
        translation = gettext.translation(
            'messages', 
            localedir=localedir, 
            languages=[language],
            fallback=False
        )
        st.session_state._translation_func = translation.gettext
    except Exception as e:
        print(f"Translation error: {e}")
        st.session_state._translation_func = gettext.gettext

def _(text):
    """Translation function that always gets current language"""
    return get_translation()(text)

def update_translation():
    """Update translation when language changes"""
    if hasattr(st.session_state, '_translation_func'):
        del st.session_state._translation_func
    setup_translation()
