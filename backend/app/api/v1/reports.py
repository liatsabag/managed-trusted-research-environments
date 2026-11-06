"""FastAPI REST controller for Standardized and Ad-Hoc Governance Reports."""

import logging
from enum import Enum
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse


class ReportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"

from backend.app.models.reports import (
    AvailableReportDefinition,
    ReportGenerationResponse,
)
from backend.app.services.reports import ReportsService, get_reports_service

logger = logging.getLogger("reports_api")
router = APIRouter()

REPORT_RESPONSES = {
    200: {
        "model": ReportGenerationResponse,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/ReportGenerationResponse"}},
            "text/csv": {"schema": {"type": "string", "format": "binary"}},
        },
        "description": "Standardized report dataset returned as a JSON envelope or downloadable CSV attachment.",
    }
}


@router.get("/list", response_model=List[AvailableReportDefinition], tags=["reports"])
def list_available_reports() -> List[AvailableReportDefinition]:
    """Returns available standardized report definitions and capabilities."""
    return [
        AvailableReportDefinition(
            report_type="FLEET_INVENTORY",
            title="Room Fleet Inventory Report",
            description="Complete status, configuration, spoke project mapping, and grant budget across research rooms.",
            endpoint="/api/v1/reports/fleet-inventory",
            supported_formats=["json", "csv"],
        ),
        AvailableReportDefinition(
            report_type="COMPLIANCE_EXCEPTIONS",
            title="Compliance Exceptions Report",
            description="Flagged studies with missing, incomplete, or lapsed statutory compliance prerequisites.",
            endpoint="/api/v1/reports/compliance-exceptions",
            supported_formats=["json", "csv"],
        ),
        AvailableReportDefinition(
            report_type="APPROVAL_HORIZON",
            title="Approval Expirations Horizon",
            description="Proactive report of ethics/Helsinki certificates and DUA agreements expiring in 30/60/90 days.",
            endpoint="/api/v1/reports/approval-horizon",
            supported_formats=["json", "csv"],
        ),
        AvailableReportDefinition(
            report_type="FINOPS_BILLING",
            title="Cost & FinOps Resource Billing Report",
            description="Resource billing segmented by room, academic institution, PI/researcher, and cost drivers.",
            endpoint="/api/v1/reports/cost-finops",
            supported_formats=["json", "csv"],
        ),
        AvailableReportDefinition(
            report_type="EGRESS_AUDIT",
            title="Airlock Data Egress Audit Log",
            description="Historical forensic log of candidate file export requests, inspection outcomes, and gate decisions.",
            endpoint="/api/v1/reports/egress-audit",
            supported_formats=["json", "csv"],
        ),
    ]


@router.get(
    "/fleet-inventory",
    response_model=None,
    responses=REPORT_RESPONSES,
    summary="Generate Room Fleet Inventory Report",
    tags=["reports"],
)
def get_fleet_inventory(
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
) -> Union[ReportGenerationResponse, Response]:
    """Generate Room Fleet Inventory Report."""
    try:
        report = service.get_fleet_inventory_report()
        if format == ReportFormat.CSV or str(format).lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=room_fleet_inventory.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate fleet inventory report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/compliance-exceptions",
    response_model=None,
    responses=REPORT_RESPONSES,
    summary="Generate Compliance Exceptions Report",
    tags=["reports"],
)
def get_compliance_exceptions(
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
) -> Union[ReportGenerationResponse, Response]:
    """Generate Compliance Exceptions Report."""
    try:
        report = service.get_compliance_exceptions_report()
        if format == ReportFormat.CSV or str(format).lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=compliance_exceptions.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate compliance exceptions report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/approval-horizon",
    response_model=None,
    responses=REPORT_RESPONSES,
    summary="Generate Approval Expirations Horizon Report",
    tags=["reports"],
)
def get_approval_horizon(
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
) -> Union[ReportGenerationResponse, Response]:
    """Generate Approval Expirations Horizon Report."""
    try:
        report = service.get_approval_expirations_report()
        if format == ReportFormat.CSV or str(format).lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=approval_expirations_horizon.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate approval horizon report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/cost-finops",
    response_model=None,
    responses=REPORT_RESPONSES,
    summary="Generate Cost & FinOps Resource Billing Report",
    tags=["reports"],
)
def get_cost_finops_report(
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
) -> Union[ReportGenerationResponse, Response]:
    """Generate Cost & FinOps Resource Billing Report."""
    try:
        report = service.get_cost_finops_report()
        if format == ReportFormat.CSV or str(format).lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cost_finops_report.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate cost FinOps report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/egress-audit",
    response_model=None,
    responses=REPORT_RESPONSES,
    summary="Generate Airlock Egress Inspection Audit Report",
    tags=["reports"],
)
def get_egress_audit_report(
    format: ReportFormat = Query(ReportFormat.JSON, description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
) -> Union[ReportGenerationResponse, Response]:
    """Generate Airlock Egress Inspection Audit Report."""
    try:
        report = service.get_egress_audit_report()
        if format.lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=egress_audit_report.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate egress audit report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
