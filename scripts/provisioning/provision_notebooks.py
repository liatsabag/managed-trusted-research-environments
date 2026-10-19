"""Jupyter / Colab Enterprise notebook provisioning module for spoke research rooms."""
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)


import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("provision_notebooks")


def load_topology(topology_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load fleet topology JSON specification."""
    if topology_path is None:
        topology_path = Path(__file__).resolve().parents[1] / "fixtures" / "fleet_topology.json"
    with open(topology_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_notebook_content(room_id: str, spoke_project: str, filename: str, title: str, local_ds: str) -> Dict[str, Any]:
    """Construct valid Jupyter Notebook JSON structure with BigQuery magics and Python analysis."""
    sample_table = get_sample_table(local_ds)
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# {title}\n",
                f"**Research Room:** `{room_id}` | **Project:** `{spoke_project}` | **Dataset:** `{local_ds}`\n",
                "\n",
                "This governed Colab Enterprise / BigQuery Studio notebook demonstrates SQL exploration, "
                "data extraction, statistical modeling, and airlock export staging within the secure boundary.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Environment Setup & Verification\n",
                "import os\n",
                "import pandas as pd\n",
                "import numpy as np\n",
                "from google.cloud import bigquery\n",
                "\n",
                f"PROJECT_ID = '{spoke_project}'\n",
                f"DATASET_ID = '{local_ds}'\n",
                "client = bigquery.Client(project=PROJECT_ID)\n",
                "print(f'Active Research Room Environment: {PROJECT_ID}')",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. BigQuery Cohort Query (Using %%bqsql Magic)\n",
                f"Querying the local spoke dataset `{local_ds}.{sample_table}` directly in BigQuery.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                f"%%bqsql --project={spoke_project}\n",
                f"SELECT * FROM `{spoke_project}.{local_ds}.{sample_table}`\n",
                "LIMIT 50",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Statistical Analysis & Feature Engineering\n",
                "Computing summary statistics and preparing candidate figures.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Simulated analytical computation\n",
                "df = pd.DataFrame({\n",
                "    'feature_index': range(1, 21),\n",
                "    'importance_score': np.random.uniform(0.1, 0.95, 20),\n",
                "    'p_value': np.random.uniform(0.001, 0.05, 20)\n",
                "})\n",
                "print('Top 5 Statistical Features:')\n",
                "print(df.head())",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. Airlock Egress Candidate Staging\n",
                "Saving aggregated model outputs to the outbound quarantine bucket for DPO review.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                f"export_bkt = 'gs://{room_id}-export'\n",
                "output_filename = 'candidate_results.csv'\n",
                "print(f'Depositing candidate egress file to {export_bkt}/{output_filename}')\n",
                "# df.to_csv(f'{export_bkt}/{output_filename}', index=False)",
            ],
        },
    ]

    return {
        "cells": cells,
        "metadata": {
            "colab": {"name": title, "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.9"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def get_sample_table(dataset_id: str) -> str:
    """Helper to return the primary table for a dataset."""
    mapping = {
        "spoke_local_oncology": "patient_cohort",
        "spoke_local_genomics": "variant_calls",
        "spoke_local_cardio": "patient_registry",
        "spoke_local_neurology": "cognitive_assessments",
    }
    return mapping.get(dataset_id, "patient_cohort")


def provision_notebooks(
    topology: Optional[Dict[str, Any]] = None,
    staging_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Generate and deploy the 2 domain notebooks per spoke room to GCS inbound buckets and Colab Enterprise."""
    if topology is None:
        topology = load_topology()
    if staging_dir is None:
        staging_dir = Path(__file__).resolve().parent.parent / "staging" / "notebooks"

    staging_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Any] = {"notebooks_created": 0, "notebooks_uploaded": 0, "room_notebooks": {}}

    storage_mod = None
    if not dry_run:
        from google.cloud import storage as storage_mod

    for room in topology.get("research_rooms", []):
        room_id = room["room_id"]
        spoke_p = room.get("spoke_project_id", "gcp-rr-hub-core")
        inbound_bkt = room["inbound_bucket"].replace("gs://", "")
        local_ds = room.get("local_dataset", {}).get("dataset_id", f"{room_id}_data")
        room_dir = staging_dir / room_id
        room_dir.mkdir(parents=True, exist_ok=True)
        results["room_notebooks"][room_id] = []

        spoke_storage = storage_mod.Client(project=spoke_p) if storage_mod else None
        bucket = spoke_storage.bucket(inbound_bkt) if spoke_storage else None

        for nb_def in room.get("notebooks", []):
            fname = nb_def["filename"]
            title = nb_def["title"]
            nb_content = build_notebook_content(room_id, spoke_p, fname, title, local_ds)

            nb_path = room_dir / fname
            nb_json_str = json.dumps(nb_content, indent=2)
            with open(nb_path, "w", encoding="utf-8") as f:
                f.write(nb_json_str)

            results["notebooks_created"] += 1

            # Upload to gs://rr-[spoke]-inbound/notebooks/[filename]
            gcs_dest_path = f"notebooks/{fname}"
            if bucket:
                try:
                    blob = bucket.blob(gcs_dest_path)
                    blob.upload_from_string(nb_json_str, content_type="application/x-ipynb+json")
                    results["notebooks_uploaded"] += 1
                    logger.info("Uploaded Notebook to live GCS: gs://%s/%s (project %s)", inbound_bkt, gcs_dest_path, spoke_p)
                except Exception as e:
                    logger.error("FATAL: Failed to upload notebook to gs://%s/%s: %s", inbound_bkt, gcs_dest_path, e)
                    raise RuntimeError(f"Notebook upload failed for gs://{inbound_bkt}/{gcs_dest_path}: {e}") from e

            results["room_notebooks"][room_id].append({
                "filename": fname,
                "title": title,
                "gcs_uri": f"gs://{inbound_bkt}/{gcs_dest_path}",
                "local_path": str(nb_path),
            })
            logger.info("[%s] Provisioned Notebook: %s ('%s')", room_id, fname, title)

    logger.info("Notebook provisioning complete. Total notebooks: %d, Uploaded: %d", results["notebooks_created"], results["notebooks_uploaded"])
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    res = provision_notebooks()
    print(json.dumps(res, indent=2))
