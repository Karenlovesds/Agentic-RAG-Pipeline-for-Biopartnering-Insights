"""Basic CSV exporter for standardized drug/trial fields (placeholder)."""

from __future__ import annotations

from typing import List
import csv
from pathlib import Path
from sqlalchemy.orm import Session
from loguru import logger

from src.models.entities import Drug, ClinicalTrial, Company


HEADERS = [
    "Company name",
    "Generic name",
    "Brand name",
    "FDA approval status",
    "Approval date",
    "Drug class",
    "Target(s)",
    "Mechanism of action",
    "Indications",
    "Current clinical trials",
]


def export_basic(db: Session, out_path: str) -> str:
    """Export basic drug data to CSV with proper overwrite handling."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Remove existing file if it exists to ensure clean overwrite
        if path.exists():
            logger.info(f"Removing existing file: {path}")
            path.unlink()
        
        logger.info(f"Exporting basic data to: {path}")
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)

            # Placeholder export: join Drug + Company; trials summarized per drug
            drugs = db.query(Drug).all()
            for d in drugs:
                company_name = d.company.name if d.company else ""
                trials = db.query(ClinicalTrial).filter(ClinicalTrial.drug_id == d.id).all()
                trial_summaries: List[str] = []
                for t in trials:
                    trial_summaries.append(
                        " | ".join([
                            (t.title or "").strip(),
                            (t.phase or "").strip(),
                            (t.status or "").strip(),
                            t.nct_id,
                        ])
                    )
                writer.writerow([
                    company_name,
                    d.generic_name,
                    d.brand_name or "",
                    "Y" if d.fda_approval_status else "N",
                    d.fda_approval_date.isoformat() if d.fda_approval_date else "",
                    d.drug_class or "",
                    "; ".join([dt.target.name for dt in d.targets]) if d.targets else "",
                    (d.mechanism_of_action or "").strip(),
                    "; ".join([di.indication.name for di in d.indications]) if d.indications else "",
                    " || ".join(trial_summaries),
                ])
        
        logger.info(f"✅ Basic export completed: {path}")
        return str(path)
        
    except Exception as e:
        logger.error(f"❌ Failed to export basic data to {path}: {e}")
        raise


DRUG_TABLE_HEADERS = [
    "Company name",
    "Generic name",
    "Brand name",
    "FDA Approval",
    "Drug Class",
    "Target",
    "Mechanism",
    "Indication Approved",
    "Current Clinical Trials",
]


def export_drug_table(db: Session, out_path: str) -> str:
    """Export a drug-centric table matching the provided schema."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Remove existing file if it exists to ensure clean overwrite
        if path.exists():
            logger.info(f"Removing existing file: {path}")
            path.unlink()
        
        logger.info(f"Exporting drug table to: {path}")
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(DRUG_TABLE_HEADERS)

            drugs = db.query(Drug).all()
            for d in drugs:
                fda_approval = ""
                if d.fda_approval_date:
                    # Format YYYY/MM if day is not important
                    try:
                        fda_approval = d.fda_approval_date.strftime("%Y/%m")
                    except Exception:
                        fda_approval = d.fda_approval_date.isoformat()
                targets = "; ".join([dt.target.name for dt in d.targets]) if d.targets else ""
                indications_approved = "; ".join([
                    di.indication.name for di in d.indications if getattr(di, "approval_status", False)
                ]) if d.indications else ""
                trials = db.query(ClinicalTrial).filter(ClinicalTrial.drug_id == d.id).all()
                trial_summaries = []
                for t in trials:
                    parts = [
                        (t.title or "").strip(),
                        (t.phase or "").strip(),
                        (t.status or "").strip(),
                    ]
                    trial_summaries.append(" | ".join([p for p in parts if p]))
                writer.writerow([
                    d.company.name if d.company else "",
                    d.generic_name,
                    d.brand_name or "",
                    fda_approval,
                    d.drug_class or "",
                    targets,
                    (d.mechanism_of_action or "").strip(),
                    indications_approved,
                    "; ".join(trial_summaries),
                ])
        
        logger.info(f"✅ Drug table export completed: {path}")
        return str(path)
        
    except Exception as e:
        logger.error(f"❌ Failed to export drug table to {path}: {e}")
        raise


