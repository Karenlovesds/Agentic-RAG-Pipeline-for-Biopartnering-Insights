"""Minimal processing pipeline: heuristic entity extraction and linking.

This is a placeholder implementation to demonstrate flow:
- Extract companies from the configured list and ensure DB rows exist
- Heuristically create drugs if certain keywords appear in documents
- Link trials to companies by sponsor name containment
"""

from __future__ import annotations

from typing import List
from loguru import logger
from sqlalchemy.orm import Session

from config import get_target_companies
from src.models.entities import Company, Drug, ClinicalTrial, Document


COMMON_DRUG_KEYWORDS = [
    "pembrolizumab", "nivolumab", "trastuzumab", "palbociclib", "olaparib",
]


def ensure_companies(db: Session) -> int:
    count_created = 0
    for name in get_target_companies():
        if not db.query(Company).filter(Company.name == name).first():
            db.add(Company(name=name))
            count_created += 1
    if count_created:
        db.commit()
    return count_created


def extract_drugs_from_documents(db: Session) -> int:
    created = 0
    docs = db.query(Document).all()
    companies = {c.name: c.id for c in db.query(Company).all()}
    for doc in docs:
        text = (doc.content or "").lower()
        for kw in COMMON_DRUG_KEYWORDS:
            if kw in text:
                # Use first company found in doc title/url as a naive owner
                owner_id = None
                for cname, cid in companies.items():
                    if (doc.title and cname.lower() in doc.title.lower()) or cname.lower() in doc.source_url.lower():
                        owner_id = cid
                        break
                if not db.query(Drug).filter(Drug.generic_name == kw).first():
                    db.add(Drug(generic_name=kw, company_id=owner_id or list(companies.values())[0]))
                    created += 1
    if created:
        db.commit()
    return created


def link_trials_to_companies(db: Session) -> int:
    updates = 0
    companies = db.query(Company).all()
    trials = db.query(ClinicalTrial).all()
    for t in trials:
        if t.sponsor_id:
            continue
        for c in companies:
            if t.title and c.name.lower() in t.title.lower():
                t.sponsor_id = c.id
                updates += 1
                break
    if updates:
        db.commit()
    return updates


def run_processing(db: Session) -> dict:
    logger.info("Processing pipeline start")
    created_companies = ensure_companies(db)
    created_drugs = extract_drugs_from_documents(db)
    linked_trials = link_trials_to_companies(db)
    logger.info("Processing pipeline done")
    return {
        "companies_created": created_companies,
        "drugs_created": created_drugs,
        "trials_linked": linked_trials,
    }


