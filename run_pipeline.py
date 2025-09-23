#!/usr/bin/env python3
"""
Main entry point for the Biopartnering Insights Pipeline

This script provides a unified interface to run the pipeline with different options.
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_subprocess(cmd, verbose=False):
    """Helper function to run subprocess commands."""
    if verbose:
        cmd.append('--verbose')
    subprocess.run(cmd)


def clean_cache():
    """Clean cache and database files to start fresh."""
    import shutil
    from pathlib import Path
    
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
    print("   python run_pipeline.py run")
    print()
    print("2. Or run individual components:")
    print("   python run_pipeline.py data-collect")
    print("   python run_pipeline.py process")
    print("   python run_pipeline.py export")
    print()
    print("3. Start Streamlit dashboard:")
    print("   streamlit run scripts/main/streamlit_app.py")
    print()
    print("✨ Your pipeline is ready for a fresh start!")


def run_scheduled_pipeline(interval_hours: int = 720, max_runtime_hours: int = 2, verbose: bool = False):
    """Run the pipeline on a schedule with intelligent change detection."""
    import asyncio
    import time
    from datetime import datetime, timedelta
    from loguru import logger
    
    # Setup logging
    if verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    logger.info(f"🕐 Starting scheduled pipeline runner (interval: {interval_hours}h)")
    
    try:
        while True:
            try:
                # Check if we should run (every interval_hours)
                # For simplicity, we'll run every interval_hours
                logger.info(f"⏰ Running scheduled pipeline (interval: {interval_hours}h)")
                
                # Run the complete pipeline
                import subprocess
                cmd = [sys.executable, 'scripts/main/run_complete_pipeline.py']
                if verbose:
                    cmd.append('--verbose')
                
                start_time = datetime.now()
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=max_runtime_hours * 3600)
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if result.returncode == 0:
                    logger.info(f"✅ Scheduled run completed successfully in {duration:.2f} seconds")
                    if verbose and result.stdout:
                        logger.info(f"Output: {result.stdout}")
                else:
                    logger.error(f"❌ Scheduled run failed: {result.stderr}")
                
                # Wait for next run
                logger.info(f"😴 Sleeping for {interval_hours} hours until next run...")
                time.sleep(interval_hours * 3600)  # Convert hours to seconds
                
            except subprocess.TimeoutExpired:
                logger.error(f"❌ Pipeline timed out after {max_runtime_hours} hours")
                logger.info(f"😴 Sleeping for {interval_hours} hours until next run...")
                time.sleep(interval_hours * 3600)
            except Exception as e:
                logger.error(f"💥 Error in scheduled runner: {e}")
                logger.info("😴 Sleeping for 1 hour before retrying...")
                time.sleep(3600)  # Wait 1 hour before retrying
                
    except KeyboardInterrupt:
        logger.info("👋 Shutting down scheduled pipeline gracefully...")
    except Exception as e:
        logger.error(f"💥 Fatal error in scheduled pipeline: {e}")
        sys.exit(1)


def run_validation(db_path: str, gt_path: str, output_dir: str, verbose: bool = False):
    """Run ground truth validation directly."""
    from src.validation.ground_truth_validator import GroundTruthValidator
    from loguru import logger
    
    # Setup logging
    if verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    try:
        logger.info("🔍 Starting ground truth validation...")
        
        # Create validator
        validator = GroundTruthValidator(db_path=db_path, ground_truth_path=gt_path)
        
        # Run validation
        results = validator.run_full_validation()
        
        # Save results
        validator.save_results()
        
        # Generate and print report
        report = validator.generate_report()
        print(report)
        
        # Save report
        import os
        os.makedirs(output_dir, exist_ok=True)
        with open(f"{output_dir}/validation_report.txt", "w") as f:
            f.write(report)
        
        logger.info("✅ Validation completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        raise


def run_overlap_analysis(db_path: str, gt_path: str, output_dir: str, verbose: bool = False):
    """Run overlap analysis directly."""
    import pandas as pd
    from sqlalchemy.orm import Session
    from loguru import logger
    from src.models.database import get_db
    from src.models.entities import Company, Drug, ClinicalTrial, Target
    
    # Setup logging
    if verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    try:
        logger.info("📊 Starting overlap analysis...")
        
        # Load ground truth companies
        gt_df = pd.read_excel(gt_path)
        gt_companies = gt_df['Partner'].dropna().unique().tolist()
        logger.info(f"Loaded {len(gt_companies)} companies from Ground Truth")
        
        # Load pipeline data
        db = get_db()
        pipeline_companies = db.query(Company).all()
        pipeline_company_names = [c.name for c in pipeline_companies]
        
        # Find overlaps
        exact_matches = []
        partial_matches = []
        
        for gt_company in gt_companies:
            # Check for exact matches
            exact_match = None
            for pipeline_company in pipeline_companies:
                if pipeline_company.name.lower() == gt_company.lower():
                    exact_match = pipeline_company
                    break
            
            if exact_match:
                exact_matches.append({
                    'ground_truth_company': gt_company,
                    'pipeline_company': exact_match.name,
                    'match_type': 'exact',
                    'drug_count': len(exact_match.drugs),
                    'trial_count': len(exact_match.clinical_trials)
                })
            else:
                # Check for partial matches
                for pipeline_company in pipeline_companies:
                    if (gt_company.lower() in pipeline_company.name.lower() or 
                        pipeline_company.name.lower() in gt_company.lower()):
                        partial_matches.append({
                            'ground_truth_company': gt_company,
                            'pipeline_company': pipeline_company.name,
                            'match_type': 'partial',
                            'drug_count': len(pipeline_company.drugs),
                            'trial_count': len(pipeline_company.clinical_trials)
                        })
                        break
        
        # Combine results
        all_matches = exact_matches + partial_matches
        results_df = pd.DataFrame(all_matches)
        
        # Save results
        import os
        os.makedirs(output_dir, exist_ok=True)
        results_df.to_csv(f"{output_dir}/company_overlap_analysis.csv", index=False)
        
        # Print summary
        print(f"\n📊 Overlap Analysis Results:")
        print(f"Exact matches: {len(exact_matches)}")
        print(f"Partial matches: {len(partial_matches)}")
        print(f"Total overlaps: {len(all_matches)}")
        print(f"Ground truth companies: {len(gt_companies)}")
        print(f"Pipeline companies: {len(pipeline_companies)}")
        
        logger.info("✅ Overlap analysis completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Overlap analysis failed: {e}")
        raise


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
  python run_pipeline.py validate                  # Run ground truth validation
  python run_pipeline.py overlap-analysis          # Run overlap analysis
  python run_pipeline.py gt-validator              # Run ground truth validator directly
  python run_pipeline.py quick-validate            # Run quick validation wrapper
  python run_pipeline.py regenerate-summary        # Regenerate drug collection summary
  python run_pipeline.py clean-cache               # Clean cache and database files
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run complete pipeline')
    run_parser.add_argument('--force', action='store_true', help='Force refresh all steps')
    run_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Run scheduled pipeline')
    schedule_parser.add_argument('--interval', type=int, default=720, help='Interval in hours (default: 720 = 1 month)')
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
    
    # Validation command
    validation_parser = subparsers.add_parser('validate', help='Run ground truth validation')
    validation_parser.add_argument('--db-path', default='biopartnering_insights.db', help='Path to database file')
    validation_parser.add_argument('--gt-path', default='data/Pipeline_Ground_Truth.xlsx', help='Path to ground truth Excel file')
    validation_parser.add_argument('--output-dir', default='outputs', help='Output directory for results')
    validation_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Overlap analysis command
    overlap_parser = subparsers.add_parser('overlap-analysis', help='Run overlap analysis between ground truth and pipeline data')
    overlap_parser.add_argument('--db-path', default='biopartnering_insights.db', help='Path to database file')
    overlap_parser.add_argument('--gt-path', default='data/Pipeline_Ground_Truth.xlsx', help='Path to ground truth Excel file')
    overlap_parser.add_argument('--output-dir', default='outputs', help='Output directory for results')
    overlap_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Ground truth validator command
    gt_validator_parser = subparsers.add_parser('gt-validator', help='Run ground truth validator directly')
    gt_validator_parser.add_argument('--db-path', default='biopartnering_insights.db', help='Path to database file')
    gt_validator_parser.add_argument('--gt-path', default='data/Pipeline_Ground_Truth.xlsx', help='Path to ground truth Excel file')
    gt_validator_parser.add_argument('--output-dir', default='outputs', help='Output directory for results')
    gt_validator_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Quick validation command
    quick_validation_parser = subparsers.add_parser('quick-validate', help='Run quick validation (wrapper)')
    quick_validation_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Drug summary regeneration command
    drug_summary_parser = subparsers.add_parser('regenerate-summary', help='Regenerate drug collection summary')
    drug_summary_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # Clean cache command
    clean_cache_parser = subparsers.add_parser('clean-cache', help='Clean cache and database files to start fresh')
    clean_cache_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
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
        run_subprocess(cmd, args.verbose)
        
    elif args.command == 'schedule':
        run_scheduled_pipeline(args.interval, args.max_runtime, args.verbose)
        
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
        from src.processing.csv_export import export_drugs_dashboard
        from src.models.database import get_db
        
        db = get_db()
        try:
            # Ensure outputs directory exists
            Path("outputs").mkdir(exist_ok=True)
            
            # Export drugs dashboard data
            export_drugs_dashboard(db, 'outputs/drugs_dashboard.csv')
            print("✅ Drugs dashboard data exported: outputs/drugs_dashboard.csv")
            
        finally:
            db.close()
            
    elif args.command == 'maintenance':
        from src.maintenance.maintenance_orchestrator import run_maintenance
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
        run_subprocess(cmd, args.verbose)
        
    elif args.command == 'validate':
        run_validation(args.db_path, args.gt_path, args.output_dir, args.verbose)
        
    elif args.command == 'overlap-analysis':
        run_overlap_analysis(args.db_path, args.gt_path, args.output_dir, args.verbose)
        
    elif args.command == 'gt-validator':
        import subprocess
        cmd = [sys.executable, 'src/validation/ground_truth_validator.py']
        if args.db_path != 'biopartnering_insights.db':
            cmd.extend(['--db-path', args.db_path])
        if args.gt_path != 'data/Pipeline_Ground_Truth.xlsx':
            cmd.extend(['--gt-path', args.gt_path])
        if args.output_dir != 'outputs':
            cmd.extend(['--output-dir', args.output_dir])
        run_subprocess(cmd, args.verbose)
        
    elif args.command == 'quick-validate':
        import subprocess
        cmd = [sys.executable, 'run_validation.py']
        run_subprocess(cmd, args.verbose)
        
    elif args.command == 'regenerate-summary':
        import subprocess
        cmd = [sys.executable, 'src/processing/regenerate_drug_summary.py']
        run_subprocess(cmd, args.verbose)
        
    elif args.command == 'clean-cache':
        clean_cache()
            
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == '__main__':
    main()

