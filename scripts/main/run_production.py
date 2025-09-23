#!/usr/bin/env python3
"""Production runner for the Biopartnering Insights Pipeline with monitoring and scheduling."""

import sys
import time
import argparse
from pathlib import Path
from loguru import logger
from src.monitoring.scheduler import create_scheduler
from src.monitoring.notifications import create_notification_manager
from src.monitoring.change_detector import WebsiteChangeDetector
from common_utils import SignalHandler, setup_production_logging


class ProductionRunner:
    """Production runner with monitoring, scheduling, and notifications."""
    
    def __init__(self, enable_monitoring: bool = True, enable_weekly_runs: bool = True, enable_notifications: bool = True):
        self.enable_monitoring = enable_monitoring
        self.enable_weekly_runs = enable_weekly_runs
        self.enable_notifications = enable_notifications
        self.running = False
        
        # Setup logging
        setup_production_logging()
        
        # Initialize components
        self.scheduler = create_scheduler(enable_monitoring, enable_weekly_runs)
        self.notification_manager = create_notification_manager() if enable_notifications else None
        self.change_detector = WebsiteChangeDetector()
        
        # Setup signal handling
        self.signal_handler = SignalHandler()
    
    # Logging and signal handling moved to common_utils.py
    
    def start(self):
        """Start the production pipeline."""
        try:
            logger.info("🚀 Starting Biopartnering Insights Pipeline in Production Mode")
            logger.info(f"📊 Monitoring: {'Enabled' if self.enable_monitoring else 'Disabled'}")
            logger.info(f"📅 Weekly Runs: {'Enabled' if self.enable_weekly_runs else 'Disabled'}")
            logger.info(f"📧 Notifications: {'Enabled' if self.enable_notifications else 'Disabled'}")
            
            self.running = True
            
            # Start scheduler
            self.scheduler.start()
            
            # Send startup notification
            if self.notification_manager:
                self.notification_manager.send_scheduled_run_notification(
                    "startup", 0, True
                )
            
            # Initial change check
            if self.enable_monitoring:
                logger.info("🔍 Performing initial change detection...")
                changes = self.change_detector.check_for_changes()
                if changes:
                    logger.info(f"🔄 {len(changes)} changes detected on startup")
                    self.scheduler.change_detector.trigger_pipeline_update(changes)
            
            # Main loop
            self._main_loop()
            
        except Exception as e:
            logger.error(f"❌ Error in production runner: {e}")
            if self.notification_manager:
                self.notification_manager.send_error_notification(
                    "production_startup", str(e)
                )
            raise
    
    def _main_loop(self):
        """Main production loop."""
        logger.info("🔄 Production loop started")
        
        while self.signal_handler.running:
            try:
                # Check scheduler status
                status = self.scheduler.get_status()
                
                # Log status every hour
                if hasattr(self, '_last_status_log'):
                    if time.time() - self._last_status_log > 3600:  # 1 hour
                        logger.info(f"📊 Scheduler Status: {status}")
                        self._last_status_log = time.time()
                else:
                    self._last_status_log = time.time()
                
                # Sleep for a minute
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                if self.notification_manager:
                    self.notification_manager.send_error_notification(
                        "main_loop", str(e)
                    )
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def stop(self):
        """Stop the production pipeline."""
        logger.info("⏹️ Stopping production pipeline...")
        self.running = False
        
        # Stop scheduler
        self.scheduler.stop()
        
        # Send shutdown notification
        if self.notification_manager:
            self.notification_manager.send_scheduled_run_notification(
                "shutdown", 0, True
            )
        
        logger.info("✅ Production pipeline stopped")
    
    def run_once(self, run_type: str = "full"):
        """Run the pipeline once and exit."""
        logger.info(f"🔄 Running pipeline once: {run_type}")
        
        try:
            success = self.scheduler.run_now(run_type)
            if success:
                logger.info("✅ One-time run completed successfully")
            else:
                logger.error("❌ One-time run failed")
                return False
        except Exception as e:
            logger.error(f"❌ Error in one-time run: {e}")
            if self.notification_manager:
                self.notification_manager.send_error_notification(
                    "one_time_run", str(e)
                )
            return False
        
        return True
    
    def check_changes(self):
        """Check for changes and update if needed."""
        logger.info("🔍 Checking for changes...")
        
        try:
            changes = self.change_detector.check_for_changes()
            if changes:
                logger.info(f"🔄 {len(changes)} changes detected")
                success = self.change_detector.trigger_pipeline_update(changes)
                
                if self.notification_manager and success:
                    # Get update results
                    from src.data_collection.orchestrator import DataCollectionOrchestrator
                    orchestrator = DataCollectionOrchestrator()
                    results = {}
                    for source in ['clinical_trials', 'drugs', 'fda', 'company_websites']:
                        try:
                            result = orchestrator.run_full_collection([source])
                            results[source] = result.get(source, 0)
                        except:
                            results[source] = 0
                    
                    self.notification_manager.send_change_notification(changes, results)
                
                return success
            else:
                logger.info("✅ No changes detected")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error checking changes: {e}")
            if self.notification_manager:
                self.notification_manager.send_error_notification(
                    "change_check", str(e)
                )
            return False


def main():
    """Main entry point for production runner."""
    parser = argparse.ArgumentParser(description="Biopartnering Insights Pipeline Production Runner")
    parser.add_argument("--mode", choices=["daemon", "once", "check"], default="daemon",
                       help="Run mode: daemon (continuous), once (single run), check (check changes)")
    parser.add_argument("--run-type", choices=["full", "light", "monitor"], default="full",
                       help="Type of run for 'once' mode")
    parser.add_argument("--no-monitoring", action="store_true",
                       help="Disable website change monitoring")
    parser.add_argument("--no-weekly", action="store_true",
                       help="Disable weekly scheduled runs")
    parser.add_argument("--no-notifications", action="store_true",
                       help="Disable email notifications")
    
    args = parser.parse_args()
    
    # Create production runner
    runner = ProductionRunner(
        enable_monitoring=not args.no_monitoring,
        enable_weekly_runs=not args.no_weekly,
        enable_notifications=not args.no_notifications
    )
    
    try:
        if args.mode == "daemon":
            runner.start()
        elif args.mode == "once":
            success = runner.run_once(args.run_type)
            sys.exit(0 if success else 1)
        elif args.mode == "check":
            success = runner.check_changes()
            sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        runner.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        runner.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
