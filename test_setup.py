"""Simple test to verify the setup works correctly."""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

def test_imports():
    """Test that all main modules can be imported."""
    try:
        # Test config import
        from config import settings
        print("✅ Config import successful")
        
        # Test models import
        from src.models import Base, engine, get_session
        print("✅ Models import successful")
        
        # Test data collection import
        from src.data_collection import BaseCollector, ClinicalTrialsCollector
        print("✅ Data collection import successful")
        
        # Test database creation
        from src.models.database import create_tables
        create_tables()
        print("✅ Database tables created successfully")
        
        print("\n🎉 All tests passed! The setup is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_streamlit_import():
    """Test Streamlit import."""
    try:
        import streamlit as st
        print("✅ Streamlit import successful")
        return True
    except ImportError as e:
        print(f"❌ Streamlit import failed: {e}")
        print("Please install Streamlit: pip install streamlit")
        return False


if __name__ == "__main__":
    print("🧬 Testing Biopartnering Insights Pipeline Setup\n")
    
    success = True
    success &= test_imports()
    success &= test_streamlit_import()
    
    if success:
        print("\n🚀 Setup is complete! You can now:")
        print("1. Run 'python main.py' to initialize the database")
        print("2. Run 'streamlit run streamlit_app.py' to launch the UI")
        print("3. Set up your .env file with OpenAI API key")
    else:
        print("\n❌ Setup incomplete. Please check the errors above.")
        sys.exit(1)
