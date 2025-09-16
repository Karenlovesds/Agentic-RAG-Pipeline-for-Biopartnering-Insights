#!/usr/bin/env python3
"""
Scheduled Biopartnering Insights Pipeline

This script runs the complete pipeline on a schedule with intelligent change detection.
Perfect for production environments with cron jobs or systemd timers.
"""

import asyncio
import sys
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append('.')

from run_complete_pipeline import CompletePipeline


class ScheduledPipelineRunner:
    """Runs the pipeline on a schedule with intelligent change detection."""
    
    def __init__(self, interval_hours: int = 6, max_runtime_hours: int = 2):
        self.interval_hours = interval_hours
        self.max_runtime_hours = max_runtime_hours
        self.pipeline = CompletePipeline()
        self.running = True
        self.current_task = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
        if self.current_task and not self.current_task.done():
            logger.info("Cancelling current pipeline run...")
            self.current_task.cancel()
    
    async def run_pipeline_once(self, force_refresh: bool = False) -> bool:
        """Run the pipeline once and return success status."""
        try:
            logger.info("🚀 Starting scheduled pipeline run")
            start_time = datetime.now()
            
            # Run pipeline with timeout
            self.current_task = asyncio.create_task(
                self.pipeline.run_complete_pipeline(force_refresh=force_refresh)
            )
            
            try:
                results = await asyncio.wait_for(
                    self.current_task, 
                    timeout=self.max_runtime_hours * 3600  # Convert to seconds
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ Pipeline completed successfully in {duration:.2f} seconds")
                
                # Log summary
                summary = results.get('summary', {})
                logger.info(f"📊 Database stats: {summary.get('companies', 0)} companies, "
                          f"{summary.get('drugs', 0)} drugs, {summary.get('documents', 0)} documents")
                
                return True
                
            except asyncio.TimeoutError:
                logger.error(f"❌ Pipeline timed out after {self.max_runtime_hours} hours")
                return False
            except asyncio.CancelledError:
                logger.warning("⚠️  Pipeline run was cancelled")
                return False
                
        except Exception as e:
            logger.error(f"💥 Pipeline run failed: {e}")
            return False
        finally:
            self.current_task = None
    
    async def run_scheduled(self):
        """Run the pipeline on schedule."""
        logger.info(f"🕐 Starting scheduled pipeline runner (interval: {self.interval_hours}h)")
        
        while self.running:
            try:
                # Check if we should run (every interval_hours)
                last_run = self.pipeline.state_manager.state.get("last_run")
                should_run = True
                
                if last_run:
                    last_run_time = datetime.fromisoformat(last_run)
                    time_since_last = datetime.now() - last_run_time
                    should_run = time_since_last >= timedelta(hours=self.interval_hours)
                
                if should_run:
                    logger.info("⏰ Time for scheduled pipeline run")
                    success = await self.run_pipeline_once()
                    
                    if success:
                        logger.info("✅ Scheduled run completed successfully")
                    else:
                        logger.error("❌ Scheduled run failed")
                else:
                    logger.info("⏭️  Skipping scheduled run - not time yet")
                
                # Wait for next check (check every hour)
                logger.info(f"😴 Sleeping for 1 hour (next check in {self.interval_hours}h)")
                await asyncio.sleep(3600)  # Sleep for 1 hour
                
            except Exception as e:
                logger.error(f"💥 Error in scheduled runner: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def run_once(self, force_refresh: bool = False):
        """Run the pipeline once and exit."""
        logger.info("🔄 Running pipeline once")
        return asyncio.run(self.run_pipeline_once(force_refresh=force_refresh))


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scheduled Biopartnering Insights Pipeline")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--force", action="store_true", help="Force refresh all steps")
    parser.add_argument("--interval", type=int, default=6, help="Interval in hours (default: 6)")
    parser.add_argument("--max-runtime", type=int, default=2, help="Max runtime in hours (default: 2)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO")
    
    # Create runner
    runner = ScheduledPipelineRunner(
        interval_hours=args.interval,
        max_runtime_hours=args.max_runtime
    )
    
    try:
        if args.once:
            # Run once and exit
            success = runner.run_once(force_refresh=args.force)
            sys.exit(0 if success else 1)
        else:
            # Run on schedule
            asyncio.run(runner.run_scheduled())
            
    except KeyboardInterrupt:
        logger.info("👋 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
