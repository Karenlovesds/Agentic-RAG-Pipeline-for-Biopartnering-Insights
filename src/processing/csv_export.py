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


def export_drugs_dashboard(db: Session, out_path: str) -> str:
    """Export drugs data to CSV format for dashboard display."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Remove existing file if it exists to ensure clean overwrite
        if path.exists():
            logger.info(f"Removing existing file: {path}")
            path.unlink()
        
        logger.info(f"Exporting drugs dashboard data to: {path}")
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS)

            # Export drugs with all related data
            drugs = db.query(Drug).all()
            for d in drugs:
                company_name = d.company.name if d.company else ""
                # Filter out completed trials
                trials = db.query(ClinicalTrial).filter(
                    ClinicalTrial.drug_id == d.id,
                    ClinicalTrial.status != "Completed"
                ).all()
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
                    d.fda_approval_date.strftime("%Y-%m-%d") if d.fda_approval_date else "",
                    d.drug_class or "",
                    " | ".join([dt.target.name.upper() for dt in d.targets]) if d.targets else "",
                    (d.mechanism_of_action or "").strip(),
                    " | ".join([di.indication.name for di in d.indications]) if d.indications else "",
                    " || ".join(trial_summaries),
                ])
        
        logger.info(f"✅ Drugs dashboard export completed: {path}")
        return str(path)
        
    except Exception as e:
        logger.error(f"❌ Failed to export drugs dashboard data to {path}: {e}")
        raise


# Removed export_drug_table function - consolidated into export_drugs_dashboard


