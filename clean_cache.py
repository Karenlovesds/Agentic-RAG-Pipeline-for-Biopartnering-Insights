   python run_pipeline.py
#!/usr/bin/env python3
"""
Clean Cache Script for Biopartnering Insights Pipeline

This script clears all cache files and databases to start fresh.
Run this when you want to reset the pipeline with only cancer/oncology data.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Clean cache and database files."""
    print("🧹 Biopartnering Insights Pipeline - Cache Cleaner")
    print("=" * 60)
    
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    os.chdir(project_root)
    
    print(f"📁 Working directory: {project_root}")
    print()
    
    # Files and directories to clean
    items_to_remove = [
        "biopartnering_insights.db",
        "chroma_db",
        "outputs/biopharma_drugs.csv",
        "outputs/drug_collection_summary.txt",
        "outputs/biopartnering_data.csv",
        "logs/biopartnering_insights.log",
        "monitoring/pipeline_state.json"
    ]
    
    print("🗑️  Clearing cache and database files...")
    print("-" * 40)
    
    removed_count = 0
    for item in items_to_remove:
        item_path = Path(item)
        if item_path.exists():
            if item_path.is_file():
                item_path.unlink()
                print(f"   ✅ Removed file: {item}")
                removed_count += 1
            elif item_path.is_dir():
                import shutil
                shutil.rmtree(item_path)
                print(f"   ✅ Removed directory: {item}")
                removed_count += 1
        else:
            print(f"   ⚪ Not found: {item}")
    
    print()
    print(f"🎉 Cleanup complete! Removed {removed_count} items.")
    print()
    
    # Show next steps
    print("🚀 Next Steps - Rerun your pipeline:")
    print("=" * 60)
    print()
    print("1. Run the complete pipeline:")
    print("   python run_pipeline.py")
    print()
    print("2. Or run individual components:")
    print("   # Data collection only")
    print("   python -m scripts.main.run_complete_pipeline")
    print()
    print("   # Start Streamlit dashboard")
    print("   streamlit run scripts/main/streamlit_app.py")
    print()
    print("3. The pipeline will now collect only cancer/oncology drugs")
    print("   and exclude diabetes drugs like metformin.")
    print()
    print("✨ Your pipeline is ready for a fresh start!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cleanup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        sys.exit(1)
