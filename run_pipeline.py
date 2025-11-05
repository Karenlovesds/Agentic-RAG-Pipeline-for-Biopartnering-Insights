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
  python run_pipeline.py web                       # Start web interface
  python run_pipeline.py web --port 8502          # Start web interface on custom port
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run complete pipeline')
    run_parser.add_argument('--force', action='store_true', help='Force refresh all steps')
    run_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Web command
    web_parser = subparsers.add_parser('web', help='Start web interface')
    web_parser.add_argument('--port', type=int, default=8501, help='Port to run on (default: 8501)')
    web_parser.add_argument('--host', default='localhost', help='Host to bind to (default: localhost)')
    
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
        
    elif args.command == 'web':
        import subprocess
        cmd = [
            sys.executable, '-m', 'streamlit', 'run', 
            'scripts/main/streamlit_app.py',
            '--server.port', str(args.port),
            '--server.address', args.host
        ]
        subprocess.run(cmd)
            
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == '__main__':
    main()

