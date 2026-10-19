"""Synthetic clinical, genomic, reference, and telemetry data generators."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import random
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

random.seed(42)


def generate_icd10(count: int = 500) -> List[Dict[str, Any]]:
    """Generate realistic ICD-10 diagnostic coding records."""
    categories = [
        ("C00-C97", "II", "Malignant neoplasms", ["C34.9", "C50.9", "C18.9", "C61", "C25.9"]),
        ("I00-I99", "IX", "Diseases of circulatory system", ["I25.1", "I50.9", "I10", "I48.9", "I63.9"]),
        ("G00-G99", "VI", "Diseases of nervous system", ["G30.9", "G20", "G35", "G40.9", "G31.84"]),
        ("E00-E89", "IV", "Endocrine and metabolic diseases", ["E11.9", "E78.5", "E03.9", "E66.9"]),
        ("Q00-Q99", "XVII", "Congenital malformations", ["Q90.9", "Q87.4", "Q78.0", "Q04.0"]),
    ]
    records = []
    for i in range(count):
        block, chap, chap_name, base_codes = categories[i % len(categories)]
        code = f"{random.choice(base_codes)}.{i % 10}"
        records.append({
            "icd10_code": code,
            "code_description": f"Clinical diagnosis variant #{i+1} under {chap_name}",
            "chapter": chap,
            "block": block,
            "is_valid_clinical_concept": True,
        })
    return records


def generate_omop_vocab(count: int = 800) -> List[Dict[str, Any]]:
    """Generate OMOP CDM concept vocabulary records."""
    domains = ["Condition", "Drug", "Measurement", "Procedure", "Observation"]
    records = []
    for i in range(count):
        records.append({
            "concept_id": 4000000 + i,
            "concept_name": f"OMOP Standard Clinical Concept {i+1}",
            "domain_id": domains[i % len(domains)],
            "vocabulary_id": "SNOMED",
            "concept_class_id": "Clinical Finding",
            "standard_concept": "S",
            "concept_code": f"SNOMED_{100000 + i}",
            "valid_start_date": "2020-01-01",
            "valid_end_date": "2099-12-31",
        })
    return records


def generate_gene_panel(count: int = 250) -> List[Dict[str, Any]]:
    """Generate reference gene panel biomarker records."""
    genes = ["BRCA1", "BRCA2", "TP53", "EGFR", "KRAS", "BRAF", "PIK3CA", "PTEN", "APOE", "MAPT", "TTN", "MYH7"]
    chroms = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]
    records = []
    for i in range(count):
        g = genes[i % len(genes)]
        records.append({
            "gene_symbol": f"{g}_{i//len(genes)+1}" if i >= len(genes) else g,
            "gene_id": f"ENSG{100000000 + i}",
            "chromosome": chroms[i % len(chroms)],
            "locus_start": 1000000 + (i * 25000),
            "locus_end": 1020000 + (i * 25000),
            "clinical_significance": random.choice(["Pathogenic", "Likely Pathogenic", "Risk Factor"]),
            "disease_association": random.choice(["Hereditary Cancer", "Cardiomyopathy", "Neurodegeneration"]),
            "inheritance_mode": random.choice(["Autosomal Dominant", "Autosomal Recessive"]),
            "acmg_tier": random.choice(["Tier 1", "Tier 2", "Tier 3"]),
        })
    return records


def generate_lab_ranges(count: int = 150) -> List[Dict[str, Any]]:
    """Generate standard physiological laboratory reference ranges."""
    labs = [
        ("WBC", "White Blood Cells", "Blood", 4.5, 11.0, "10^3/uL"),
        ("RBC", "Red Blood Cells", "Blood", 4.2, 5.9, "10^6/uL"),
        ("PLT", "Platelets", "Blood", 150.0, 450.0, "10^3/uL"),
        ("ALT", "Alanine Aminotransferase", "Serum", 7.0, 56.0, "U/L"),
        ("CREAT", "Creatinine", "Serum", 0.7, 1.3, "mg/dL"),
        ("CRP", "C-Reactive Protein", "Serum", 0.0, 3.0, "mg/L"),
        ("GLUC", "Fasting Glucose", "Plasma", 70.0, 99.0, "mg/dL"),
    ]
    records = []
    for i in range(count):
        code, name, spec, low, high, unit = labs[i % len(labs)]
        records.append({
            "test_code": f"{code}_{i+1}",
            "test_name": f"{name} Panel Variant {i+1}",
            "specimen_type": spec,
            "low_normal_val": low,
            "high_normal_val": high,
            "unit_of_measure": unit,
            "age_group": "ADULT",
            "sex": "ALL",
        })
    return records


def generate_oncology_data(table_id: str, count: int) -> List[Dict[str, Any]]:
    """Generate synthetic oncology spoke datasets."""
    records = []
    for i in range(count):
        pid = f"PAT-ONC-{1000 + (i % 650):04d}"
        if table_id == "patient_cohort":
            records.append({
                "patient_id": pid,
                "enrollment_date": str(date(2023, 1, 1) + timedelta(days=i % 600)),
                "age": random.randint(35, 82),
                "biological_sex": "F" if i % 2 == 0 else "M",
                "primary_diagnosis": random.choice(["NSCLC", "Melanoma", "Colorectal", "Breast Carcinoma"]),
                "stage": random.choice(["Stage IIIA", "Stage IIIB", "Stage IV"]),
                "ecog_ps": random.choice([0, 1, 2]),
                "smoker_status": random.choice(["Never", "Former", "Current"]),
                "vital_status": "Alive" if random.random() > 0.25 else "Deceased",
            })
        elif table_id == "tumor_markers":
            records.append({
                "marker_id": f"TM-{i+1:06d}",
                "patient_id": pid,
                "test_date": str(date(2023, 6, 1) + timedelta(days=i % 400)),
                "marker_name": random.choice(["CEA", "CA-125", "PSA", "AFP", "CA 19-9"]),
                "quantitative_val": round(random.uniform(1.2, 185.0), 2),
                "unit": "ng/mL",
                "reference_range": "< 5.0 ng/mL",
                "flag_abnormal": random.random() > 0.4,
            })
        elif table_id == "treatment_outcomes":
            records.append({
                "outcome_id": f"TX-{i+1:05d}",
                "patient_id": pid,
                "line_of_therapy": random.choice([1, 2, 3]),
                "regimen_name": random.choice(["Pembrolizumab + Chemo", "Nivolumab + Ipilimumab", "Osimertinib"]),
                "start_date": str(date(2023, 2, 1) + timedelta(days=i % 400)),
                "end_date": str(date(2024, 1, 1) + timedelta(days=i % 300)),
                "best_overall_response": random.choice(["Complete Response", "Partial Response", "Stable Disease", "Progressive Disease"]),
                "progression_free_survival_days": random.randint(60, 720),
                "adverse_event_grade": random.choice([0, 1, 2, 3]),
            })
        elif table_id == "immunotherapy_response":
            records.append({
                "response_id": f"IO-{i+1:05d}",
                "patient_id": pid,
                "checkpoint_inhibitor": random.choice(["Pembrolizumab", "Nivolumab", "Atezolizumab"]),
                "pd_l1_tps_percent": round(random.uniform(0.0, 95.0), 1),
                "tmb_score": round(random.uniform(2.5, 38.0), 2),
                "response_category": random.choice(["Responder", "Non-Responder"]),
                "recist_1_1": random.choice(["PR", "CR", "SD", "PD"]),
                "immune_adverse_event": random.random() > 0.7,
            })
    return records


def generate_genomics_data(table_id: str, count: int) -> List[Dict[str, Any]]:
    """Generate synthetic genomics spoke datasets."""
    records = []
    for i in range(count):
        sid = f"SAM-GEN-{100 + (i % 200):03d}"
        if table_id == "variant_calls":
            records.append({
                "variant_id": f"VAR-{i+1:06d}",
                "sample_id": sid,
                "chromosome": f"chr{random.randint(1, 22)}",
                "position": random.randint(100000, 150000000),
                "ref_allele": random.choice(["A", "C", "G", "T"]),
                "alt_allele": random.choice(["T", "G", "C", "A"]),
                "genotype": random.choice(["0/1", "1/1"]),
                "filter_status": "PASS",
                "depth": random.randint(30, 120),
                "allele_frequency": round(random.uniform(0.0001, 0.45), 5),
                "clinvar_id": f"RCV{i+1:07d}",
                "pathogenicity": random.choice(["Pathogenic", "Likely Pathogenic", "VUS", "Benign"]),
            })
        elif table_id == "sample_manifests":
            records.append({
                "sample_id": sid,
                "subject_id": f"SUBJ-{100 + (i % 200):03d}",
                "tissue_type": random.choice(["Peripheral Blood", "Skin Biopsy", "Saliva"]),
                "sequencing_type": "WGS",
                "platform": "Illumina NovaSeq 6000",
                "mean_coverage": round(random.uniform(32.5, 68.0), 1),
                "percent_q30": round(random.uniform(91.0, 98.5), 1),
                "library_prep_date": str(date(2023, 3, 1) + timedelta(days=i % 300)),
                "batch_id": f"BATCH-WGS-2023-{(i//20)+1:02d}",
            })
        elif table_id == "phenotype_mapping":
            records.append({
                "phenotype_id": f"PHE-{i+1:05d}",
                "subject_id": f"SUBJ-{100 + (i % 200):03d}",
                "hpo_id": f"HP:{random.randint(1000, 9999):07d}",
                "hpo_term": random.choice(["Muscular dystrophy", "Seizures", "Ataxia", "Microcephaly", "Cardiomyopathy"]),
                "onset_age_years": round(random.uniform(0.5, 18.0), 1),
                "modifier": random.choice(["Severe", "Moderate", "Mild"]),
                "confirmed_flag": True,
            })
    return records


def generate_cardio_data(table_id: str, count: int) -> List[Dict[str, Any]]:
    """Generate synthetic cardio spoke datasets."""
    records = []
    for i in range(count):
        pid = f"PAT-CARD-{100 + (i % 400):03d}"
        if table_id == "ecg_telemetry_metrics":
            records.append({
                "recording_id": f"ECG-{i+1:06d}",
                "patient_id": pid,
                "timestamp": f"2024-03-01T{i%24:02d}:{(i*7)%60:02d}:00Z",
                "heart_rate_bpm": round(random.uniform(55.0, 115.0), 1),
                "pr_interval_ms": round(random.uniform(120.0, 210.0), 1),
                "qrs_duration_ms": round(random.uniform(80.0, 135.0), 1),
                "qtc_interval_ms": round(random.uniform(380.0, 480.0), 1),
                "rhythm_interpretation": random.choice(["Sinus Rhythm", "Sinus Tachycardia", "Atrial Fibrillation"]),
                "st_segment_elevation": random.random() > 0.88,
            })
        elif table_id == "lipid_profiles":
            records.append({
                "lipid_id": f"LIP-{i+1:05d}",
                "patient_id": pid,
                "sample_date": str(date(2023, 4, 1) + timedelta(days=i % 350)),
                "total_cholesterol_mg_dl": round(random.uniform(140.0, 280.0), 1),
                "hdl_mg_dl": round(random.uniform(35.0, 75.0), 1),
                "ldl_mg_dl": round(random.uniform(80.0, 190.0), 1),
                "triglycerides_mg_dl": round(random.uniform(90.0, 250.0), 1),
                "hs_crp_mg_l": round(random.uniform(0.5, 9.8), 2),
                "statin_therapy": random.random() > 0.45,
            })
        elif table_id == "patient_registry":
            records.append({
                "patient_id": pid,
                "enrollment_date": str(date(2022, 6, 1) + timedelta(days=i % 400)),
                "age_at_intake": random.randint(45, 85),
                "sex": "M" if i % 2 == 0 else "F",
                "baseline_sbp": random.randint(110, 175),
                "baseline_dbp": random.randint(70, 105),
                "bmi": round(random.uniform(21.5, 37.0), 1),
                "hypertension_history": random.random() > 0.35,
                "diabetes_history": random.random() > 0.6,
                "smoker": random.random() > 0.7,
            })
        elif table_id == "cardiac_events":
            records.append({
                "event_id": f"EVT-{i+1:05d}",
                "patient_id": pid,
                "event_date": str(date(2023, 8, 1) + timedelta(days=i % 300)),
                "event_type": random.choice(["Myocardial Infarction", "Unstable Angina", "Heart Failure Exacerbation", "Stroke"]),
                "adjudicated_flag": True,
                "nyha_class": random.choice(["Class II", "Class III", "Class IV"]),
                "ejection_fraction_percent": round(random.uniform(30.0, 60.0), 1),
                "intervention": random.choice(["PCI / Stent", "CABG", "Medical Management"]),
            })
    return records


def generate_neurology_data(table_id: str, count: int) -> List[Dict[str, Any]]:
    """Generate synthetic neurology spoke datasets."""
    records = []
    for i in range(count):
        pid = f"PART-NEUR-{100 + (i % 200):03d}"
        if table_id == "cognitive_assessments":
            records.append({
                "assessment_id": f"COG-{i+1:05d}",
                "participant_id": pid,
                "assessment_date": str(date(2023, 5, 1) + timedelta(days=i % 360)),
                "mmse_score": random.randint(18, 30),
                "adas_cog_score": round(random.uniform(5.0, 45.0), 1),
                "cdr_sum_of_boxes": round(random.uniform(0.0, 9.5), 1),
                "mo_ca_score": random.randint(16, 29),
                "clinician_notes_summary": f"Mild cognitive assessment evaluation notes #{i+1}",
            })
        elif table_id == "mri_volumetric_features":
            records.append({
                "scan_id": f"MRI-{i+1:05d}",
                "participant_id": pid,
                "scan_date": str(date(2023, 6, 1) + timedelta(days=i % 300)),
                "whole_brain_volume_cm3": round(random.uniform(1050.0, 1380.0), 1),
                "hippocampal_volume_left_mm3": round(random.uniform(2800.0, 4200.0), 1),
                "hippocampal_volume_right_mm3": round(random.uniform(2900.0, 4350.0), 1),
                "entorhinal_cortex_thickness_mm": round(random.uniform(2.1, 3.8), 2),
                "white_matter_hyperintensities_cm3": round(random.uniform(1.2, 14.5), 2),
            })
        elif table_id == "clinical_trial_registry":
            records.append({
                "enrollment_id": f"TRL-{i+1:04d}",
                "participant_id": pid,
                "trial_arm": random.choice(["Active Drug 10mg", "Active Drug 20mg", "Placebo"]),
                "cohort_type": random.choice(["Early MCI", "Mild AD", "Pre-symptomatic"]),
                "baseline_abeta_42": round(random.uniform(450.0, 1100.0), 1),
                "baseline_ptau_181": round(random.uniform(15.0, 85.0), 1),
                "apoe_genotype": random.choice(["e3/e3", "e3/e4", "e4/e4", "e2/e3"]),
                "active_trial_status": "COMPLETED" if i % 4 == 0 else "ACTIVE",
            })
    return records
