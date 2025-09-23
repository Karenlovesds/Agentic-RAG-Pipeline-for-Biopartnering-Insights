"""
Feedback Analysis Module for RAG System Improvement

This module provides comprehensive feedback analysis capabilities to help improve
the RAG system based on user feedback patterns and specific issue identification.
"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger


def get_detailed_feedback_options() -> Dict[str, str]:
    """Get the detailed feedback options available for user selection."""
    return {
        "incorrect_info": "❌ Contains incorrect information",
        "too_detailed": "📚 Too detailed/complex",
        "too_brief": "📝 Too brief/simple", 
        "unreliable": "⚠️ Information seems unreliable",
        "outdated": "📅 Information appears outdated",
        "irrelevant": "🎯 Not relevant to my question",
        "missing_info": "❓ Missing important information",
        "poor_format": "📄 Poor formatting/structure",
        "hard_to_understand": "🤔 Hard to understand",
        "too_technical": "🔬 Too technical",
        "not_actionable": "🚫 Not actionable/practical"
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
    
    if issue_percentages.get("too_detailed", 0) > 25:
        recommendations.append({
            "issue": "Too Detailed/Complex",
            "percentage": issue_percentages["too_detailed"],
            "recommendation": "📚 Add response length controls and provide both summary and detailed versions. Implement progressive disclosure.",
            "priority": "Medium"
        })
    
    if issue_percentages.get("too_brief", 0) > 25:
        recommendations.append({
            "issue": "Too Brief/Simple",
            "percentage": issue_percentages["too_brief"],
            "recommendation": "📝 Expand response depth and add more context. Provide additional details and examples.",
            "priority": "Medium"
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
    
    if issue_percentages.get("too_technical", 0) > 20:
        recommendations.append({
            "issue": "Too Technical",
            "percentage": issue_percentages["too_technical"],
            "recommendation": "🔬 Add technical term definitions and provide simpler explanations alongside technical details.",
            "priority": "Medium"
        })
    
    if issue_percentages.get("unreliable", 0) > 15:
        recommendations.append({
            "issue": "Unreliable Information",
            "percentage": issue_percentages["unreliable"],
            "recommendation": "⚠️ Improve source credibility assessment and add confidence indicators to responses.",
            "priority": "High"
        })
    
    if issue_percentages.get("not_actionable", 0) > 20:
        recommendations.append({
            "issue": "Not Actionable",
            "percentage": issue_percentages["not_actionable"],
            "recommendation": "🚫 Add practical next steps, specific recommendations, and actionable insights to responses.",
            "priority": "Medium"
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


def create_feedback_dashboard_data(feedback_analysis: Dict[str, Any], 
                                 feedback_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create data for feedback dashboard visualization.
    
    Args:
        feedback_analysis: Results from analyze_feedback_patterns()
        feedback_summary: Results from generate_feedback_summary()
        
    Returns:
        Dictionary containing dashboard-ready data
    """
    dashboard_data = {
        "summary_metrics": {
            "total_responses": feedback_summary.get("total_responses", 0),
            "average_rating": feedback_summary.get("average_rating", 0),
            "quality_score": feedback_summary.get("quality_score", "No Data")
        },
        "rating_distribution": feedback_summary.get("rating_distribution", {}),
        "issue_breakdown": {
            "issues": list(feedback_analysis.get("issue_percentages", {}).keys()),
            "percentages": list(feedback_analysis.get("issue_percentages", {}).values()),
            "counts": list(feedback_analysis.get("issue_counts", {}).values())
        }
    }
    
    return dashboard_data


def validate_feedback_data(feedback_data: Dict[int, int], 
                          detailed_feedback: Dict[int, List[str]]) -> Dict[str, Any]:
    """
    Validate feedback data for consistency and completeness.
    
    Args:
        feedback_data: Dictionary mapping message indices to ratings
        detailed_feedback: Dictionary mapping message indices to detailed issues
        
    Returns:
        Dictionary containing validation results
    """
    validation_results = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    # Check for invalid ratings
    for msg_idx, rating in feedback_data.items():
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            validation_results["errors"].append(f"Invalid rating {rating} for message {msg_idx}")
            validation_results["is_valid"] = False
    
    # Check for missing detailed feedback
    for msg_idx in feedback_data.keys():
        if msg_idx not in detailed_feedback:
            validation_results["warnings"].append(f"Missing detailed feedback for message {msg_idx}")
    
    # Check for orphaned detailed feedback
    for msg_idx in detailed_feedback.keys():
        if msg_idx not in feedback_data:
            validation_results["warnings"].append(f"Detailed feedback without rating for message {msg_idx}")
    
    return validation_results


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






