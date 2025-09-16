"""RAG Cache Manager for storing and retrieving cached RAG results."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from src.models.entities import RAGCache, Document


class RAGCacheManager:
    """Manages RAG retrieval caching to improve performance."""
    
    def __init__(self, cache_ttl_hours: int = 24):
        """
        Initialize cache manager.
        
        Args:
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
        """
        self.cache_ttl_hours = cache_ttl_hours
        logger.info(f"RAGCacheManager initialized with TTL: {cache_ttl_hours} hours")
    
    def _generate_query_hash(self, query: str) -> str:
        """Generate SHA-256 hash for query."""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: RAGCache) -> bool:
        """Check if cache entry is still valid."""
        if cache_entry.expires_at is None:
            return True
        
        return datetime.utcnow() < cache_entry.expires_at
    
    def get_cached_result(self, db: Session, query: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached result for a query.
        
        Args:
            db: Database session
            query: Query string
            
        Returns:
            Cached result dict or None if not found/expired
        """
        query_hash = self._generate_query_hash(query)
        
        try:
            cache_entry = db.query(RAGCache).filter(
                RAGCache.query_hash == query_hash
            ).first()
            
            if not cache_entry:
                logger.debug(f"No cache entry found for query: {query[:50]}...")
                return None
            
            if not self._is_cache_valid(cache_entry):
                logger.debug(f"Cache entry expired for query: {query[:50]}...")
                # Delete expired entry
                db.delete(cache_entry)
                db.commit()
                return None
            
            # Update access statistics
            cache_entry.last_accessed = datetime.utcnow()
            cache_entry.access_count += 1
            db.commit()
            
            logger.info(f"Cache hit for query: {query[:50]}... (access count: {cache_entry.access_count})")
            
            return {
                "answer": cache_entry.answer,
                "citations": cache_entry.citations,
                "confidence_score": cache_entry.confidence_score,
                "cached": True,
                "cache_age_hours": (datetime.utcnow() - cache_entry.created_at).total_seconds() / 3600
            }
            
        except Exception as e:
            logger.error(f"Error retrieving cached result: {e}")
            return None
    
    def store_cached_result(
        self, 
        db: Session, 
        query: str, 
        retrieved_docs: List[Any], 
        answer: str, 
        citations: List[Dict[str, Any]], 
        confidence_score: Optional[float] = None
    ) -> bool:
        """
        Store RAG result in cache.
        
        Args:
            db: Database session
            query: Query string
            retrieved_docs: List of retrieved documents
            answer: Generated answer
            citations: List of citations
            confidence_score: Optional confidence score
            
        Returns:
            True if stored successfully, False otherwise
        """
        query_hash = self._generate_query_hash(query)
        expires_at = datetime.utcnow() + timedelta(hours=self.cache_ttl_hours)
        
        try:
            # Extract document IDs from retrieved docs
            doc_ids = []
            for doc in retrieved_docs:
                if hasattr(doc, 'id'):
                    doc_ids.append(doc.id)
                elif isinstance(doc, dict) and 'id' in doc:
                    doc_ids.append(doc['id'])
            
            # Check if entry already exists
            existing_entry = db.query(RAGCache).filter(
                RAGCache.query_hash == query_hash
            ).first()
            
            if existing_entry:
                # Update existing entry
                existing_entry.retrieved_doc_ids = doc_ids
                existing_entry.answer = answer
                existing_entry.citations = citations
                existing_entry.confidence_score = confidence_score
                existing_entry.expires_at = expires_at
                existing_entry.last_accessed = datetime.utcnow()
                existing_entry.access_count = 0  # Reset access count
                logger.info(f"Updated cache entry for query: {query[:50]}...")
            else:
                # Create new entry
                # Convert Citation objects to dictionaries for JSON serialization
                citations_dict = []
                if citations:
                    for citation in citations:
                        if hasattr(citation, 'dict'):
                            citations_dict.append(citation.dict())
                        elif hasattr(citation, '__dict__'):
                            citations_dict.append(citation.__dict__)
                        else:
                            citations_dict.append({
                                'label': getattr(citation, 'label', ''),
                                'title': getattr(citation, 'title', ''),
                                'url': getattr(citation, 'url', ''),
                                'source': getattr(citation, 'source', '')
                            })
                
                cache_entry = RAGCache(
                    query_hash=query_hash,
                    query_text=query,
                    retrieved_doc_ids=doc_ids,
                    answer=answer,
                    citations=citations_dict,
                    confidence_score=confidence_score,
                    expires_at=expires_at
                )
                db.add(cache_entry)
                logger.info(f"Created new cache entry for query: {query[:50]}...")
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error storing cached result: {e}")
            db.rollback()
            return False
    
    def invalidate_cache(self, db: Session, query: str = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            db: Database session
            query: Specific query to invalidate (if None, invalidate all)
            
        Returns:
            Number of entries invalidated
        """
        try:
            if query:
                query_hash = self._generate_query_hash(query)
                entries = db.query(RAGCache).filter(RAGCache.query_hash == query_hash).all()
            else:
                entries = db.query(RAGCache).all()
            
            count = len(entries)
            for entry in entries:
                db.delete(entry)
            
            db.commit()
            logger.info(f"Invalidated {count} cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            db.rollback()
            return 0
    
    def cleanup_expired_cache(self, db: Session) -> int:
        """
        Remove expired cache entries.
        
        Args:
            db: Database session
            
        Returns:
            Number of entries removed
        """
        try:
            now = datetime.utcnow()
            expired_entries = db.query(RAGCache).filter(
                RAGCache.expires_at < now
            ).all()
            
            count = len(expired_entries)
            for entry in expired_entries:
                db.delete(entry)
            
            db.commit()
            logger.info(f"Cleaned up {count} expired cache entries")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired cache: {e}")
            db.rollback()
            return 0
    
    def get_cache_stats(self, db: Session) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cache statistics
        """
        try:
            total_entries = db.query(RAGCache).count()
            valid_entries = db.query(RAGCache).filter(
                RAGCache.expires_at > datetime.utcnow()
            ).count()
            expired_entries = total_entries - valid_entries
            
            # Get most accessed queries
            most_accessed = db.query(RAGCache).order_by(
                RAGCache.access_count.desc()
            ).limit(5).all()
            
            return {
                "total_entries": total_entries,
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "most_accessed": [
                    {
                        "query": entry.query_text[:100] + "..." if len(entry.query_text) > 100 else entry.query_text,
                        "access_count": entry.access_count,
                        "last_accessed": entry.last_accessed.isoformat()
                    }
                    for entry in most_accessed
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
