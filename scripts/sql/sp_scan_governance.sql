CREATE OR REPLACE PROCEDURE `gcp-rr-hub-core.hub_telemetry.sp_scan_governance`(target_type STRING)
BEGIN
  DECLARE norm_target_type STRING;
  SET norm_target_type = UPPER(TRIM(target_type));

  -- Step 1: Execute BigQuery AI Remote Model inference over Object Table gs://gcp-rr-hub-approvals/*
  CREATE TEMP TABLE temp_ai_extracted AS
  WITH raw_inference AS (
    SELECT
      uri,
      SPLIT(REGEXP_EXTRACT(uri, r'gs://gcp-rr-hub-approvals/([^/]+)/'), '/')[OFFSET(0)] AS room_id,
      REGEXP_EXTRACT(ml_generate_text_llm_result, r'\{[\s\S]*\}') AS clean_json
    FROM ML.GENERATE_TEXT(
      MODEL `gcp-rr-hub-core.hub_telemetry.gemini_flash_model`,
      TABLE `gcp-rr-hub-core.hub_telemetry.obj_approval_documents`,
      STRUCT(
        0.0 AS temperature,
        500 AS max_output_tokens,
        TRUE AS flatten_json_output,
        'You are analyzing a health data platform regulatory approval document. Extract the metadata from the document text. Output ONLY a valid JSON object without markdown fences, with exact keys: "item_type" (must be exactly one of: Research_Protocol, Helsinki_IRB, Data_Transfer, Extraction_Protocol, DUA), "item_name" (string description), "approval_date" (YYYY-MM-DD), "expiration_date" (YYYY-MM-DD), "approver_name" (approving official name/title), "status" ("APPROVED" or "EXPIRED").' AS prompt
      )
    )
  )
  SELECT
    room_id,
    JSON_VALUE(clean_json, '$.item_type') AS item_type,
    COALESCE(JSON_VALUE(clean_json, '$.item_name'), CONCAT(room_id, ' ', JSON_VALUE(clean_json, '$.item_type'))) AS item_name,
    SAFE.PARSE_DATE('%Y-%m-%d', JSON_VALUE(clean_json, '$.approval_date')) AS approval_date,
    SAFE.PARSE_DATE('%Y-%m-%d', JSON_VALUE(clean_json, '$.expiration_date')) AS expiration_date,
    JSON_VALUE(clean_json, '$.approver_name') AS approver_name,
    COALESCE(JSON_VALUE(clean_json, '$.status'), 'APPROVED') AS parsed_status,
    uri AS document_uri
  FROM raw_inference
  WHERE JSON_VALUE(clean_json, '$.item_type') IS NOT NULL;

  -- Step 2: Define the 5 statutory prerequisite types
  CREATE TEMP TABLE temp_required_types AS
  SELECT 'Research_Protocol' AS item_type UNION ALL
  SELECT 'Helsinki_IRB' UNION ALL
  SELECT 'Data_Transfer' UNION ALL
  SELECT 'Extraction_Protocol' UNION ALL
  SELECT 'DUA';

  -- Step 3: Handle PROVISIONED rooms
  IF norm_target_type = 'PROVISIONED' THEN
    CREATE TEMP TABLE temp_target_rooms AS
    SELECT DISTINCT room_id FROM `gcp-rr-hub-core.hub_telemetry.dim_research_rooms`;

    MERGE `gcp-rr-hub-core.hub_telemetry.ops_regulatory_checklist` T
    USING (
      SELECT
        CONCAT(r.room_id, '_', req.item_type) AS item_id,
        r.room_id,
        'PROVISIONED' AS room_type,
        req.item_type,
        COALESCE(doc.item_name, CONCAT(r.room_id, ' ', req.item_type)) AS item_name,
        CASE
          WHEN doc.document_uri IS NULL THEN 'MISSING'
          WHEN doc.expiration_date IS NOT NULL AND doc.expiration_date < CURRENT_DATE() THEN 'EXPIRED'
          ELSE 'APPROVED'
        END AS status,
        doc.approval_date,
        doc.expiration_date,
        doc.approver_name,
        doc.document_uri,
        CASE
          WHEN doc.document_uri IS NULL THEN 'Prerequisite document missing from approvals repository'
          WHEN doc.expiration_date IS NOT NULL AND doc.expiration_date < CURRENT_DATE() THEN 'Approval expired'
          ELSE 'Verified and active by BigQuery AI'
        END AS comments,
        CURRENT_TIMESTAMP() AS last_updated
      FROM temp_target_rooms r
      CROSS JOIN temp_required_types req
      LEFT JOIN temp_ai_extracted doc
        ON r.room_id = doc.room_id AND req.item_type = doc.item_type
    ) S
    ON T.room_id = S.room_id AND T.item_type = S.item_type AND T.room_type = S.room_type
    WHEN MATCHED THEN
      UPDATE SET
        item_name = S.item_name,
        status = S.status,
        approval_date = S.approval_date,
        expiration_date = S.expiration_date,
        approver_name = S.approver_name,
        document_uri = S.document_uri,
        comments = S.comments,
        last_updated = S.last_updated
    WHEN NOT MATCHED THEN
      INSERT (item_id, room_id, room_type, item_type, item_name, status, approval_date, expiration_date, approver_name, document_uri, comments, last_updated)
      VALUES (S.item_id, S.room_id, S.room_type, S.item_type, S.item_name, S.status, S.approval_date, S.expiration_date, S.approver_name, S.document_uri, S.comments, S.last_updated);

  -- Step 4: Handle REQUEST rooms
  ELSEIF norm_target_type = 'REQUEST' THEN
    CREATE TEMP TABLE temp_target_requests AS
    SELECT DISTINCT request_id, proposed_room_id FROM `gcp-rr-hub-core.hub_telemetry.ops_room_requests`;

    MERGE `gcp-rr-hub-core.hub_telemetry.ops_regulatory_checklist` T
    USING (
      SELECT
        CONCAT(r.proposed_room_id, '_', req.item_type) AS item_id,
        r.proposed_room_id AS room_id,
        'REQUEST' AS room_type,
        req.item_type,
        COALESCE(doc.item_name, CONCAT(r.proposed_room_id, ' ', req.item_type)) AS item_name,
        CASE
          WHEN doc.document_uri IS NULL THEN 'MISSING'
          WHEN doc.expiration_date IS NOT NULL AND doc.expiration_date < CURRENT_DATE() THEN 'EXPIRED'
          ELSE 'APPROVED'
        END AS status,
        doc.approval_date,
        doc.expiration_date,
        doc.approver_name,
        doc.document_uri,
        CASE
          WHEN doc.document_uri IS NULL THEN 'Prerequisite document missing from approvals repository'
          WHEN doc.expiration_date IS NOT NULL AND doc.expiration_date < CURRENT_DATE() THEN 'Approval expired'
          ELSE 'Verified and active by BigQuery AI'
        END AS comments,
        CURRENT_TIMESTAMP() AS last_updated
      FROM temp_target_requests r
      CROSS JOIN temp_required_types req
      LEFT JOIN temp_ai_extracted doc
        ON r.proposed_room_id = doc.room_id AND req.item_type = doc.item_type
    ) S
    ON T.room_id = S.room_id AND T.item_type = S.item_type AND T.room_type = S.room_type
    WHEN MATCHED THEN
      UPDATE SET
        item_name = S.item_name,
        status = S.status,
        approval_date = S.approval_date,
        expiration_date = S.expiration_date,
        approver_name = S.approver_name,
        document_uri = S.document_uri,
        comments = S.comments,
        last_updated = S.last_updated
    WHEN NOT MATCHED THEN
      INSERT (item_id, room_id, room_type, item_type, item_name, status, approval_date, expiration_date, approver_name, document_uri, comments, last_updated)
      VALUES (S.item_id, S.room_id, S.room_type, S.item_type, S.item_name, S.status, S.approval_date, S.expiration_date, S.approver_name, S.document_uri, S.comments, S.last_updated);

    -- Step 5: Update gate decisions on ops_room_requests
    UPDATE `gcp-rr-hub-core.hub_telemetry.ops_room_requests` req
    SET
      gate_decision = eval.gate_decision,
      missing_items = eval.missing_items,
      expired_items = eval.expired_items,
      warning_items = eval.warning_items,
      summary_reason = eval.summary_reason,
      scanned_at = CURRENT_TIMESTAMP()
    FROM (
      SELECT
        c.room_id AS proposed_room_id,
        CASE
          WHEN COUNTIF(c.status != 'APPROVED') = 0 AND COUNT(c.item_type) = 5 THEN 'GATE_PASSED'
          ELSE 'GATE_BLOCKED'
        END AS gate_decision,
        STRING_AGG(CASE WHEN c.status = 'MISSING' THEN c.item_type END, ', ') AS missing_items,
        STRING_AGG(CASE WHEN c.status = 'EXPIRED' THEN c.item_type END, ', ') AS expired_items,
        STRING_AGG(CASE WHEN c.expiration_date IS NOT NULL AND DATE_DIFF(c.expiration_date, CURRENT_DATE(), DAY) BETWEEN 0 AND 30 THEN c.item_type END, ', ') AS warning_items,
        CASE
          WHEN COUNTIF(c.status != 'APPROVED') = 0 AND COUNT(c.item_type) = 5 THEN 'All 5 regulatory prerequisites verified and active'
          ELSE CONCAT('Blocked by regulatory gate: ', COALESCE(STRING_AGG(CASE WHEN c.status != 'APPROVED' THEN CONCAT(c.item_type, ' (', c.status, ')') END, ', '), 'Missing items'))
        END AS summary_reason
      FROM `gcp-rr-hub-core.hub_telemetry.ops_regulatory_checklist` c
      WHERE c.room_type = 'REQUEST'
      GROUP BY c.room_id
    ) eval
    WHERE req.proposed_room_id = eval.proposed_room_id;
  END IF;
END;
