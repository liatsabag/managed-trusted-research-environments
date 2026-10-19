"""Gemini-powered Airlock Data Egress Governance and Privacy Risk Scanner Service."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from google.cloud import bigquery, storage

from backend.app.core.config import get_settings
from backend.app.models.airlock import (
    AirlockActionRequest,
    AirlockActionResponse,
    AirlockExportCandidate,
)

logger = logging.getLogger("gemini_risk_service")


class GeminiRiskService:
    """Evaluates candidate data export files from spoke research rooms for privacy risks via Gemini AI."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.bq_client = bigquery.Client(
            project=self.settings.GCP_PROJECT_ID,
            location=self.settings.GCP_REGION,
        )
        self.storage_client = storage.Client(project=self.settings.GCP_PROJECT_ID)

    def _get_export_buckets(self, room_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Retrieve active spoke rooms and their export bucket names."""
        reg_table = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_REGISTRY_DATASET}.reg_research_rooms"
        query = f"SELECT room_id, export_bucket, spoke_project_id FROM `{reg_table}`"
        if room_id:
            query += f" WHERE room_id = '{room_id}'"
        
        buckets = []
        for r in self.bq_client.query(query).result():
            b_name = r["export_bucket"].replace("gs://", "").strip("/")
            buckets.append({"room_id": r["room_id"], "bucket_name": b_name, "project_id": r["spoke_project_id"]})
        return buckets

    def list_candidates(self, room_id: Optional[str] = None) -> List[AirlockExportCandidate]:
        """List all candidate export files in spoke export buckets with their latest Gemini scan results."""
        buckets = self._get_export_buckets(room_id)
        
        # 1. Fetch historical scans from ops_airlock_export_scans
        scans_table = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_airlock_export_scans"
        scans_by_key: Dict[str, Dict[str, Any]] = {}
        try:
            q_scans = f"""
                SELECT scan_id, room_id, file_name, bucket_name, file_size_bytes, researcher_email,
                       risk_score, risk_level, pii_tokens, k_anonymity_violation, findings,
                       recommendation, reason, status, scanned_at, created_at
                FROM `{scans_table}`
                QUALIFY ROW_NUMBER() OVER (PARTITION BY room_id, file_name ORDER BY scanned_at DESC, created_at DESC) = 1
            """
            for row in self.bq_client.query(q_scans).result():
                key = f"{row['room_id']}/{row['file_name']}"
                scans_by_key[key] = dict(row)
        except Exception as e:
            logger.warning("Could not read ops_airlock_export_scans: %s", e)

        candidates: List[AirlockExportCandidate] = []
        for b_info in buckets:
            r_id = b_info["room_id"]
            b_name = b_info["bucket_name"]
            try:
                bucket = self.storage_client.bucket(b_name)
                blobs = list(bucket.list_blobs(max_results=50))
                for blob in blobs:
                    if blob.name.endswith("/"):
                        continue
                    key = f"{r_id}/{blob.name}"
                    created_iso = blob.time_created.isoformat() if blob.time_created else None
                    
                    # Deduce researcher from filename e.g. analysis_output_dr.oren.katz_20260928_203105.csv
                    researcher = None
                    if "dr." in blob.name or "prof." in blob.name:
                        parts = blob.name.split("_")
                        for part in parts:
                            if part.startswith("dr.") or part.startswith("prof."):
                                researcher = f"{part}@{self.settings.ADMIN_DOMAIN}"
                                break

                    scan_data = scans_by_key.get(key)
                    if scan_data:
                        scanned_ts = scan_data["scanned_at"].isoformat() if scan_data.get("scanned_at") else None
                        candidates.append(
                            AirlockExportCandidate(
                                scan_id=scan_data.get("scan_id"),
                                room_id=r_id,
                                file_name=blob.name,
                                bucket_name=b_name,
                                file_size_bytes=blob.size or scan_data.get("file_size_bytes", 0),
                                created_at=created_iso or scan_data.get("created_at"),
                                researcher_email=researcher or scan_data.get("researcher_email"),
                                status=scan_data.get("status", "SCANNED"),
                                risk_score=scan_data.get("risk_score"),
                                risk_level=scan_data.get("risk_level"),
                                pii_tokens_detected=list(scan_data.get("pii_tokens") or []),
                                k_anonymity_violation=bool(scan_data.get("k_anonymity_violation", False)),
                                findings=list(scan_data.get("findings") or []),
                                recommendation=scan_data.get("recommendation"),
                                reason=scan_data.get("reason"),
                                scanned_at=scanned_ts,
                            )
                        )
                    else:
                        candidates.append(
                            AirlockExportCandidate(
                                room_id=r_id,
                                file_name=blob.name,
                                bucket_name=b_name,
                                file_size_bytes=blob.size or 0,
                                created_at=created_iso,
                                researcher_email=researcher,
                                status="PENDING_SCAN",
                            )
                        )
            except Exception as e:
                logger.warning("Error reading bucket %s for room %s: %s", b_name, r_id, e)

        return candidates

    def scan_export_file(self, room_id: str, file_name: str) -> AirlockExportCandidate:
        """Read candidate file from GCS, invoke BigQuery ML Gemini remote model, and persist evaluation."""
        buckets = self._get_export_buckets(room_id)
        if not buckets:
            raise ValueError(f"Research room {room_id} not found.")
        
        bucket_name = buckets[0]["bucket_name"]
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        if not blob.exists():
            raise FileNotFoundError(f"File {file_name} does not exist in bucket gs://{bucket_name}")

        blob.reload()
        file_size = blob.size or 0
        created_iso = blob.time_created.isoformat() if blob.time_created else datetime.now(timezone.utc).isoformat()
        
        # Read header + first 35 lines or up to 8KB
        content_bytes = blob.download_as_bytes(start=0, end=min(8192, file_size or 8192))
        sample_text = content_bytes.decode("utf-8", errors="replace")
        lines = sample_text.splitlines()[:35]
        sample_snippet = "\n".join(lines)

        # Build Gemini Governance Evaluation Prompt
        prompt = f"""You are a strict healthcare data compliance officer, medical privacy auditor, and HIPAA Safe Harbor verification engine.
Analyze the following candidate analytical export file snippet from Research Room '{room_id}' for direct identifiers, quasi-identifiers, Protected Health Information (PHI), and k-anonymity privacy violations (such as cell counts k < 5).

Evaluation Rules:
1. Direct Identifiers (CRITICAL Risk): MRN, Patient ID, National ID/SSN, Patient Full Name, Phone, Email, Physical Address, Full Date of Birth (DOB).
2. Quasi-Identifiers / Re-identification: 5-digit ZIP codes combined with age/gender, rare disease diagnoses with low cohort count (k < 5).
3. If aggregate statistical metrics (e.g. mean, stddev, cohort count >= 10, de-identified feature coefficients) are present with no PII, classify as LOW risk (Score 0-25) and recommend APPROVE.
4. If raw patient rows or direct PII tokens are present, classify as HIGH/CRITICAL (Score 75-100), flag violations, and recommend REJECT.

Return ONLY a valid JSON object matching this schema exactly:
{{
  "risk_score": 0-100,
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "pii_tokens_detected": ["token_or_column_names"],
  "k_anonymity_violation": true | false,
  "findings": ["finding description 1", "finding description 2"],
  "recommendation": "APPROVE" | "FLAG_FOR_REVIEW" | "REJECT",
  "reason": "Executive summary explanation"
}}

Candidate Export File Content:
\"\"\"
{sample_snippet}
\"\"\""""

        # Call BigQuery ML Gemini remote model
        bq_query = f"""
            SELECT ml_generate_text_result
            FROM ML.GENERATE_TEXT(
              MODEL `{self.settings.GCP_PROJECT_ID}.hub_telemetry.gemini_flash_model`,
              (SELECT @prompt AS prompt),
              STRUCT(0.1 AS temperature, 1024 AS max_output_tokens)
            )
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("prompt", "STRING", prompt)]
        )
        res_rows = list(self.bq_client.query(bq_query, job_config=job_config).result())
        if not res_rows:
            raise RuntimeError("Gemini AI model returned empty evaluation.")
        
        raw_res = res_rows[0]["ml_generate_text_result"]
        # Extract JSON string from candidate parts
        gen_text = ""
        try:
            candidates_list = raw_res.get("candidates", [])
            if candidates_list:
                parts = candidates_list[0].get("content", {}).get("parts", [])
                if parts:
                    gen_text = parts[0].get("text", "")
        except Exception:
            gen_text = str(raw_res)

        clean_json = gen_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        parsed = json.loads(clean_json)
        risk_score = int(parsed.get("risk_score", 50))
        risk_level = str(parsed.get("risk_level", "MEDIUM")).upper()
        pii_tokens = [str(t) for t in parsed.get("pii_tokens_detected", [])]
        k_anon = bool(parsed.get("k_anonymity_violation", False))
        findings = [str(f) for f in parsed.get("findings", [])]
        recommendation = str(parsed.get("recommendation", "FLAG_FOR_REVIEW")).upper()
        reason = str(parsed.get("reason", "Airlock scan completed."))

        now_utc = datetime.now(timezone.utc)
        scan_id = f"scan-{uuid.uuid4().hex[:10]}"
        new_status = "APPROVED" if recommendation == "APPROVE" else "FLAGGED" if recommendation == "FLAG_FOR_REVIEW" else "REJECTED"

        # Deduce researcher
        researcher = None
        if "dr." in file_name or "prof." in file_name:
            for part in file_name.split("_"):
                if part.startswith("dr.") or part.startswith("prof."):
                    researcher = f"{part}@{self.settings.ADMIN_DOMAIN}"
                    break

        # Persist to BigQuery ops_airlock_export_scans
        scans_table = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_airlock_export_scans"
        rows_to_insert = [
            {
                "scan_id": scan_id,
                "room_id": room_id,
                "file_name": file_name,
                "bucket_name": bucket_name,
                "file_size_bytes": file_size,
                "researcher_email": researcher,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "pii_tokens": pii_tokens,
                "k_anonymity_violation": k_anon,
                "findings": findings,
                "recommendation": recommendation,
                "reason": reason,
                "status": new_status,
                "scanned_at": now_utc.isoformat(),
                "created_at": created_iso,
            }
        ]
        try:
            self.bq_client.insert_rows_json(scans_table, rows_to_insert)
        except Exception as e:
            logger.warning("Failed inserting airlock scan to BQ: %s", e)

        return AirlockExportCandidate(
            scan_id=scan_id,
            room_id=room_id,
            file_name=file_name,
            bucket_name=bucket_name,
            file_size_bytes=file_size,
            created_at=created_iso,
            researcher_email=researcher,
            status=new_status,
            risk_score=risk_score,
            risk_level=risk_level,
            pii_tokens_detected=pii_tokens,
            k_anonymity_violation=k_anon,
            findings=findings,
            recommendation=recommendation,
            reason=reason,
            scanned_at=now_utc.isoformat(),
        )

    def take_decision(self, req: AirlockActionRequest) -> AirlockActionResponse:
        """Record administrative approval or rejection for candidate file."""
        decision_status = "APPROVED" if req.action.upper() == "APPROVE" else "REJECTED"
        scans_table = f"{self.settings.GCP_PROJECT_ID}.{self.settings.HUB_TELEMETRY_DATASET}.ops_airlock_export_scans"
        
        # Update status in BigQuery table
        update_sql = f"""
            UPDATE `{scans_table}`
            SET status = '{decision_status}'
            WHERE room_id = '{req.room_id}' AND file_name = '{req.file_name}'
        """
        try:
            self.bq_client.query(update_sql).result()
        except Exception as e:
            logger.warning("Failed updating scan status in BigQuery: %s", e)

        return AirlockActionResponse(
            room_id=req.room_id,
            file_name=req.file_name,
            action=req.action.upper(),
            status=decision_status,
            message=f"Export candidate '{req.file_name}' marked as {decision_status}.",
        )


_risk_service: Optional[GeminiRiskService] = None


def get_gemini_risk_service() -> GeminiRiskService:
    global _risk_service
    if _risk_service is None:
        _risk_service = GeminiRiskService()
    return _risk_service
