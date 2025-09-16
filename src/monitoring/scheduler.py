"""Scheduler for automated pipeline runs and monitoring."""

import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable
from loguru import logger
from .change_detector import WebsiteChangeDetector
from ..data_collection.orchestrator import DataCollectionOrchestrator
from ..models.database import get_db
from ..models.entities import Document


class PipelineScheduler:
    """Schedules and manages automated pipeline runs."""
    
    def __init__(self, enable_monitoring: bool = True, enable_weekly_runs: bool = True):
        self.enable_monitoring = enable_monitoring
        self.enable_weekly_runs = enable_weekly_runs
        self.change_detector = WebsiteChangeDetector()
        self.running = False
        self.scheduler_thread = None
        
        # Setup logging
        self._setup_logging()
        
        # Configure schedules
        self._setup_schedules()
    
    def _setup_logging(self):
        """Setup logging for scheduler."""
        log_file = Path("logs/scheduler.log")
        log_file.parent.mkdir(exist_ok=True)
        
        logger.add(
            str(log_file),
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
    
    def _setup_schedules(self):
        """Setup scheduled tasks."""
        if self.enable_monitoring:
            # Check for website changes every 6 hours
            schedule.every(6).hours.do(self._check_and_update)
            logger.info("📅 Scheduled website monitoring every 6 hours")
        
        if self.enable_weekly_runs:
            # Full pipeline run every Sunday at 2 AM
            schedule.every().sunday.at("02:00").do(self._weekly_full_run)
            logger.info("📅 Scheduled weekly full run every Sunday at 2 AM")
            
            # Light update every Wednesday at 2 AM
            schedule.every().wednesday.at("02:00").do(self._weekly_light_update)
            logger.info("📅 Scheduled weekly light update every Wednesday at 2 AM")
    
    def _check_and_update(self):
        """Check for changes and update if needed."""
        try:
            logger.info("🔍 Starting scheduled change detection...")
            changes = self.change_detector.check_for_changes()
            
            if changes:
                logger.info(f"🔄 {len(changes)} changes detected, triggering update...")
                success = self.change_detector.trigger_pipeline_update(changes)
                if success:
                    logger.info("✅ Pipeline update completed successfully")
                else:
                    logger.error("❌ Pipeline update failed")
            else:
                logger.info("✅ No changes detected")
                
        except Exception as e:
            logger.error(f"❌ Error in scheduled change detection: {e}")
    
    def _weekly_full_run(self):
        """Weekly full pipeline run."""
        try:
            logger.info("🚀 Starting weekly full pipeline run...")
            
            # Run all data sources
            sources = ['clinical_trials', 'drugs', 'fda', 'company_websites']
            orchestrator = DataCollectionOrchestrator()
            
            total_documents = 0
            for source in sources:
                try:
                    result = orchestrator.run_full_collection([source])
                    count = result.get(source, 0)
                    total_documents += count
                    logger.info(f"✅ {source}: {count} documents")
                except Exception as e:
                    logger.error(f"❌ Error collecting {source}: {e}")
            
            # Log the run
            self._log_scheduled_run("weekly_full", total_documents)
            logger.info(f"🎉 Weekly full run completed: {total_documents} total documents")
            
        except Exception as e:
            logger.error(f"❌ Error in weekly full run: {e}")
    
    def _weekly_light_update(self):
        """Weekly light update (FDA and recent clinical trials only)."""
        try:
            logger.info("🔄 Starting weekly light update...")
            
            # Run only FDA and recent clinical trials
            sources = ['fda', 'clinical_trials']
            orchestrator = DataCollectionOrchestrator()
            
            total_documents = 0
            for source in sources:
                try:
                    result = orchestrator.run_full_collection([source])
                    count = result.get(source, 0)
                    total_documents += count
                    logger.info(f"✅ {source}: {count} documents")
                except Exception as e:
                    logger.error(f"❌ Error collecting {source}: {e}")
            
            # Log the run
            self._log_scheduled_run("weekly_light", total_documents)
            logger.info(f"🎉 Weekly light update completed: {total_documents} total documents")
            
        except Exception as e:
            logger.error(f"❌ Error in weekly light update: {e}")
    
    def _log_scheduled_run(self, run_type: str, total_documents: int):
        """Log scheduled run details."""
        run_log = {
            'timestamp': datetime.now().isoformat(),
            'run_type': run_type,
            'total_documents': total_documents,
            'triggered_by': 'scheduler'
        }
        
        # Save to log file
        log_file = Path("logs/scheduled_runs.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(run_log) + '\n')
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("🚀 Pipeline scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("⏹️ Pipeline scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        logger.info("🔄 Scheduler loop started")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"❌ Error in scheduler loop: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            'running': self.running,
            'monitoring_enabled': self.enable_monitoring,
            'weekly_runs_enabled': self.enable_weekly_runs,
            'next_jobs': [str(job) for job in schedule.jobs],
            'monitoring_status': self.change_detector.get_monitoring_status()
        }
    
    def run_now(self, run_type: str = "full") -> bool:
        """Manually trigger a run now."""
        try:
            if run_type == "full":
                self._weekly_full_run()
            elif run_type == "light":
                self._weekly_light_update()
            elif run_type == "monitor":
                self._check_and_update()
            else:
                logger.error(f"Unknown run type: {run_type}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error in manual run: {e}")
            return False


def create_scheduler(enable_monitoring: bool = True, enable_weekly_runs: bool = True) -> PipelineScheduler:
    """Create and configure a pipeline scheduler."""
    return PipelineScheduler(enable_monitoring, enable_weekly_runs)

