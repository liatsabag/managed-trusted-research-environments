"""Structured synthetic approval document generator for 5-Item Regulatory Checklist."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


from typing import Any, Dict, List

ROOM_APPROVAL_SPECS: Dict[str, Dict[str, Any]] = {
    "rr-oncology-01": {
        "title": "Precision Oncology Genomic Biomarker Cohort",
        "protocol_no": "ONC-2024-881",
        "irb_no": "IRB-TLV-2024-099",
        "dtc_no": "DTC-MOH-2024-412",
        "ext_no": "EXT-ONC-2024-11",
        "dua_no": "DUA-MOH-ONC-2024",
        "approver": "Prof. D. Weiss, Oncology Review Board",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "Dean of Medicine & Hospital Directorate",
        "approval_date": "2024-10-15",
        "expiration_date": "2027-12-31",
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Data_Transfer", "Extraction_Protocol", "DUA"],
    },
    "rr-genomics-02": {
        "title": "Rare Variant Discovery and Population Pharmacogenomics",
        "protocol_no": "GEN-2025-101",
        "irb_no": "IRB-TLV-2025-012",
        "dtc_no": "DTC-MOH-2025-098",
        "ext_no": "EXT-GEN-2025-02",
        "dua_no": "DUA-MOH-GEN-2025",
        "approver": "Dr. E. Ben-Ari, Institute of Human Genetics",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "National Research Authority",
        "approval_date": "2025-01-10",
        "expiration_date": "2028-01-10",
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Data_Transfer", "Extraction_Protocol", "DUA"],
    },
    "rr-cardio-03": {
        "title": "Cardiovascular Risk Stratification & MACE Cohort",
        "protocol_no": "CARD-2024-512",
        "irb_no": "IRB-TLV-2024-104",
        "dtc_no": "DTC-MOH-2024-418",
        "ext_no": "EXT-CARD-2024-05",
        "dua_no": "DUA-MOH-CARD-2024",
        "approver": "Prof. A. Goldstein, Cardiology Board",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "Hospital Directorate Legal Affairs",
        "approval_date": "2024-11-01",
        "expiration_date": "2027-11-01",
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Data_Transfer", "Extraction_Protocol", "DUA"],
    },
    "rr-neurology-04": {
        "title": "Neurodegenerative Biomarkers and Cognitive Trajectories",
        "protocol_no": "NEUR-2025-303",
        "irb_no": "IRB-TLV-2025-045",
        "dtc_no": "DTC-MOH-2025-155",
        "ext_no": "EXT-NEUR-2025-09",
        "dua_no": "DUA-MOH-NEUR-2025",
        "approver": "Prof. M. Stern, Neurological Research Center",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "Hospital Directorate Legal Affairs",
        "approval_date": "2025-02-01",
        "expiration_date": "2027-08-30",
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Data_Transfer", "Extraction_Protocol", "DUA"],
    },
    "rr-immunology-05": {
        "title": "Autoimmune Biomarkers and Biological Therapeutics",
        "protocol_no": "IMM-2025-702",
        "irb_no": "IRB-TLV-2025-088",
        "dtc_no": "DTC-MOH-2025-PENDING",
        "ext_no": "EXT-IMM-2025-01",
        "dua_no": "DUA-MOH-IMM-2025",
        "approver": "Prof. R. Sharon, Department of Immunology",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "Hospital Directorate Legal Affairs",
        "approval_date": "2025-03-15",
        "expiration_date": "2027-03-15",
        # TEST CASE: Missing Data_Transfer Statutory Sign-off!
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Extraction_Protocol", "DUA"],
    },
    "rr-pediatrics-06": {
        "title": "Pediatric Rare Disorders Longitudinal Study",
        "protocol_no": "PED-2024-001",
        "irb_no": "IRB-TLV-2024-010",
        "dtc_no": "DTC-MOH-2024-080",
        "ext_no": "EXT-PED-2024-04",
        "dua_no": "DUA-MOH-PED-2024",
        "approver": "Dr. H. Naveh, Pediatric Research Institute",
        "irb_approver": "Dr. Sarah Lev, Helsinki Ethics Chair",
        "dtc_approver": "Adv. Michael Bar, Statutory Data Commissioner",
        "ext_approver": "Eng. Tamar Cohen, CISO & Privacy Officer",
        "dua_approver": "Hospital Directorate Legal Affairs",
        "approval_date": "2024-01-15",
        # TEST CASE: Expired Helsinki IRB (Expired 2026-06-30 vs current 2026-09-27)
        "irb_expiration_date": "2026-06-30",
        "expiration_date": "2027-12-31",
        "include_items": ["Research_Protocol", "Helsinki_IRB", "Data_Transfer", "Extraction_Protocol", "DUA"],
    },
}


def build_document_content(room_id: str, item_type: str, spec: Dict[str, Any]) -> str:
    """Generate high-fidelity structured text for a single regulatory prerequisite."""
    app_date = spec.get("approval_date", "2025-01-01")
    exp_date = spec.get("irb_expiration_date", spec.get("expiration_date", "2027-12-31")) if item_type == "Helsinki_IRB" else spec.get("expiration_date", "2027-12-31")

    if item_type == "Research_Protocol":
        return f"""================================================================================
GCP HEALTH DATA PLATFORM - SCIENTIFIC RESEARCH PROTOCOL APPROVAL
================================================================================
Room Identifier: {room_id}
Study Title: {spec['title']}
Protocol Reference: {spec['protocol_no']}
Item Type: Research_Protocol
Item Name: Scientific Research Protocol Sign-Off

STATUS: APPROVED
Approval Date: {app_date}
Expiration Date: {exp_date}
Approving Body: Institutional Scientific Oversight Committee
Approver Name: {spec['approver']}

TERMS OF RESEARCH:
1. The research team is authorized to perform computational analysis on cohort data.
2. Direct raw data egress is prohibited. All analytical outputs must undergo automated quarantine review.
3. Protocol revisions require formal addenda submission.
================================================================================
"""
    elif item_type == "Helsinki_IRB":
        return f"""================================================================================
HELSINKI ETHICS COMMITTEE / INSTITUTIONAL REVIEW BOARD (IRB) APPROVAL
================================================================================
Room Identifier: {room_id}
Study Title: {spec['title']}
IRB Protocol Number: {spec['irb_no']}
Item Type: Helsinki_IRB
Item Name: Helsinki Ethics Committee Statutory Approval

STATUS: APPROVED
Approval Date: {app_date}
Valid Through (Expiration): {exp_date}
Ethics Board: Tel-Aviv Medical Center Helsinki Committee
Chair / Approver: {spec['irb_approver']}

ETHICAL CLEARANCE TERMS:
1. Ethics approval is granted in accordance with the Declaration of Helsinki.
2. Informed consent waiver applies under secondary research de-identification provisions.
3. Access is strictly bound to certified investigators.
================================================================================
"""
    elif item_type == "Data_Transfer":
        return f"""================================================================================
DATA TRANSFER COMMITTEE (DTC) STATUTORY SIGN-OFF
================================================================================
Room Identifier: {room_id}
Study Title: {spec['title']}
Transfer Clearance Ref: {spec['dtc_no']}
Item Type: Data_Transfer
Item Name: Statutory Data Transfer Committee Approval

STATUS: APPROVED
Approval Date: {app_date}
Expiration Date: {exp_date}
Statutory Body: Ministry of Health & Hospital Data Transfer Directorate
Authorized Officer: {spec['dtc_approver']}

TRANSFER SPECIFICATIONS:
1. Data source tables authorized for replication into Spoke Inbound Storage.
2. Cross-border transmission is strictly restricted.
================================================================================
"""
    elif item_type == "Extraction_Protocol":
        return f"""================================================================================
DE-IDENTIFICATION & EXTRACTION QUERY PROTOCOL SPECIFICATION
================================================================================
Room Identifier: {room_id}
Study Title: {spec['title']}
Query Protocol ID: {spec['ext_no']}
Item Type: Extraction_Protocol
Item Name: De-identification and Extraction Query Protocol

STATUS: APPROVED
Approval Date: {app_date}
Expiration Date: {exp_date}
Review Authority: Security & Data Privacy Review Board
Privacy Officer: {spec['ext_approver']}

EXTRACTION CRITERIA:
1. Direct identifiers (Name, MRN, National ID, Phone) stripped prior to ingestion.
2. Minimum k-anonymity threshold enforced (k >= 5) on exported summary strata.
================================================================================
"""
    elif item_type == "DUA":
        return f"""================================================================================
MULTI-PARTY DATA USE AGREEMENT (DUA)
================================================================================
Room Identifier: {room_id}
Study Title: {spec['title']}
DUA Master Agreement: {spec['dua_no']}
Item Type: DUA
Item Name: Multi-party Data Use Agreement

STATUS: APPROVED
Execution Date: {app_date}
Expiration Date: {exp_date}
Parties: Data Custodian, Academic Medical Center, and Principal Investigator
Legal Signatory: {spec['dua_approver']}

COVENANTS AND WARRANTIES:
1. Data recipient will not attempt re-identification of research subjects.
2. Cloud compute infrastructure must maintain CMEK encryption and perimeter isolation.
================================================================================
"""
    return f"Approval Document for {room_id} - {item_type}"
