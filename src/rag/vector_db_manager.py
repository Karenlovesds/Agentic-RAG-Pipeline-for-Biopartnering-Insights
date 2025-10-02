"""
Vector Database Manager for Semantic Search

This module provides semantic search capabilities for the React RAG agent using ChromaDB.
It handles embedding generation, storage, and retrieval with relevance scoring.

🎯 FEATURES:
- Semantic search across all biopharmaceutical data
- Top-K retrieval with relevance scoring
- Handles query variations and typos
- Contextual understanding
- No hybrid complexity - pure vector search
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from loguru import logger
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from src.rag.ground_truth_loader import GroundTruthLoader
from src.models.database import SessionLocal
from src.models.entities import Drug, Company, ClinicalTrial, Target, Document


class VectorDBManager:
    """Manages vector database for semantic search in React RAG agent."""
    
    def __init__(self, persist_directory: str = "chroma_db"):
        """
        Initialize vector database manager.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.gt_loader = GroundTruthLoader()
        
        # Initialize embedding model
        self._init_embedding_model()
        
        # Initialize ChromaDB
        self._init_chromadb()
        
        logger.info("VectorDBManager initialized successfully")
    
    def _init_embedding_model(self):
        """Initialize embedding model for text vectorization."""
        try:
            # Use HuggingFace embedding model (no API key required)
            self.embedding_model = HuggingFaceEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                device="cpu"  # Use CPU for compatibility
            )
            logger.info("Embedding model initialized: sentence-transformers/all-MiniLM-L6-v2")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            raise
    
    def _init_chromadb(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name="biopharma_semantic_search",
                metadata={"description": "Biopharmaceutical data for semantic search"}
            )
            
            logger.info(f"ChromaDB collection initialized: {self.collection.name}")
            
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {e}")
            raise
    
    def _create_text_chunks(self) -> List[Dict[str, Any]]:
        """Create text chunks from ground truth and database data."""
        chunks = []
        
        # Load ground truth data
        if not self.gt_loader._data.empty:
            for _, row in self.gt_loader._data.iterrows():
                # Create comprehensive text chunk for each ground truth entry
                text_parts = []
                
                if pd.notna(row['Generic name']):
                    text_parts.append(f"Drug: {row['Generic name']}")
                if pd.notna(row['Brand name']):
                    text_parts.append(f"Brand: {row['Brand name']}")
                if pd.notna(row['Partner']):
                    text_parts.append(f"Company: {row['Partner']}")
                if pd.notna(row['Target']):
                    text_parts.append(f"Target: {row['Target']}")
                if pd.notna(row['Mechanism']):
                    text_parts.append(f"Mechanism: {row['Mechanism']}")
                if pd.notna(row['Drug Class']):
                    text_parts.append(f"Drug Class: {row['Drug Class']}")
                if pd.notna(row['Indication Approved']):
                    text_parts.append(f"Indication: {row['Indication Approved']}")
                if pd.notna(row['Current Clinical Trials']):
                    text_parts.append(f"Current Clinical Trials: {row['Current Clinical Trials']}")
                if pd.notna(row['Tickets']):
                    text_parts.append(f"Ticket: {row['Tickets']}")
                
                if text_parts:
                    chunk_text = " | ".join(text_parts)
                    chunks.append({
                        "text": chunk_text,
                        "metadata": {
                            "source": "ground_truth",
                            "generic_name": str(row['Generic name']) if pd.notna(row['Generic name']) else "",
                            "brand_name": str(row['Brand name']) if pd.notna(row['Brand name']) else "",
                            "company": str(row['Partner']) if pd.notna(row['Partner']) else "",
                            "target": str(row['Target']) if pd.notna(row['Target']) else "",
                            "mechanism": str(row['Mechanism']) if pd.notna(row['Mechanism']) else "",
                            "drug_class": str(row['Drug Class']) if pd.notna(row['Drug Class']) else "",
                            "indication": str(row['Indication Approved']) if pd.notna(row['Indication Approved']) else "",
                            "clinical_trials": str(row['Current Clinical Trials']) if pd.notna(row['Current Clinical Trials']) else "",
                            "ticket": str(row['Tickets']) if pd.notna(row['Tickets']) else ""
                        }
                    })
        
        # Load database data
        try:
            db = SessionLocal()
            
            # Add drugs from database
            drugs = db.query(Drug).join(Company).all()
            for drug in drugs:
                text_parts = []
                text_parts.append(f"Drug: {drug.generic_name}")
                if drug.brand_name:
                    text_parts.append(f"Brand: {drug.brand_name}")
                text_parts.append(f"Company: {drug.company.name}")
                if drug.mechanism_of_action:
                    text_parts.append(f"Mechanism: {drug.mechanism_of_action}")
                if drug.drug_class:
                    text_parts.append(f"Drug Class: {drug.drug_class}")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "database",
                        "generic_name": drug.generic_name or "",
                        "brand_name": drug.brand_name or "",
                        "company": drug.company.name,
                        "target": "",
                        "mechanism": drug.mechanism_of_action or "",
                        "drug_class": drug.drug_class or "",
                        "indication": "",
                        "ticket": ""
                    }
                })
            
            # Add clinical trials
            trials = db.query(ClinicalTrial).all()
            for trial in trials:
                text_parts = []
                text_parts.append(f"Clinical Trial: {trial.nct_id}")
                if trial.title:
                    text_parts.append(f"Title: {trial.title}")
                if trial.phase:
                    text_parts.append(f"Phase: {trial.phase}")
                if trial.status:
                    text_parts.append(f"Status: {trial.status}")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "clinical_trial",
                        "generic_name": "",
                        "brand_name": "",
                        "company": "",
                        "target": "",
                        "mechanism": "",
                        "drug_class": "",
                        "indication": "",
                        "ticket": "",
                        "nct_id": trial.nct_id or "",
                        "phase": trial.phase or "",
                        "status": trial.status or ""
                    }
                })
            
            # Add FDA approved drugs
            fda_drugs = db.query(Drug).filter(Drug.fda_approval_status == True).all()
            for drug in fda_drugs:
                text_parts = []
                text_parts.append(f"FDA Approved Drug: {drug.generic_name}")
                if drug.brand_name:
                    text_parts.append(f"Brand: {drug.brand_name}")
                if drug.company and drug.company.name:
                    text_parts.append(f"Company: {drug.company.name}")
                if drug.drug_class:
                    text_parts.append(f"Drug Class: {drug.drug_class}")
                if drug.mechanism_of_action:
                    text_parts.append(f"Mechanism: {drug.mechanism_of_action}")
                if drug.fda_approval_date:
                    text_parts.append(f"FDA Approval Date: {drug.fda_approval_date.strftime('%Y-%m-%d')}")
                
                # Add target information
                if drug.targets:
                    targets = [dt.target.name for dt in drug.targets]
                    text_parts.append(f"Targets: {', '.join(targets)}")
                
                # Add indication information
                if drug.indications:
                    indications = [di.indication.name for di in drug.indications]
                    text_parts.append(f"Indications: {', '.join(indications)}")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "fda",
                        "generic_name": drug.generic_name,
                        "brand_name": drug.brand_name or "",
                        "company": drug.company.name if drug.company else "",
                        "target": ', '.join([dt.target.name for dt in drug.targets]) if drug.targets else "",
                        "mechanism": drug.mechanism_of_action or "",
                        "drug_class": drug.drug_class or "",
                        "indication": ', '.join([di.indication.name for di in drug.indications]) if drug.indications else "",
                        "ticket": "",
                        "fda_approval_date": drug.fda_approval_date.strftime('%Y-%m-%d') if drug.fda_approval_date else ""
                    }
                })
            
            # Add FDA documents
            fda_docs = db.query(Document).filter(Document.source_type == 'fda_drug_approval').all()
            for doc in fda_docs:
                # Extract key information from FDA document content
                content_parts = doc.content.split('\n')[:10] if doc.content else []  # First 10 lines for key info
                text_parts = []
                text_parts.append(f"FDA Document: {doc.title}")
                text_parts.append(f"Source: {doc.source_url}")
                
                # Add relevant content snippets
                for part in content_parts:
                    if part.strip() and len(part.strip()) > 10:
                        text_parts.append(f"Content: {part.strip()[:200]}...")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "fda_document",
                        "generic_name": "",
                        "brand_name": "",
                        "company": "",
                        "target": "",
                        "mechanism": "",
                        "drug_class": "",
                        "indication": "",
                        "ticket": "",
                        "title": doc.title or "",
                        "url": doc.source_url,
                        "retrieval_date": doc.retrieval_date.strftime('%Y-%m-%d') if doc.retrieval_date else ""
                    }
                })
            
            # Add Drugs.com documents
            drugs_com_docs = db.query(Document).filter(Document.source_type == 'drugs_com_profile').all()
            for doc in drugs_com_docs:
                # Extract key information from Drugs.com document content
                content_parts = doc.content.split('\n')[:15] if doc.content else []  # First 15 lines for comprehensive info
                text_parts = []
                text_parts.append(f"Drugs.com Profile: {doc.title}")
                text_parts.append(f"Source: {doc.source_url}")
                
                # Add relevant content snippets (drug descriptions, mechanisms, etc.)
                for part in content_parts:
                    if part.strip() and len(part.strip()) > 10:
                        # Look for specific drug information patterns
                        if any(keyword in part.lower() for keyword in ['mechanism', 'indication', 'dosage', 'side effect', 'interaction', 'contraindication']):
                            text_parts.append(f"Drug Info: {part.strip()[:300]}...")
                        elif len(part.strip()) > 20:  # General content
                            text_parts.append(f"Content: {part.strip()[:200]}...")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "drugs_com",
                        "generic_name": "",
                        "brand_name": "",
                        "company": "",
                        "target": "",
                        "mechanism": "",
                        "drug_class": "",
                        "indication": "",
                        "ticket": "",
                        "title": doc.title or "",
                        "url": doc.source_url,
                        "retrieval_date": doc.retrieval_date.strftime('%Y-%m-%d') if doc.retrieval_date else ""
                    }
                })
            
            # Add drug interaction documents
            interaction_docs = db.query(Document).filter(Document.source_type == 'drug_interaction').all()
            for doc in interaction_docs:
                # Extract drug interaction information
                content_parts = doc.content.split('\n')[:10] if doc.content else []
                text_parts = []
                text_parts.append(f"Drug Interaction: {doc.title}")
                text_parts.append(f"Source: {doc.source_url}")
                
                # Add interaction details
                for part in content_parts:
                    if part.strip() and len(part.strip()) > 10:
                        if any(keyword in part.lower() for keyword in ['interaction', 'contraindication', 'warning', 'severe', 'moderate', 'minor']):
                            text_parts.append(f"Interaction: {part.strip()[:250]}...")
                
                chunk_text = " | ".join(text_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": "drug_interaction",
                        "generic_name": "",
                        "brand_name": "",
                        "company": "",
                        "target": "",
                        "mechanism": "",
                        "drug_class": "",
                        "indication": "",
                        "ticket": "",
                        "title": doc.title or "",
                        "url": doc.source_url,
                        "retrieval_date": doc.retrieval_date.strftime('%Y-%m-%d') if doc.retrieval_date else ""
                    }
                })
            
            db.close()
            
        except Exception as e:
            logger.error(f"Error loading database data: {e}")
        
        logger.info(f"Created {len(chunks)} text chunks for embedding")
        return chunks
    
    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks."""
        try:
            embeddings = self.embedding_model.get_text_embedding_batch(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def populate_database(self):
        """Populate vector database with embeddings."""
        try:
            logger.info("Starting vector database population...")
            
            # Create text chunks
            chunks = self._create_text_chunks()
            
            if not chunks:
                logger.warning("No chunks created, skipping population")
                return
            
            # Extract texts and metadata
            texts = [chunk["text"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            ids = [f"chunk_{i}" for i in range(len(chunks))]
            
            # Generate embeddings
            logger.info("Generating embeddings...")
            embeddings = self._generate_embeddings(texts)
            
            # Add to ChromaDB collection
            logger.info("Adding embeddings to ChromaDB...")
            self.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Successfully populated vector database with {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error populating vector database: {e}")
            raise
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform semantic search on vector database.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of search results with relevance scores
        """
        try:
            # Generate embedding for query
            query_embedding = self.embedding_model.get_text_embedding(query)
            
            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results["documents"][0])):
                # Convert distance to similarity score (lower distance = higher similarity)
                distance = results["distances"][0][i]
                similarity_score = 1.0 / (1.0 + distance)  # Convert distance to similarity
                
                formatted_results.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "similarity_score": similarity_score,
                    "distance": distance
                })
            
            logger.info(f"Semantic search returned {len(formatted_results)} results for query: '{query}'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector database collection."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection.name,
                "total_chunks": count,
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
                "status": "active"
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"status": "error", "error": str(e)}
    
    def reset_collection(self):
        """Reset the collection (useful for re-population)."""
        try:
            self.client.delete_collection(self.collection.name)
            self.collection = self.client.get_or_create_collection(
                name="biopharma_semantic_search",
                metadata={"description": "Biopharmaceutical data for semantic search"}
            )
            logger.info("Collection reset successfully")
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            raise
