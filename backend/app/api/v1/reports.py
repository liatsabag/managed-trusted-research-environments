"""FastAPI REST controller for Standardized and Ad-Hoc Governance Reports."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse

from backend.app.models.reports import ReportGenerationResponse
from backend.app.services.reports import ReportsService, get_reports_service

logger = logging.getLogger("reports_api")
router = APIRouter()


@router.get("/list", tags=["reports"])
def list_available_reports():
    """Returns available standardized report definitions and capabilities."""
    return [
        {
            "report_type": "FLEET_INVENTORY",
            "title": "Room Fleet Inventory Report",
            "description": "Complete status, configuration, spoke project mapping, and grant budget across research rooms.",
            "endpoint": "/api/v1/reports/fleet-inventory",
            "supported_formats": ["json", "csv", "pdf"],
        },
        {
            "report_type": "COMPLIANCE_EXCEPTIONS",
            "title": "Compliance Exceptions Report",
            "description": "Flagged studies with missing, incomplete, or lapsed statutory compliance prerequisites.",
            "endpoint": "/api/v1/reports/compliance-exceptions",
            "supported_formats": ["json", "csv", "pdf"],
        },
        {
            "report_type": "APPROVAL_HORIZON",
            "title": "Approval Expirations Horizon",
            "description": "Proactive report of ethics/Helsinki certificates and DUA agreements expiring in 30/60/90 days.",
            "endpoint": "/api/v1/reports/approval-horizon",
            "supported_formats": ["json", "csv", "pdf"],
        },
        {
            "report_type": "FINOPS_BILLING",
            "title": "Cost & FinOps Resource Billing Report",
            "description": "Resource billing segmented by room, academic institution, PI/researcher, and cost drivers.",
            "endpoint": "/api/v1/reports/cost-finops",
            "supported_formats": ["json", "csv", "pdf"],
        },
        {
            "report_type": "EGRESS_AUDIT",
            "title": "Airlock Data Egress Audit Log",
            "description": "Historical forensic log of candidate file export requests, inspection outcomes, and gate decisions.",
            "endpoint": "/api/v1/reports/egress-audit",
            "supported_formats": ["json", "csv", "pdf"],
        },
    ]


@router.get("/fleet-inventory", tags=["reports"])
def get_fleet_inventory(
    format: str = Query("json", description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
):
    """Generate Room Fleet Inventory Report."""
    try:
        report = service.get_fleet_inventory_report()
        if format.lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=room_fleet_inventory.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate fleet inventory report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance-exceptions", tags=["reports"])
def get_compliance_exceptions(
    format: str = Query("json", description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
):
    """Generate Compliance Exceptions Report."""
    try:
        report = service.get_compliance_exceptions_report()
        if format.lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=compliance_exceptions.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate compliance exceptions report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approval-horizon", tags=["reports"])
def get_approval_horizon(
    format: str = Query("json", description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
):
    """Generate Approval Expirations Horizon Report."""
    try:
        report = service.get_approval_expirations_report()
        if format.lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=approval_expirations_horizon.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate approval horizon report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost-finops", tags=["reports"])
def get_cost_finops_report(
    format: str = Query("json", description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
):
    """Generate Cost & FinOps Resource Billing Report."""
    try:
        report = service.get_cost_finops_report()
        if format.lower() == "csv":
            csv_data = service.export_as_csv(report)
            return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cost_finops_report.csv"})
        return report
    except Exception as e:
        logger.error(f"Failed to generate cost FinOps report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/egress-audit", tags=["reports"])
def get_egress_audit_report(
    format: str = Query("json", description="Output format ('json' or 'csv')"),
    service: ReportsService = Depends(get_reports_service),
):
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
