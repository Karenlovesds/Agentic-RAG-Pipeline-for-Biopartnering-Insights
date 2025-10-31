"""Website change detection system for monitoring data sources."""

import hashlib
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger
from sqlalchemy.orm import Session
from ..data_collection.orchestrator import DataCollectionOrchestrator


class WebsiteChangeDetector:
    """Detects changes in monitored websites and triggers pipeline updates."""
    
    def __init__(self, check_interval_hours: int = 24):
        self.check_interval_hours = check_interval_hours
        self.monitoring_file = Path("data/website_monitoring.json")
        self.monitoring_file.parent.mkdir(exist_ok=True)
        
        # Load existing monitoring data
        self.monitoring_data = self._load_monitoring_data()
        
        # Define websites to monitor
        self.monitored_sites = {
            "fda_drug_approvals": "https://api.fda.gov/drug/label.json",
            "clinical_trials": "https://clinicaltrials.gov/api/v2/studies"
        }
    
    def _load_monitoring_data(self) -> Dict:
        """Load existing monitoring data from file."""
        if self.monitoring_file.exists():
            try:
                with open(self.monitoring_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading monitoring data: {e}")
        return {}
    
    def _save_monitoring_data(self):
        """Save monitoring data to file."""
        try:
            with open(self.monitoring_file, 'w') as f:
                json.dump(self.monitoring_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving monitoring data: {e}")
    
    def _get_content_hash(self, url: str) -> Optional[str]:
        """Get content hash for a URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; BiopartneringInsights/1.0)'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Create hash of content
            content_hash = hashlib.md5(response.content).hexdigest()
            return content_hash
        except Exception as e:
            logger.error(f"Error getting content hash for {url}: {e}")
            return None
    
    def check_for_changes(self) -> List[Dict]:
        """Check all monitored sites for changes."""
        changes_detected = []
        current_time = datetime.now()
        
        logger.info("Starting website change detection...")
        
        for site_name, url in self.monitored_sites.items():
            try:
                # Get current content hash
                current_hash = self._get_content_hash(url)
                if not current_hash:
                    continue
                
                # Check if we have previous hash
                last_check = self.monitoring_data.get(site_name, {})
                previous_hash = last_check.get('content_hash')
                last_check_time = last_check.get('last_check')
                
                # Check if enough time has passed since last check
                if last_check_time:
                    last_check_dt = datetime.fromisoformat(last_check_time)
                    if current_time - last_check_dt < timedelta(hours=self.check_interval_hours):
                        continue
                
                # Update monitoring data
                self.monitoring_data[site_name] = {
                    'url': url,
                    'content_hash': current_hash,
                    'last_check': current_time.isoformat(),
                    'previous_hash': previous_hash
                }
                
                # Check for changes
                if previous_hash and previous_hash != current_hash:
                    change_info = {
                        'site_name': site_name,
                        'url': url,
                        'previous_hash': previous_hash,
                        'current_hash': current_hash,
                        'change_detected_at': current_time.isoformat(),
                        'change_type': 'content_modified'
                    }
                    changes_detected.append(change_info)
                    logger.info(f"🔄 Change detected in {site_name}: {url}")
                
                # If this is the first check, record it
                elif not previous_hash:
                    logger.info(f"📝 First check recorded for {site_name}: {url}")
                
            except Exception as e:
                logger.error(f"Error checking {site_name} ({url}): {e}")
        
        # Save updated monitoring data
        self._save_monitoring_data()
        
        logger.info(f"Change detection completed. {len(changes_detected)} changes detected.")
        return changes_detected
    
    def trigger_pipeline_update(self, changes: List[Dict]) -> bool:
        """Trigger pipeline update when changes are detected."""
        if not changes:
            return False
        
        try:
            logger.info(f"🔄 Triggering pipeline update due to {len(changes)} changes...")
            
            # Determine which data sources to update based on changes
            sources_to_update = set()
            for change in changes:
                site_name = change['site_name']
                if 'pipeline' in site_name or 'research' in site_name:
                    sources_to_update.add('company_websites')
                elif 'fda' in site_name:
                    sources_to_update.add('fda')
                elif 'clinical' in site_name:
                    sources_to_update.add('clinical_trials')
            
            # Add drugs source for comprehensive update
            sources_to_update.add('drugs')
            
            # Run data collection
            orchestrator = DataCollectionOrchestrator()
            results = {}
            
            for source in sources_to_update:
                try:
                    result = orchestrator.run_full_collection([source])
                    results[source] = result.get(source, 0)
                    logger.info(f"✅ Updated {source}: {results[source]} documents")
                except Exception as e:
                    logger.error(f"Error updating {source}: {e}")
            
            # Log the update
            self._log_pipeline_update(changes, results)
            
            return True
            
        except Exception as e:
            logger.error(f"Error triggering pipeline update: {e}")
            return False
    
    def _log_pipeline_update(self, changes: List[Dict], results: Dict):
        """Log pipeline update details."""
        update_log = {
            'timestamp': datetime.now().isoformat(),
            'triggered_by': 'website_changes',
            'changes_detected': changes,
            'sources_updated': results,
            'total_documents_collected': sum(results.values())
        }
        
        # Save to log file
        log_file = Path("logs/pipeline_updates.jsonl")
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'a') as f:
            f.write(json.dumps(update_log) + '\n')
        
        logger.info(f"📊 Pipeline update completed: {sum(results.values())} total documents collected")
    
    def get_monitoring_status(self) -> Dict:
        """Get current monitoring status."""
        status = {
            'total_sites_monitored': len(self.monitored_sites),
            'last_check_times': {},
            'sites_with_changes': [],
            'monitoring_active': True
        }
        
        for site_name, data in self.monitoring_data.items():
            if 'last_check' in data:
                status['last_check_times'][site_name] = data['last_check']
            
            if 'previous_hash' in data and 'content_hash' in data:
                if data['previous_hash'] != data['content_hash']:
                    status['sites_with_changes'].append(site_name)
        
        return status
    
    def force_check_all(self) -> List[Dict]:
        """Force check all sites regardless of timing."""
        original_interval = self.check_interval_hours
        self.check_interval_hours = 0  # Force immediate check
        changes = self.check_for_changes()
        self.check_interval_hours = original_interval
        return changes

