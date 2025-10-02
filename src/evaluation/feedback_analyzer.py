"""
Enhanced Feedback Analysis Module

This module combines the database persistence with advanced analysis capabilities
from the existing feedback_analysis.py module.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from src.evaluation.feedback_manager import FeedbackManager


def get_detailed_feedback_options() -> Dict[str, str]:
    """Get the detailed feedback options available for user selection."""
    return {
        "incorrect_info": "❌ Contains incorrect information",
        "missing_info": "❓ Missing important information", 
        "irrelevant": "🎯 Not relevant to my question",
        "outdated": "📅 Information appears outdated",
        "hard_to_understand": "🤔 Hard to understand"
    }


def analyze_feedback_patterns(detailed_feedback: Dict[int, List[str]]) -> Dict[str, Any]:
    """
    Analyze feedback patterns to identify improvement opportunities.
    
    Args:
        detailed_feedback: Dictionary mapping message indices to lists of feedback issues
        
    Returns:
        Dictionary containing analysis results with issue counts and percentages
    """
    if not detailed_feedback:
        return {
            "total_responses": 0,
            "issue_counts": {},
            "issue_percentages": {}
        }
    
    # Count issue types
    issue_counts = {}
    total_responses = len(detailed_feedback)
    
    for message_idx, issues in detailed_feedback.items():
        for issue in issues:
            if not issue.startswith("comment:"):
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
    
    # Calculate percentages
    issue_percentages = {}
    for issue, count in issue_counts.items():
        issue_percentages[issue] = (count / total_responses) * 100 if total_responses > 0 else 0
    
    logger.info(f"Analyzed feedback for {total_responses} responses, found {len(issue_counts)} unique issues")
    
    return {
        "total_responses": total_responses,
        "issue_counts": issue_counts,
        "issue_percentages": issue_percentages
    }


def get_improvement_recommendations(feedback_analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Generate improvement recommendations based on feedback analysis.
    
    Args:
        feedback_analysis: Results from analyze_feedback_patterns()
        
    Returns:
        List of recommendation dictionaries with issue, percentage, recommendation, and priority
    """
    recommendations = []
    
    if not feedback_analysis or feedback_analysis["total_responses"] == 0:
        return recommendations
    
    issue_percentages = feedback_analysis["issue_percentages"]
    
    # Generate specific recommendations based on common issues
    if issue_percentages.get("incorrect_info", 0) > 20:
        recommendations.append({
            "issue": "Incorrect Information",
            "percentage": issue_percentages["incorrect_info"],
            "recommendation": "🔍 Improve data validation and fact-checking. Consider adding source verification and cross-referencing with multiple databases.",
            "priority": "High"
        })
    
    if issue_percentages.get("outdated", 0) > 15:
        recommendations.append({
            "issue": "Outdated Information", 
            "percentage": issue_percentages["outdated"],
            "recommendation": "📅 Implement real-time data updates and add timestamps to information. Consider integrating live data feeds.",
            "priority": "High"
        })
    
    
    if issue_percentages.get("missing_info", 0) > 20:
        recommendations.append({
            "issue": "Missing Information",
            "percentage": issue_percentages["missing_info"],
            "recommendation": "❓ Enhance data collection to cover more comprehensive information sources and add follow-up questions.",
            "priority": "High"
        })
    
    if issue_percentages.get("hard_to_understand", 0) > 20:
        recommendations.append({
            "issue": "Hard to Understand",
            "percentage": issue_percentages["hard_to_understand"],
            "recommendation": "🤔 Simplify language and improve explanation clarity. Add definitions and examples for technical terms.",
            "priority": "High"
        })
    
    if issue_percentages.get("irrelevant", 0) > 15:
        recommendations.append({
            "issue": "Not Relevant",
            "percentage": issue_percentages["irrelevant"],
            "recommendation": "🎯 Improve query understanding and response relevance. Enhance context matching and filtering.",
            "priority": "High"
        })
    
    
    logger.info(f"Generated {len(recommendations)} improvement recommendations")
    return recommendations


def generate_feedback_summary(feedback_data: Dict[int, int], detailed_feedback: Dict[int, List[str]]) -> Dict[str, Any]:
    """
    Generate a comprehensive feedback summary.
    
    Args:
        feedback_data: Dictionary mapping message indices to ratings (1-5)
        detailed_feedback: Dictionary mapping message indices to detailed issues
        
    Returns:
        Dictionary containing comprehensive feedback summary
    """
    if not feedback_data:
        return {
            "total_responses": 0,
            "average_rating": 0,
            "rating_distribution": {},
            "quality_score": "No Data"
        }
    
    ratings = list(feedback_data.values())
    total_responses = len(ratings)
    average_rating = sum(ratings) / total_responses if total_responses > 0 else 0
    
    # Count ratings by category
    rating_distribution = {
        "excellent": sum(1 for r in ratings if r == 5),
        "very_good": sum(1 for r in ratings if r == 4),
        "good": sum(1 for r in ratings if r == 3),
        "fair": sum(1 for r in ratings if r == 2),
        "poor": sum(1 for r in ratings if r == 1)
    }
    
    # Calculate quality score
    if average_rating >= 4.5:
        quality_score = "Excellent"
    elif average_rating >= 3.5:
        quality_score = "Good"
    elif average_rating >= 2.5:
        quality_score = "Fair"
    else:
        quality_score = "Needs Improvement"
    
    return {
        "total_responses": total_responses,
        "average_rating": round(average_rating, 2),
        "rating_distribution": rating_distribution,
        "quality_score": quality_score
    }


def get_feedback_insights(feedback_analysis: Dict[str, Any], 
                         recommendations: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Generate high-level insights from feedback analysis.
    
    Args:
        feedback_analysis: Results from analyze_feedback_patterns()
        recommendations: List of improvement recommendations
        
    Returns:
        Dictionary containing key insights
    """
    insights = {
        "top_issues": [],
        "improvement_priorities": [],
        "system_health": "Unknown"
    }
    
    if not feedback_analysis or feedback_analysis["total_responses"] == 0:
        return insights
    
    # Get top 3 issues
    issue_percentages = feedback_analysis["issue_percentages"]
    top_issues = sorted(issue_percentages.items(), key=lambda x: x[1], reverse=True)[:3]
    insights["top_issues"] = [{"issue": issue, "percentage": percentage} for issue, percentage in top_issues]
    
    # Get high priority recommendations
    high_priority_recs = [rec for rec in recommendations if rec.get("priority") == "High"]
    insights["improvement_priorities"] = high_priority_recs
    
    # Determine system health
    total_responses = feedback_analysis["total_responses"]
    high_issue_percentage = sum(1 for p in issue_percentages.values() if p > 30)
    
    if high_issue_percentage == 0:
        insights["system_health"] = "Excellent"
    elif high_issue_percentage <= 2:
        insights["system_health"] = "Good"
    elif high_issue_percentage <= 4:
        insights["system_health"] = "Fair"
    else:
        insights["system_health"] = "Needs Attention"
    
    return insights


def export_feedback_data(feedback_data: Dict[int, int], 
                        detailed_feedback: Dict[int, List[str]], 
                        messages: List[Dict[str, Any]]) -> str:
    """
    Export comprehensive feedback data as JSON.
    
    Args:
        feedback_data: Dictionary mapping message indices to ratings
        detailed_feedback: Dictionary mapping message indices to detailed issues
        messages: List of chat messages
        
    Returns:
        JSON string containing all feedback data
    """
    enhanced_feedback_data = []
    
    for i, msg in enumerate(messages):
        if msg["role"] == "assistant" and i in feedback_data:
            rating = feedback_data[i]
            rating_text = {1: "Poor", 2: "Fair", 3: "Good", 4: "Very Good", 5: "Excellent"}[rating]
            
            # Include detailed feedback
            detailed_issues = detailed_feedback.get(i, [])
            comments = [issue for issue in detailed_issues if issue.startswith("comment:")]
            issues = [issue for issue in detailed_issues if not issue.startswith("comment:")]
            
            enhanced_feedback_data.append({
                "message_index": i,
                "question": messages[i-1]["content"] if i > 0 else "N/A",
                "response": msg["content"] if isinstance(msg["content"], str) else msg["content"].get("answer", ""),
                "rating": rating,
                "rating_text": rating_text,
                "detailed_issues": issues,
                "comments": [comment.replace("comment: ", "") for comment in comments],
                "timestamp": datetime.now().isoformat()
            })
    
    return json.dumps(enhanced_feedback_data, indent=2)


class EnhancedFeedbackAnalyzer:
    """Enhanced feedback analyzer that combines database persistence with advanced analysis."""
    
    def __init__(self):
        self.feedback_manager = FeedbackManager()
    
    def get_comprehensive_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive feedback analysis combining database data with advanced analytics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Comprehensive analysis including patterns, recommendations, and insights
        """
        try:
            # Get database feedback data
            db_feedback = self.feedback_manager.get_feedback_for_analysis(days)
            
            if not db_feedback:
                return {
                    "status": "no_data",
                    "message": f"No feedback data found for the last {days} days",
                    "recommendations": []
                }
            
            # Convert database format to analysis format
            detailed_feedback = {}
            feedback_data = {}
            
            for record in db_feedback:
                msg_idx = record["message_index"]
                detailed_feedback[msg_idx] = record["detailed_issues"]
                feedback_data[msg_idx] = record["rating"]
            
            # Perform advanced analysis
            analysis = analyze_feedback_patterns(detailed_feedback)
            recommendations = get_improvement_recommendations(analysis)
            summary = generate_feedback_summary(feedback_data, detailed_feedback)
            insights = get_feedback_insights(analysis, recommendations)
            
            # Add database-specific metrics
            db_summary = self.feedback_manager.get_feedback_summary(days)
            
            return {
                "status": "success",
                "database_metrics": db_summary,
                "advanced_analysis": analysis,
                "recommendations": recommendations,
                "summary": summary,
                "insights": insights,
                "data_period": f"Last {days} days",
                "total_records": len(db_feedback)
            }
            
        except Exception as e:
            logger.error(f"Error in comprehensive analysis: {e}")
            return {
                "status": "error",
                "message": str(e),
                "recommendations": []
            }
    
    def get_trend_analysis(self, days: int = 30) -> Dict[str, Any]:
        """
        Analyze feedback trends over time.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Trend analysis with time-based patterns
        """
        try:
            db_feedback = self.feedback_manager.get_feedback_for_analysis(days)
            
            if not db_feedback:
                return {"status": "no_data", "trends": []}
            
            # Convert to DataFrame for time analysis
            df = pd.DataFrame(db_feedback)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            # Daily trends
            daily_trends = df.groupby('date').agg({
                'rating': ['mean', 'count'],
                'id': 'count'
            }).round(2)
            
            # Weekly trends
            df['week'] = df['timestamp'].dt.isocalendar().week
            weekly_trends = df.groupby('week').agg({
                'rating': ['mean', 'count'],
                'id': 'count'
            }).round(2)
            
            # Issue trends over time
            issue_trends = {}
            for _, row in df.iterrows():
                date = row['date']
                issues = row['detailed_issues'] or []
                for issue in issues:
                    if issue not in issue_trends:
                        issue_trends[issue] = {}
                    issue_trends[issue][date] = issue_trends[issue].get(date, 0) + 1
            
            return {
                "status": "success",
                "daily_trends": daily_trends.to_dict(),
                "weekly_trends": weekly_trends.to_dict(),
                "issue_trends": issue_trends,
                "analysis_period": f"Last {days} days"
            }
            
        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_actionable_insights(self, days: int = 30) -> Dict[str, Any]:
        """
        Get actionable insights for RAG system improvement.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Actionable insights with specific recommendations
        """
        try:
            comprehensive_analysis = self.get_comprehensive_analysis(days)
            
            if comprehensive_analysis["status"] != "success":
                return comprehensive_analysis
            
            analysis = comprehensive_analysis["advanced_analysis"]
            recommendations = comprehensive_analysis["recommendations"]
            insights = comprehensive_analysis["insights"]
            
            # Prioritize recommendations by impact
            high_impact_recs = [r for r in recommendations if r.get("priority") == "High"]
            medium_impact_recs = [r for r in recommendations if r.get("priority") == "Medium"]
            
            # Generate specific action items
            action_items = []
            
            for rec in high_impact_recs:
                action_items.append({
                    "action": rec["recommendation"],
                    "issue": rec["issue"],
                    "impact": rec["percentage"],
                    "priority": "High",
                    "timeline": "Immediate (1-2 weeks)"
                })
            
            for rec in medium_impact_recs:
                action_items.append({
                    "action": rec["recommendation"],
                    "issue": rec["issue"],
                    "impact": rec["percentage"],
                    "priority": "Medium",
                    "timeline": "Short-term (1 month)"
                })
            
            return {
                "status": "success",
                "system_health": insights.get("system_health", "Unknown"),
                "top_issues": insights.get("top_issues", []),
                "action_items": action_items,
                "quick_wins": [item for item in action_items if item["priority"] == "High"][:3],
                "data_quality": {
                    "total_responses": analysis.get("total_responses", 0),
                    "response_rate": "Good" if analysis.get("total_responses", 0) > 50 else "Needs more data"
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating actionable insights: {e}")
            return {"status": "error", "message": str(e)}
    
    def export_enhanced_analysis(self, days: int = 30) -> str:
        """
        Export comprehensive analysis as JSON.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            JSON string with comprehensive analysis
        """
        try:
            comprehensive = self.get_comprehensive_analysis(days)
            trends = self.get_trend_analysis(days)
            insights = self.get_actionable_insights(days)
            
            export_data = {
                "analysis_timestamp": datetime.now().isoformat(),
                "analysis_period_days": days,
                "comprehensive_analysis": comprehensive,
                "trend_analysis": trends,
                "actionable_insights": insights,
                "export_version": "2.0"
            }
            
            return json.dumps(export_data, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error exporting enhanced analysis: {e}")
            return json.dumps({"error": str(e)}, indent=2)
    
    def close(self):
        """Close database connection."""
        self.feedback_manager.close()


# Convenience functions for easy integration
def get_enhanced_feedback_analysis(days: int = 30) -> Dict[str, Any]:
    """Get enhanced feedback analysis."""
    analyzer = EnhancedFeedbackAnalyzer()
    try:
        return analyzer.get_comprehensive_analysis(days)
    finally:
        analyzer.close()


def get_feedback_trends(days: int = 30) -> Dict[str, Any]:
    """Get feedback trends over time."""
    analyzer = EnhancedFeedbackAnalyzer()
    try:
        return analyzer.get_trend_analysis(days)
    finally:
        analyzer.close()


def get_rag_improvement_plan(days: int = 30) -> Dict[str, Any]:
    """Get actionable RAG improvement plan."""
    analyzer = EnhancedFeedbackAnalyzer()
    try:
        return analyzer.get_actionable_insights(days)
    finally:
        analyzer.close()


if __name__ == "__main__":
    # Demo the enhanced analysis
    analyzer = EnhancedFeedbackAnalyzer()
    
    print("🧪 Testing Enhanced Feedback Analysis")
    print("=" * 50)
    
    # Test comprehensive analysis
    print("\n1. Comprehensive Analysis:")
    analysis = analyzer.get_comprehensive_analysis(30)
    print(f"Status: {analysis.get('status')}")
    if analysis.get('status') == 'success':
        print(f"Total records: {analysis.get('total_records', 0)}")
        print(f"Recommendations: {len(analysis.get('recommendations', []))}")
    
    # Test trend analysis
    print("\n2. Trend Analysis:")
    trends = analyzer.get_trend_analysis(30)
    print(f"Status: {trends.get('status')}")
    
    # Test actionable insights
    print("\n3. Actionable Insights:")
    insights = analyzer.get_actionable_insights(30)
    print(f"Status: {insights.get('status')}")
    if insights.get('status') == 'success':
        print(f"System Health: {insights.get('system_health')}")
        print(f"Action Items: {len(insights.get('action_items', []))}")
    
    analyzer.close()
    print("\n✅ Enhanced analysis test completed!")
