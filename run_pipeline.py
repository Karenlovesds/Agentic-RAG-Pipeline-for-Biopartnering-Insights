#!/usr/bin/env python3
"""
Main entry point for the Biopartnering Insights Pipeline

This script provides a unified interface to run the pipeline with different options.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    parser = argparse.ArgumentParser(
        description="Biopartnering Insights Pipeline - Main Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py --help                    # Show this help
  python run_pipeline.py run                       # Run complete pipeline once
  python run_pipeline.py run --force               # Force refresh all data
  python run_pipeline.py schedule                  # Run scheduled pipeline
  python run_pipeline.py web                       # Start web interface
  python run_pipeline.py data-collect              # Run data collection only
  python run_pipeline.py process                   # Run processing only
  python run_pipeline.py export                    # Run exports only
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run complete pipeline')
    run_parser.add_argument('--force', action='store_true', help='Force refresh all steps')
    run_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Run scheduled pipeline')
    schedule_parser.add_argument('--interval', type=int, default=6, help='Interval in hours (default: 6)')
    schedule_parser.add_argument('--max-runtime', type=int, default=2, help='Max runtime in hours (default: 2)')
    schedule_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Web command
    web_parser = subparsers.add_parser('web', help='Start web interface')
    web_parser.add_argument('--port', type=int, default=8501, help='Port to run on (default: 8501)')
    web_parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    
    # Data collection command
    data_parser = subparsers.add_parser('data-collect', help='Run data collection only')
    data_parser.add_argument('--sources', nargs='+', 
                           choices=['clinical_trials', 'fda', 'company_websites', 'drugs'],
                           default=['clinical_trials', 'fda', 'company_websites', 'drugs'],
                           help='Data sources to collect from')
    data_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Run processing only')
    process_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Run exports only')
    export_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Maintenance command
    maintenance_parser = subparsers.add_parser('maintenance', help='Run database maintenance only')
    maintenance_parser.add_argument('--tasks', nargs='+', 
                                  choices=['drug_capitalization', 'drug_validation', 'drug_deduplication'],
                                  help='Specific maintenance tasks to run (default: all)')
    maintenance_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Drug summary command
    summary_parser = subparsers.add_parser('drug-summary', help='Generate drug collection summary only')
    summary_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Change to project root directory
    os.chdir(project_root)
    
    # Add project root to Python path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Also add the current working directory
    if '.' not in sys.path:
        sys.path.insert(0, '.')
    
    if args.command == 'run':
        import subprocess
        cmd = [sys.executable, 'scripts/main/run_complete_pipeline.py']
        if args.force:
            cmd.append('--force')
        if args.verbose:
            cmd.append('--verbose')
        subprocess.run(cmd)
        
    elif args.command == 'schedule':
        import subprocess
        cmd = [sys.executable, 'scripts/main/run_scheduled_pipeline.py']
        cmd.extend(['--interval', str(args.interval)])
        cmd.extend(['--max-runtime', str(args.max_runtime)])
        if args.verbose:
            cmd.append('--verbose')
        subprocess.run(cmd)
        
    elif args.command == 'web':
        import subprocess
        cmd = [
            sys.executable, '-m', 'streamlit', 'run', 
            'scripts/main/streamlit_app.py',
            '--server.port', str(args.port),
            '--server.address', args.host
        ]
        subprocess.run(cmd)
        
    elif args.command == 'data-collect':
        import asyncio
        from src.data_collection.orchestrator import DataCollectionOrchestrator
        
        async def run_data_collection():
            orchestrator = DataCollectionOrchestrator()
            results = await orchestrator.run_full_collection(args.sources)
            print(f"Data collection completed: {results}")
        
        asyncio.run(run_data_collection())
        
    elif args.command == 'process':
        from src.processing.pipeline import run_processing
        from src.models.database import get_db
        
        db = get_db()
        try:
            results = run_processing(db)
            print(f"Processing completed: {results}")
        finally:
            db.close()
            
    elif args.command == 'export':
        from src.processing.csv_export import export_drug_table, export_basic
        from src.models.database import get_db
        
        db = get_db()
        try:
            # Ensure outputs directory exists
            Path("outputs").mkdir(exist_ok=True)
            
            # Export drug table
            export_drug_table(db, 'outputs/biopharma_drugs.csv')
            print("✅ Drug table exported: outputs/biopharma_drugs.csv")
            
            # Export basic data
            export_basic(db, 'outputs/basic_export.csv')
            print("✅ Basic data exported: outputs/basic_export.csv")
            
        finally:
            db.close()
            
    elif args.command == 'maintenance':
        from scripts.maintenance.maintenance_orchestrator import run_maintenance
        import asyncio
        
        try:
            results = asyncio.run(run_maintenance(args.tasks))
            print(f"\n🔧 Maintenance Results:")
            print(f"Total tasks: {results['total_tasks']}")
            print(f"Successful: {results['successful_tasks']}")
            print(f"Failed: {results['failed_tasks']}")
            
            for task_name, task_result in results['task_results'].items():
                status = "✅" if task_result['success'] else "❌"
                print(f"{status} {task_name}: {task_result}")
                
        except Exception as e:
            print(f"❌ Maintenance failed: {e}")
            
    elif args.command == 'drug-summary':
        import subprocess
        cmd = [sys.executable, 'src/processing/regenerate_drug_summary.py']
        if args.verbose:
            cmd.append('--verbose')
        subprocess.run(cmd)
            
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == '__main__':
    main()

