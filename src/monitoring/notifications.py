"""Notification system for pipeline updates and changes."""

import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from pathlib import Path
from loguru import logger
from ..config import settings


class NotificationManager:
    """Manages notifications for pipeline updates and changes."""
    
    def __init__(self, email_config: Optional[Dict] = None):
        self.email_config = email_config or self._load_email_config()
        self.notification_log = Path("logs/notifications.jsonl")
        self.notification_log.parent.mkdir(exist_ok=True)
    
    def _load_email_config(self) -> Dict:
        """Load email configuration from environment or file."""
        return {
            'smtp_server': getattr(settings, 'smtp_server', 'smtp.gmail.com'),
            'smtp_port': getattr(settings, 'smtp_port', 587),
            'sender_email': getattr(settings, 'sender_email', ''),
            'sender_password': getattr(settings, 'sender_password', ''),
            'recipients': getattr(settings, 'notification_recipients', []),
            'enabled': getattr(settings, 'notifications_enabled', False)
        }
    
    def send_change_notification(self, changes: List[Dict], update_results: Dict):
        """Send notification about detected changes and updates."""
        if not self.email_config.get('enabled', False):
            logger.info("Email notifications disabled, skipping notification")
            return
        
        try:
            subject = f"🔄 Biopartnering Pipeline Update - {len(changes)} Changes Detected"
            
            # Create HTML email content
            html_content = self._create_change_notification_html(changes, update_results)
            text_content = self._create_change_notification_text(changes, update_results)
            
            # Send email
            self._send_email(subject, html_content, text_content)
            
            # Log notification
            self._log_notification("change_detected", changes, update_results)
            
        except Exception as e:
            logger.error(f"Error sending change notification: {e}")
    
    def send_scheduled_run_notification(self, run_type: str, total_documents: int, success: bool = True):
        """Send notification about scheduled runs."""
        if not self.email_config.get('enabled', False):
            return
        
        try:
            status_emoji = "✅" if success else "❌"
            subject = f"{status_emoji} Biopartnering Pipeline - {run_type.replace('_', ' ').title()} Run"
            
            html_content = self._create_scheduled_run_html(run_type, total_documents, success)
            text_content = self._create_scheduled_run_text(run_type, total_documents, success)
            
            self._send_email(subject, html_content, text_content)
            self._log_notification("scheduled_run", {"run_type": run_type, "total_documents": total_documents, "success": success})
            
        except Exception as e:
            logger.error(f"Error sending scheduled run notification: {e}")
    
    def send_error_notification(self, error_type: str, error_message: str, context: Dict = None):
        """Send notification about errors."""
        if not self.email_config.get('enabled', False):
            return
        
        try:
            subject = f"🚨 Biopartnering Pipeline Error - {error_type}"
            
            html_content = self._create_error_notification_html(error_type, error_message, context)
            text_content = self._create_error_notification_text(error_type, error_message, context)
            
            self._send_email(subject, html_content, text_content)
            self._log_notification("error", {"error_type": error_type, "error_message": error_message, "context": context})
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
    
    def _create_change_notification_html(self, changes: List[Dict], update_results: Dict) -> str:
        """Create HTML content for change notifications."""
        changes_html = ""
        for change in changes:
            changes_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{change['site_name']}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{change['url']}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{change['change_detected_at']}</td>
            </tr>
            """
        
        results_html = ""
        for source, count in update_results.items():
            results_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">{source.replace('_', ' ').title()}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{count}</td>
            </tr>
            """
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #2E8B57;">🔄 Biopartnering Pipeline Update</h2>
            <p>Changes were detected in monitored websites and the pipeline has been updated.</p>
            
            <h3>📊 Changes Detected ({len(changes)})</h3>
            <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Site</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">URL</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Detected At</th>
                </tr>
                {changes_html}
            </table>
            
            <h3>📈 Update Results</h3>
            <table style="border-collapse: collapse; width: 100%; margin-bottom: 20px;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; border: 1px solid #ddd;">Source</th>
                    <th style="padding: 8px; border: 1px solid #ddd;">Documents Collected</th>
                </tr>
                {results_html}
            </table>
            
            <p><strong>Total Documents:</strong> {sum(update_results.values())}</p>
            <p><em>This is an automated notification from the Biopartnering Insights Pipeline.</em></p>
        </body>
        </html>
        """
    
    def _create_change_notification_text(self, changes: List[Dict], update_results: Dict) -> str:
        """Create text content for change notifications."""
        changes_text = "\n".join([f"- {change['site_name']}: {change['url']}" for change in changes])
        results_text = "\n".join([f"- {source}: {count} documents" for source, count in update_results.items()])
        
        return f"""
Biopartnering Pipeline Update

Changes were detected in monitored websites and the pipeline has been updated.

Changes Detected ({len(changes)}):
{changes_text}

Update Results:
{results_text}

Total Documents: {sum(update_results.values())}

This is an automated notification from the Biopartnering Insights Pipeline.
        """
    
    def _create_scheduled_run_html(self, run_type: str, total_documents: int, success: bool) -> str:
        """Create HTML content for scheduled run notifications."""
        status = "Completed Successfully" if success else "Failed"
        emoji = "✅" if success else "❌"
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: {'#2E8B57' if success else '#DC143C'};">
                {emoji} Biopartnering Pipeline - {run_type.replace('_', ' ').title()} Run
            </h2>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>Run Type:</strong> {run_type.replace('_', ' ').title()}</p>
            <p><strong>Total Documents:</strong> {total_documents}</p>
            <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><em>This is an automated notification from the Biopartnering Insights Pipeline.</em></p>
        </body>
        </html>
        """
    
    def _create_scheduled_run_text(self, run_type: str, total_documents: int, success: bool) -> str:
        """Create text content for scheduled run notifications."""
        status = "Completed Successfully" if success else "Failed"
        emoji = "✅" if success else "❌"
        
        return f"""
{emoji} Biopartnering Pipeline - {run_type.replace('_', ' ').title()} Run

Status: {status}
Run Type: {run_type.replace('_', ' ').title()}
Total Documents: {total_documents}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated notification from the Biopartnering Insights Pipeline.
        """
    
    def _create_error_notification_html(self, error_type: str, error_message: str, context: Dict) -> str:
        """Create HTML content for error notifications."""
        context_html = ""
        if context:
            for key, value in context.items():
                context_html += f"<li><strong>{key}:</strong> {value}</li>"
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #DC143C;">🚨 Biopartnering Pipeline Error</h2>
            <p><strong>Error Type:</strong> {error_type}</p>
            <p><strong>Error Message:</strong> {error_message}</p>
            <p><strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            {f'<h3>Context:</h3><ul>{context_html}</ul>' if context_html else ''}
            <p><em>This is an automated error notification from the Biopartnering Insights Pipeline.</em></p>
        </body>
        </html>
        """
    
    def _create_error_notification_text(self, error_type: str, error_message: str, context: Dict) -> str:
        """Create text content for error notifications."""
        context_text = ""
        if context:
            context_text = "\nContext:\n" + "\n".join([f"- {key}: {value}" for key, value in context.items()])
        
        return f"""
🚨 Biopartnering Pipeline Error

Error Type: {error_type}
Error Message: {error_message}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{context_text}

This is an automated error notification from the Biopartnering Insights Pipeline.
        """
    
    def _send_email(self, subject: str, html_content: str, text_content: str):
        """Send email notification."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipients'])
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['sender_email'], self.email_config['sender_password'])
                server.send_message(msg)
            
            logger.info(f"📧 Notification sent: {subject}")
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise
    
    def _log_notification(self, notification_type: str, data: Dict):
        """Log notification details."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': notification_type,
            'data': data
        }
        
        # Log to file
        log_file = Path(self.notification_log)
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')


def create_notification_manager(email_config: Optional[Dict] = None) -> NotificationManager:
    """Create a notification manager with optional email configuration."""
    return NotificationManager(email_config)
