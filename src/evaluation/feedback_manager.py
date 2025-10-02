"""
Feedback Manager for RAG System

This module handles automatic saving and retrieval of feedback data to/from the database.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from loguru import logger

from src.models.database import SessionLocal
from src.models.entities import FeedbackData


class FeedbackManager:
    """Manages feedback data storage and retrieval."""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def save_feedback(self, 
                     session_id: str,
                     message_index: int,
                     rating: int,
                     detailed_issues: List[str] = None,
                     comments: str = None,
                     question: str = None,
                     response: str = None,
                     user_agent: str = None) -> bool:
        """
        Save feedback data to the database.
        
        Args:
            session_id: Unique session identifier
            message_index: Index of the message in the conversation
            rating: Rating from 1-5
            detailed_issues: List of detailed issue types
            comments: Free-text comments
            question: The user's question
            response: The assistant's response
            user_agent: User's browser information
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            # Separate comments from detailed issues
            if detailed_issues:
                issue_list = [issue for issue in detailed_issues if not issue.startswith("comment:")]
                comment_list = [issue.replace("comment: ", "") for issue in detailed_issues if issue.startswith("comment:")]
                comments = comments or " ".join(comment_list) if comment_list else None
            else:
                issue_list = None
            
            feedback = FeedbackData(
                session_id=session_id,
                message_index=message_index,
                rating=rating,
                detailed_issues=issue_list,
                comments=comments,
                question=question,
                response=response,
                user_agent=user_agent,
                timestamp=datetime.utcnow()
            )
            
            self.db.add(feedback)
            self.db.commit()
            
            logger.info(f"Saved feedback for session {session_id}, message {message_index}, rating {rating}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            self.db.rollback()
            return False
    
    def get_feedback_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get feedback summary for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary containing feedback summary statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get basic statistics
            total_feedback = self.db.query(FeedbackData).filter(
                FeedbackData.timestamp >= cutoff_date
            ).count()
            
            if total_feedback == 0:
                return {
                    "total_feedback": 0,
                    "average_rating": 0,
                    "rating_distribution": {},
                    "top_issues": [],
                    "recent_feedback": []
                }
            
            # Average rating
            avg_rating = self.db.query(func.avg(FeedbackData.rating)).filter(
                FeedbackData.timestamp >= cutoff_date
            ).scalar() or 0
            
            # Rating distribution
            rating_dist = {}
            for rating in range(1, 6):
                count = self.db.query(FeedbackData).filter(
                    FeedbackData.timestamp >= cutoff_date,
                    FeedbackData.rating == rating
                ).count()
                rating_dist[rating] = count
            
            # Top issues
            all_issues = []
            feedback_records = self.db.query(FeedbackData).filter(
                FeedbackData.timestamp >= cutoff_date,
                FeedbackData.detailed_issues.isnot(None)
            ).all()
            
            for record in feedback_records:
                if record.detailed_issues:
                    all_issues.extend(record.detailed_issues)
            
            issue_counts = {}
            for issue in all_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Recent feedback
            recent_feedback = self.db.query(FeedbackData).filter(
                FeedbackData.timestamp >= cutoff_date
            ).order_by(desc(FeedbackData.timestamp)).limit(10).all()
            
            recent_data = []
            for record in recent_feedback:
                recent_data.append({
                    "id": record.id,
                    "rating": record.rating,
                    "issues": record.detailed_issues or [],
                    "comments": record.comments,
                    "timestamp": record.timestamp.isoformat(),
                    "question": record.question[:100] + "..." if record.question and len(record.question) > 100 else record.question
                })
            
            return {
                "total_feedback": total_feedback,
                "average_rating": round(avg_rating, 2),
                "rating_distribution": rating_dist,
                "top_issues": top_issues,
                "recent_feedback": recent_data
            }
            
        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")
            return {"error": str(e)}
    
    def get_feedback_for_analysis(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get feedback data for analysis.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of feedback records
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            feedback_records = self.db.query(FeedbackData).filter(
                FeedbackData.timestamp >= cutoff_date
            ).order_by(desc(FeedbackData.timestamp)).all()
            
            feedback_data = []
            for record in feedback_records:
                feedback_data.append({
                    "id": record.id,
                    "session_id": record.session_id,
                    "message_index": record.message_index,
                    "rating": record.rating,
                    "detailed_issues": record.detailed_issues or [],
                    "comments": record.comments,
                    "question": record.question,
                    "response": record.response,
                    "timestamp": record.timestamp.isoformat(),
                    "user_agent": record.user_agent
                })
            
            return feedback_data
            
        except Exception as e:
            logger.error(f"Error getting feedback for analysis: {e}")
            return []
    
    def export_feedback_to_json(self, days: int = 30) -> str:
        """
        Export feedback data as JSON string.
        
        Args:
            days: Number of days to look back
            
        Returns:
            JSON string of feedback data
        """
        feedback_data = self.get_feedback_for_analysis(days)
        return json.dumps(feedback_data, indent=2, default=str)
    
    def close(self):
        """Close database connection."""
        self.db.close()


def create_feedback_tables():
    """Create feedback tables in the database."""
    try:
        from src.models.database import engine
        from src.models.entities import FeedbackData
        
        # Create the table
        FeedbackData.__table__.create(engine, checkfirst=True)
        logger.info("Feedback tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating feedback tables: {e}")
        return False


# Import timedelta for the summary function
from datetime import timedelta
