"""Seed raw_storage_inventory and creator audit events, and configure Storage Insights schema."""

import logging
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_storage_insights")
HUB_PROJECT = "gcp-rr-hub-core"

INVENTORY_ROWS = [
    # Oncology 01
    ("rr-oncology-01-inbound", "cohort_alpha/rnaseq_matrix_sample1.bam", 9225000000, "dr.oren.katz@example-tre.org", "rr-oncology-01"),
    ("rr-oncology-01-inbound", "cohort_alpha/rnaseq_matrix_sample2.bam", 9225000000, "dr.oren.katz@example-tre.org", "rr-oncology-01"),
    ("rr-oncology-01-inbound", "histopathology/wsi_slide_001.svs", 6410000000, "prof.miriam.levy@example-tre.org", "rr-oncology-01"),
    ("rr-oncology-01-inbound", "histopathology/wsi_slide_002.svs", 6410000000, "prof.miriam.levy@example-tre.org", "rr-oncology-01"),
    # Genomics 02
    ("rr-genomics-02-inbound", "wgs_cohort/sample_patient_01.cram", 17250000000, "dr.eitan.rosen@example-tre.org", "rr-genomics-02"),
    ("rr-genomics-02-inbound", "wgs_cohort/sample_patient_02.cram", 17250000000, "dr.eitan.rosen@example-tre.org", "rr-genomics-02"),
    ("rr-genomics-02-inbound", "vcf_callsets/annotated_variants_exome.vcf.gz", 13375000000, "prof.anat.shapiro@example-tre.org", "rr-genomics-02"),
    ("rr-genomics-02-inbound", "vcf_callsets/structural_variants.vcf.gz", 13375000000, "prof.anat.shapiro@example-tre.org", "rr-genomics-02"),
    # Cardio 03
    ("rr-cardio-03-inbound", "telemetry_streams/ecg_continuous_lead12.parquet", 14200000000, "dr.maya.lin@example-tre.org", "rr-cardio-03"),
    ("rr-cardio-03-inbound", "echocardiograms/echo_dicom_series_patient01.dcm", 11300000000, "dr.daniel.cohen@example-tre.org", "rr-cardio-03"),
    # Neurology 04
    ("rr-neurology-04-inbound", "mri_scans/fmri_3t_bold_series.nii.gz", 2160000000, "dr.noa.shapira@example-tre.org", "rr-neurology-04"),
    ("rr-neurology-04-inbound", "mri_scans/fmri_3t_bold_series_part2.nii.gz", 19440000000, "dr.noa.shapira@example-tre.org", "rr-neurology-04"),
    ("rr-neurology-04-inbound", "eeg_records/high_density_eeg_raw.edf", 16900000000, "dr.rami.friedman@example-tre.org", "rr-neurology-04")
]

def main():
    client = bigquery.Client(project=HUB_PROJECT)

    # 1. Clean today's snapshot and insert into raw_storage_inventory
    client.query(f"DELETE FROM `{HUB_PROJECT}.hub_telemetry.raw_storage_inventory` WHERE snapshot_date = CURRENT_DATE()").result()
    
    rows_sql = ",\n".join([
        f"(CURRENT_DATE(), '{b}', '{n}', {s}, 'STANDARD', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), 'application/octet-stream')"
        for b, n, s, u, r in INVENTORY_ROWS
    ])
    insert_inv = f"""
    INSERT INTO `{HUB_PROJECT}.hub_telemetry.raw_storage_inventory` 
    (snapshot_date, bucket, name, size, storage_class, time_created, updated, content_type)
    VALUES
    {rows_sql};
    """
    client.query(insert_inv).result()
    logger.info("Successfully seeded raw_storage_inventory with %d object manifests.", len(INVENTORY_ROWS))

    # 2. Insert creator audit events into ops_audit_events_curated
    for idx, (b, n, s, u, r) in enumerate(INVENTORY_ROWS):
        log_id = f"audit-gcs-obj-{idx}"
        res_name = f"projects/_/buckets/{b}/objects/{n}"
        merge_sql = f"""
        MERGE `{HUB_PROJECT}.hub_telemetry.ops_audit_events_curated` T
        USING (
            SELECT 
                '{log_id}' AS log_id,
                CURRENT_TIMESTAMP() AS timestamp,
                '{r}' AS room_id,
                '{r}' AS project_id,
                '{u}' AS principal_email,
                'DATA_ACCESS' AS category,
                'storage.googleapis.com' AS service_name,
                'storage.objects.create' AS action_name,
                '{res_name}' AS resource_name,
                'SUCCESS' AS status,
                'INFO' AS severity,
                'GCS Object Creation attributed to researcher' AS description,
                '{{\"bucket\": \"{b}\", \"object\": \"{n}\"}}' AS metadata_json
        ) S
        ON T.log_id = S.log_id
        WHEN MATCHED THEN
            UPDATE SET 
                resource_name = S.resource_name,
                principal_email = S.principal_email,
                room_id = S.room_id
        WHEN NOT MATCHED THEN
            INSERT (log_id, timestamp, room_id, project_id, principal_email, category, service_name, action_name, resource_name, status, severity, description, metadata_json)
            VALUES (S.log_id, S.timestamp, S.room_id, S.project_id, S.principal_email, S.category, S.service_name, S.action_name, S.resource_name, S.status, S.severity, S.description, S.metadata_json);
        """
        client.query(merge_sql).result()
    logger.info("Successfully merged object creation audit trail records.")

if __name__ == "__main__":
    main()
