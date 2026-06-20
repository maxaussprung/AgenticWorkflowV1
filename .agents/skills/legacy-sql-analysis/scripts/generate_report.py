#!/usr/bin/env python3
"""Generate a searchable legacy SQL analysis report.

The report intentionally treats the SQL repository as a read-only legacy reference. It inventories
SQL Server database project files, extracts official client PDF text, and cross-references SQL
objects with official document topics. It does not execute SQL.
"""

# ===== GENERIC TEMPLATE NOTE =====
# This script was developed for a specific project and contains domain-specific
# concept mappings, terminology, and analysis heuristics. To use it for a new
# project:
#   1. Update the PROJECT CONFIGURATION section (constants near top of file)
#   2. Replace the concept_mappings spec_terms with your domain terminology
#   3. Update the PDF_SOURCES to point to your specification documents
#   4. Adjust the C# namespace patterns (BACKEND_* constants)
# ==================================

from __future__ import annotations

import html
import json
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "pypdf is required. Run with the bundled workspace Python from load_workspace_dependencies."
    ) from exc


def find_repo_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "AGENTS.md").exists() and (path / "legacy-sql").exists():
            return path
    raise SystemExit("Could not locate repository root from skill script path.")


ROOT = find_repo_root(Path(__file__).resolve())

# ===== PROJECT CONFIGURATION =====
# Replace these placeholders with the actual project-specific names before use.
LEGACY_DB_NAME = "{LEGACY-DB-NAME}"  # e.g. "Example_Database"

SQL_ROOT = ROOT / "legacy-sql" / LEGACY_DB_NAME
SQLPROJ = SQL_ROOT / f"{LEGACY_DB_NAME}.sqlproj"
REPORT_DIR = ROOT / "reports" / "evaluations" / "legacy-sql"
REPORT = REPORT_DIR / "legacy-sql-analysis.html"
DATA_JSON = REPORT_DIR / "legacy-sql-analysis-data.json"
MKDOCS_COVERAGE_PAGE = ROOT / "docs" / "requirements" / "legacy-coverage-landscape.md"  # {PLACEHOLDER} rename to match your project
CSHARP_ROOT = ROOT / "csharp"
CSHARP_BACKEND_ROOT = ROOT / "csharp" / "src" / "backend"
CSHARP_INFRA_ROOT = CSHARP_BACKEND_ROOT / "{BACKEND-INFRASTRUCTURE-PROJECT}"
CSHARP_DATA_ROOT = CSHARP_INFRA_ROOT / "Data"
CSHARP_CONFIGURATION_ROOT = CSHARP_DATA_ROOT / "Configuration"
CSHARP_MIGRATIONS_ROOT = CSHARP_INFRA_ROOT / "Migrations"
CSHARP_DOMAIN_ROOT = CSHARP_BACKEND_ROOT / "{BACKEND-DOMAIN-PROJECT}"
LEGACY_CODE_ROOT = ROOT / "to_be_migrated_repo" / "{LEGACY-CODEBASE-DIR}"
LEGACY_CODE_SUFFIXES = {".ext1", ".ext2", ".ext3"}  # EXAMPLE legacy source file extensions — adjust per project
REQUIREMENTS_ROOT = ROOT / "docs" / "requirements" / "requirements"
FEATURES_ROOT = ROOT / "docs" / "requirements" / "features"

PDF_SOURCES = [
    ROOT / "docs" / "requirements" / "source-import" / "{SPEC-DOCUMENT-1}.pdf",
    ROOT
    / "docs"
    / "requirements"
    / "source-import"
    / "{SPEC-DOCUMENT-2}.pdf",
]

SPEC_DOCUMENT_1_PREFIX = "{SPEC-DOCUMENT-1-PREFIX}"  # e.g. "TRD §"
SPEC_DOCUMENT_2_PREFIX = "{SPEC-DOCUMENT-2-PREFIX}"  # e.g. "Print Spec §"

# EXAMPLE schema set — adjust per project. "app" stands in for the project's
# primary application schema; keep dbo/sys/INFORMATION_SCHEMA as standard schemas.
KNOWN_SCHEMAS = {"app", "dbo", "sys", "INFORMATION_SCHEMA"}

PRODUCT_CODE_TO_IDS = {
    "NID": {"PRODUCT-001"},
    "NAD": {"PRODUCT-002"},
    "PFU": {"PRODUCT-003"},
    "PV": {"PRODUCT-004"},
    "ASG": {"PRODUCT-006"},
    "PF": {"PRODUCT-007"},
    "PUM": {"PRODUCT-008"},
    "REC": {"PRODUCT-009"},
    "SAM": {"PRODUCT-010"},
    "EEZ": {"PRODUCT-011"},
}

PRODUCTS = [
    {
        "code": "NID",
        "name": "Example Domestic Order",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["NID", "Example Domestic Order", "APP_SEQA", "DomainConceptA", "ExampleForwarding", "Formularnr"],
    },
    {
        "code": "NAD",
        "name": "Example Foreign Order",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["NAD", "Example Foreign Order", "APP_SEQB", "DomainConceptB", "Ausland", "LKZ", "Land"],
    },
    {
        "code": "PFU",
        "name": "Example Vacation Box",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["PFU", "Example Vacation Box", "VacationBox", "ExampleVacationBox", "vacationbox", "Postfach"],
    },
    {
        "code": "PV",
        "name": "Postvollmacht",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["PV", "Postvollmacht", "PostalAuthorization", "Vollmacht", "neuerempfaenger", "hatNachPersonen"],
    },
    {
        "code": "OA",
        "name": "Ortsabwesenheit",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["OA", "Ortsabwesenheit", "LocalAbsence", "APP_SEQC"],
    },
    {
        "code": "ASG",
        "name": "Abstellgenehmigung",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, section 8.2",
        "terms": ["ASG", "Abstellgenehmigung", "DropOffAuthorization", "Abstellort", "TDropOffLocation", "ASG_Zwischentabelle"],
    },
    {
        "code": "PF",
        "name": "Postfächer",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, page 10, sections 8.2 and 9.1",
        "terms": ["Postfach", "Postfächer", "PostOfficeBox", "Postfach Plus", "Postfach Offen", "APP_SEQD", "TPostfach"],
    },
    {
        "code": "REC",
        "name": "Sachwalter / Erwachsenenvertretung / Masseverwalter / Rechtsanwaltschaft",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, pages 10-11, sections 8.2 and 9.2",
        "terms": ["REC", "Sachwalter", "Erwachsenenvertretung", "Masseverwalter", "Rechtsanw", "LegalRepresentation", "Recht_Typ"],
    },
    {
        "code": "PUM",
        "name": "Paketumleitung Dauerhaft",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, pages 10-12, sections 8.2 and 10",
        "terms": ["PUM", "Paketumleitung", "PermanentRedirectionParcels", "SSOKundennr", "SSOIdBenutzer", "Level 90"],
    },
    {
        "code": "EEZ",
        "name": "Einspruch Ersatzzustellung",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, pages 9-10, sections 8.1 and 8.2",
        "terms": ["EEZ", "Einspruch Ersatzzustellung", "ObjectionToReplacementDelivery", "Ersatzzustellung"],
    },
    {
        "code": "SAM",
        "name": "BatchOrder-A",
        "pdf_source": "{SPEC-DOCUMENT-1}.pdf, pages 10 and 58, sections 8.2 and 13",
        "terms": ["SAM", "BatchOrder", "Collective Example", "CollectiveDomainConceptA", "TBatchOrder", "CSV"],
    },
]

CSHARP_COMPARISON_TOPICS = [
    {
        "capability": "Directive/product catalog",
        "terms": ["DirectiveType", "GetDirectives", "Example Domestic Order", "Paketumleitung Dauerhaft", "Postvollmacht"],
        "expected": "Product and subtype list from specsection 8.2.",
    },
    {
        "capability": "Directive settings, durations, and incompatibilities",
        "terms": ["DirectiveSettings", "Incompatibilities", "Duration.From", "allowedFrom", "maxNumberOfCustomers"],
        "expected": "Validity windows, customer limits, product settings, and incompatibility rules.",
    },
    {
        "capability": "Directive order persistence model",
        "terms": ["DirectiveOrder", "CreateDirectiveOrder", "DirectiveOrderRepository", "DirectivesDbContext"],
        "expected": "C# aggregate/repository/API support for creating and storing directive orders.",
    },
    {
        "capability": "Formula number generation",
        "terms": ["SetFormulaNumber", "FormulaCodes", "FormulaNumber", "DirectiveFormulaDictionary"],
        "expected": "Formularnummer generation logic.",
    },
    {
        "capability": "Customer, company, and order owner data",
        "terms": ["OrderOwner", "Customer", "Company", "ContactDetails", "OrderOwnerPerson", "OrderOwnerCompany"],
        "expected": "Customer/company/person data captured for a directive order.",
    },
    {
        "capability": "Customer identification / SSO evidence",
        "terms": ["CustomerIdentification", "SSOCustomerNumber", "ExampleCrm", "ExampleCrm", "Level"],
        "expected": "PUM/online-customer identity support and SSO/ExampleCrm data.",
    },
    {
        "capability": "Origin/destination routing and address data",
        "terms": ["OrderRouting", "OrderRoutingAddress", "OrderRoutingPostOfficeBox", "Address", "Pac", "{EXTERNAL-API}"],
        "expected": "Old/new address, PAC, postbox, and routing structures.",
    },
    {
        "capability": "ASG drop-off behavior",
        "terms": ["DropOffAuthorization", "DropOffPermissionEvent", "ASGType", "DropOffLocation"],
        "expected": "Abstellgenehmigung-specific data/event mapping.",
    },
    {
        "capability": "Search/indexing",
        "terms": ["Typesense", "IndexDirectiveOrders", "DirectiveOrderFilter", "GetDirectiveOrderById"],
        "expected": "Search/indexing support replacing or complementing legacy SQL search/reporting.",
    },
    {
        "capability": "Permissions and roles",
        "terms": ["Permission", "Role", "Authorization", "CanCreateDirectives", "CanRequestDirectiveLabels"],
        "expected": "Application-level authorization model.",
    },
    {
        "capability": "Payment/billing status",
        "terms": ["DirectivePaymentStatus", "PaymentStatus", "GetDirectivesCountByPayment"],
        "expected": "Payment state evidence; not necessarily full legacy Verrechnung/Inkasso behavior.",
    },
    {
        "capability": "Print/label datafile generation",
        "terms": ["Etikett", "Kuvert", "Druck", "Label", "CanRequestDirectiveLabels"],
        "expected": "Druck/Kuvertierung interface or explicit label request behavior.",
    },
    {
        "capability": "Legacy search/fuzzy DB behavior",
        "terms": ["{EXTERNAL-SEARCH-API}", "fuzzy", "clr_{external}_person", "{db_search_proc}"],
        "expected": "Direct equivalent of legacy search/fuzzy SQL behavior.",
    },
]

# ===== PROJECT-SPECIFIC CONFIGURATION =====
# Replace the spec_terms lists below with domain-specific terminology from YOUR project.
# These terms are used to match spec document sections against SQL objects and C# code.
# The concept labels (e.g. "Search", "Address") should reflect your project's domain concepts.
# ==========================================
SPEC_COVERAGE_OVERVIEW_CONCEPTS = [
    {
        "area": "Produktkatalog und Formulararten",
        "product": "Alle spec products",
        "spec_terms": ["example-term-1", "example-term-2", "example-term-3"],
        "legacy_terms": ["TOrderType", "TShipmentOrder", "TShipmentType", "AuftragTyp_ID", "Code"],
        "csharp_terms": ["DirectiveType", "GetDirectives", "Directives", "DirectiveSettings"],
        "coverage": "Full",
        "confidence": "high",
        "legacy_meaning": "Legacy SQL stores product/order type catalogs and shipment type assignments.",
        "coverage_reason": "C# contains DirectiveType, initialized Directives, Directive settings, and EF tables for catalog data.",
        "gap": "Full coverage here means the catalog surface is present; it does not prove that every product workflow is fully implemented.",
    },
    {
        "area": "Auftragskopf und zentraler Lebenszyklus",
        "product": "Alle Auftragsprodukte",
        "spec_terms": ["example-term-A", "example-term-B"],
        "legacy_terms": ["TOrderHead", "Formularnr", "GueltigAb", "GueltigBis", "P_STORE_ORDER_XML"],
        "csharp_terms": ["DirectiveOrder", "Orders", "FormulaNumber", "ValidityExampleRefod", "DirectiveOrderConfiguration"],
        "coverage": "Partial",
        "confidence": "high",
        "legacy_meaning": "Legacy SQL bundles orders in the head table storing validity, form number, type, contact, print, cancellation, and SSO fields.",
        "coverage_reason": "C# has the active DirectiveOrder aggregate and the Orders table for form number, validity, type, payment status, routing, and JSON order data.",
        "gap": "Legacy cancellation flags, print markers, audit references, and several historical fields are not present one-to-one as C# columns.",
    },
    {
        "area": "Gültigkeit, Dauer und Produktregeln",
        "product": "Alle Auftragsprodukte",
        "spec_terms": ["example-term-C", "example-term-D", "example-term-E"],
        "legacy_terms": ["GueltigAb", "GueltigBis", "Gueltig_Typ", "FilterByCurrentOrders", "report_validOrders"],
        "csharp_terms": ["DirectiveSettings", "ValidityExampleRefod", "AllowedFrom", "MaxTo", "Duration"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL stores date fields and implements current/valid/report filters in functions.",
        "coverage_reason": "C# stores validity and product settings; parity with all SQL function cases for current, expired, or cancelled is not confirmed.",
        "gap": "Date and status transitions must be validated against confirmed spec rules before this area is considered functionally complete.",
    },
    {
        "area": "Ursprung, Ziel, Adresse und Routing",
        "product": "NID, NAD, PFU, PV, OA, PUM, SAM",
        "spec_terms": ["example-term-F", "example-term-G", "example-term-H"],
        "legacy_terms": ["TDestination", "GetAnschrift", "FilterByTStandort", "RLocation", "PAC"],
        "csharp_terms": ["OrderRouting", "OrderRoutingAddress", "OrderRoutingPostOfficeBox", "Address", "Pac", "ExampleRef"],
        "coverage": "Partial",
        "confidence": "high",
        "legacy_meaning": "Legacy SQL combines destination address rows, address formatting functions, PAC data, and provider location references.",
        "coverage_reason": "C# has routing entities and an Address aggregate with PAC, postal code, city, street, and house number fields.",
        "gap": "Provider location, post-restante, and the legacy address formatting behavior are not fully mapped as direct C# tables.",
    },
    {
        "area": "Personen, Empfänger, Kunden und Firmen",
        "product": "NID, NAD, PV, REC, SAM",
        "spec_terms": ["example-term-I", "example-term-J", "example-term-K"],
        "legacy_terms": ["TOrderDetail", "FK_Person", "NeuerEmpfaenger", "{ExternalPersonEntity}", "clr_{external}_person"],
        "csharp_terms": ["Customer", "Company", "OrderOwner", "OrderOwnerPerson", "OrderOwnerCompany", "CustomerIdentification"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL uses detail rows and external search API/CLR wrappers to link orders with person and recipient data.",
        "coverage_reason": "C# has entities for customers, companies, order owners, and identification; parity with the external person provider is not confirmed.",
        "gap": "Search API behavior and person lookup semantics must be confirmed at integration level.",
    },
    {
        "area": "Kundenidentifikation, SSO und ExampleCrm",
        "product": "PUM und Online-/Kundenflüsse",
        "spec_terms": ["example-term-L", "example-term-M"],
        "legacy_terms": ["TSsoIdentification", "TSsoDeletion", "SSOKundennr", "TRegistrationFeedback"],
        "csharp_terms": ["CustomerIdentification", "SSOCustomerNumber", "ExampleCrm", "ExampleCrm"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL stores SSO identification, SSO deletion, and registration feedback in dedicated tables.",
        "coverage_reason": "C# has customer identification entities and ExampleCrm/SSO integration fields, but no dedicated SSO persistence tables in the legacy style.",
        "gap": "Clarify whether SSO lifecycle and audit storage belong to the C# extension or are owned by external systems.",
    },
    {
        "area": "Sendungsarten und Sendungsauswahl",
        "product": "NID, NAD, PV, PFU, ASG, SAM",
        "spec_terms": ["example-term-N", "example-term-O"],
        "legacy_terms": ["TShipmentType", "TShipmentOrder", "TShipmentTypeAssignment", "SendungTyp"],
        "csharp_terms": ["ShipmentType", "ShipmentTypeGroup", "ShipmentTypes", "ShipmentTypeGroups"],
        "coverage": "Full",
        "confidence": "high",
        "legacy_meaning": "Legacy SQL stores shipment type catalogs and product assignments.",
        "coverage_reason": "C# has initialized shipment type groups and shipment types held by the Directive aggregate.",
        "gap": "Order-specific shipment selections should still be verified per product workflow.",
    },
    {
        "area": "Postfachprodukte und Postfachverwaltung",
        "product": "PF, PFU",
        "spec_terms": ["example-term-P", "example-term-Q", "example-term-R"],
        "legacy_terms": ["TBoxMasterData", "TBoxLocation", "TBoxStatus", "FilterByTStandort"],
        "csharp_terms": ["PostOfficeBox", "ExampleVacationBox", "OrderRoutingPostOfficeBox", "Postfach"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL has dedicated tables for post-office box master data, locations, and statuses.",
        "coverage_reason": "C# has post-office box directive types and a routing marker for post-box destinations.",
        "gap": "A dedicated management model for post-office box master data, locations, and statuses is not present as an active EF table.",
    },
    {
        "area": "ASG-Abstellgenehmigung",
        "product": "ASG",
        "spec_terms": ["example-term-S", "example-term-T"],
        "legacy_terms": ["TDropOffLocation", "Abstellort", "ASG_Zwischentabelle"],
        "csharp_terms": ["DropOffAuthorization", "DropOffLocation", "asg-drop-off-location", "DropOffAuthorizationOrderData"],
        "coverage": "Partial",
        "confidence": "high",
        "legacy_meaning": "Legacy SQL stores drop-off locations and ASG-specific values.",
        "coverage_reason": "C# stores ASG drop-off location lookup data and selected drop-off fields in polymorphic order data.",
        "gap": "This is not a one-to-one table clone; product workflow and event behavior still need validation at requirements level.",
    },
    {
        "area": "BatchOrder und Massenimport",
        "product": "SAM",
        "spec_terms": ["example-term-U", "example-term-V"],
        "legacy_terms": ["TBatchOrder", "Split2XML", "P_STORE_ORDER_XML", "Sammel"],
        "csharp_terms": ["CollectiveDomainConceptA", "Sammel", "DirectiveType"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL has a staging/import table and a transformation/save path for bulk order rows.",
        "coverage_reason": "C# has the SAM / CollectiveDomainConceptA product type, but no dedicated import/staging EF table.",
        "gap": "Bulk import processing, duplicate checking, and row-level validation are open implementation questions.",
    },
    {
        "area": "Verrechnung, Inkasso und Zahlungsstatus",
        "product": "PF, PFU und zahlungspflichtige Produkte",
        "spec_terms": ["example-term-W", "example-term-X"],
        "legacy_terms": ["TBilling", "TBillingStatus", "TBilling_History", "Inkasso"],
        "csharp_terms": ["DirectivePaymentStatus", "PaymentStatus", "GetDirectiveOrderCount"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL stores detailed billing/collection rows, statuses, history, and amounts.",
        "coverage_reason": "C# stores a coarse payment status on the order in Orders.",
        "gap": "Detailed billing lifecycle, collection metadata, amounts, and history are not covered by equivalent C# tables.",
    },
    {
        "area": "Druck, Etiketten und Dateischnittstelle",
        "product": "Druckrelevante Produkte",
        "spec_terms": ["example-term-Y", "example-term-Z"],
        "legacy_terms": ["LabelPrint", "FilterByOrderLabels", "GetLabelCount", "GetPrintDate", "GetItemsPerEnvelope"],
        "csharp_terms": ["CanRequestDirectiveLabels", "Label", "Etikett", "Druck"],
        "coverage": "Partial",
        "confidence": "low",
        "legacy_meaning": "Legacy SQL contains print selection and print helper functions for label and envelope output.",
        "coverage_reason": "C# shows hints of label-request and permission surfaces; the legacy print file contract is not implemented as an obvious C# equivalent.",
        "gap": "Print/envelope interface should be reviewed as a separate interface contract before parity is assumed or implemented.",
    },
    {
        "area": "Suche, Reports und Historienansichten",
        "product": "Operative Anwender",
        "spec_terms": ["example-term-AA", "example-term-BB", "example-term-CC"],
        "legacy_terms": ["OrderSearch", "report_", "Export", "Historie", "TLog"],
        "csharp_terms": ["Typesense", "DirectiveOrderFilter", "GetDirectiveOrderById", "IndexDirectiveOrders"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL contains search functions, reports, exports, history views, and log tables.",
        "coverage_reason": "C# shows search/indexing evidence via Typesense and Directive-Order filters.",
        "gap": "Concrete legacy reports, exports, and history/audit views are not fully evidenced.",
    },
    {
        "area": "Berechtigungen und rollenbasierter Zugriff",
        "product": "Anwendungsbetrieb",
        "spec_terms": ["example-term-DD", "example-term-EE"],
        "legacy_terms": ["TPermission", "GRANT", "Permissions", "RoleMemberships"],
        "csharp_terms": ["Permission", "Role", "Authorization", "CanCreateDirectives", "CanRequestDirectiveLabels"],
        "coverage": "Partial",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL contains permission tables as well as database grants and roles.",
        "coverage_reason": "C# has an auth schema and a roles/permissions model, but is structurally different from the legacy flags.",
        "gap": "Legacy operational roles must be mapped to the C# authorization model with product-owner confirmation.",
    },
    {
        "area": "Storno, Löschung und Audit-Trail",
        "product": "Alle stornierbaren Produkte",
        "spec_terms": ["example-term-FF", "example-term-GG", "example-term-HH"],
        "legacy_terms": ["deleteAuftrag", "deleteAuftragFuzzy", "WriteLog", "TLog", "StornoAm", "StornoGrund"],
        "csharp_terms": ["Cancel", "Cancellation", "Revocation", "Storno", "TLog"],
        "coverage": "Not present",
        "confidence": "medium",
        "legacy_meaning": "Legacy SQL contains cancellation/deletion procedures, cancellation columns, and audit log writes.",
        "coverage_reason": "The static scan found no clear active C# equivalent for cancellation/audit persistence.",
        "gap": "This area needs explicit requirements and implementation design before legacy behavior assumptions are removed or changed.",
    },
]

SPEC_COVERAGE_REQUIREMENT_RULES = {
    "Produktkatalog und Formulararten": {
        "prefixes": ["REQ-START-", "REQ-TYP"],
        "terms": ["Produkttyp", "product type", "Vorausverfügungstyp", "Unterauswahl", "product tile"],
    },
    "Auftragskopf und zentraler Lebenszyklus": {
        "ids": ["REQ-ERF-028", "REQ-ERF-029", "REQ-DACT-001", "REQ-DTRF-001", "REQ-DTRF-002", "REQ-IDM-001"],
        "terms": ["Formularnummer", "save the directive", "directive detail", "scanned ID data"],
    },
    "Gültigkeit, Dauer und Produktregeln": {
        "terms": ["Gültigkeit", "Gültig", "validity", "duration", "Widerruf", "max validity"],
    },
    "Ursprung, Ziel, Adresse und Routing": {
        "prefixes": ["REQ-FUZZY-", "REQ-SITE-"],
        "terms": ["Adresse", "address", "Postlagernd", "PAC", "PLZ", "Routing", "Standort", "Postfachanschrift"],
    },
    "Personen, Empfänger, Kunden und Firmen": {
        "terms": ["Personendaten", "person", "Empfänger", "recipient", "customer", "company", "Mitbewohner", "Auftraggeber"],
    },
    "Kundenidentifikation, SSO und ExampleCrm": {
        "terms": ["SSO", "ExampleCrm", "Online Kundensuche", "Level-90", "customer lookup", "Kundennummer"],
    },
    "Sendungsarten und Sendungsauswahl": {
        "terms": ["Sendungsarten", "shipment types", "mail-piece type"],
    },
    "Postfachprodukte und Postfachverwaltung": {
        "prefixes": ["REQ-PF-", "REQ-PFMD-", "REQ-TYPPF-"],
        "terms": ["Postfach", "Schließfach", "P.O. Box", "PF-Stammdaten"],
    },
    "ASG-Abstellgenehmigung": {
        "prefixes": ["REQ-ASG-"],
        "terms": ["ASG", "Abstell", "Drop-off"],
    },
    "BatchOrder und Massenimport": {
        "prefixes": ["REQ-SAM-"],
        "terms": ["SAM", "BatchOrder", "CSV", "batch", "Massen"],
    },
    "Verrechnung, Inkasso und Zahlungsstatus": {
        "prefixes": ["REQ-COLL-"],
        "terms": ["Inkasso", "Verrechnung", "Debitor", "payment", "Zahlung", "unpaid"],
    },
    "Druck, Etiketten und Dateischnittstelle": {
        "prefixes": ["REQ-PRT-"],
        "terms": ["Etiketten", "Label", "Druck", "print", "envelope", "Kuvert"],
    },
    "Suche, Reports und Historienansichten": {
        "prefixes": ["REQ-SEARCH-", "REQ-HITS-", "REQ-ADVS-", "REQ-LOG-"],
        "terms": ["Suche", "search", "Trefferliste", "report", "history", "Historie", "Logdaten"],
    },
    "Berechtigungen und rollenbasierter Zugriff": {
        "prefixes": ["REQ-RBAC-", "REQ-AUTH-"],
        "terms": ["Berechtigung", "authorization", "role", "permission", "access"],
    },
    "Storno, Löschung und Audit-Trail": {
        "ids": ["REQ-AUDIT-001", "REQ-IDM-001", "REQ-DACT-003", "REQ-DACT-004", "REQ-REC-003"],
        "prefixes": ["REQ-LOG-"],
        "terms": ["Storno", "cancel", "Widerruf", "Audit", "Log", "history"],
    },
}

DB_TABLE_RECOMMENDATION_RULES = {
    "app.TDropOffLocation": {
        "priority": "medium",
        "decision": "Keep ASG drop-off locations in the existing Lookups model",
        "target_model": "Lookups",
        "recommendation": (
            "Do not introduce a separate DropOffLocations table. The client-confirmed C# target structure is "
            "LookupConfiguration/Lookups with LookupType.AsgDropOffLocation. During implementation only verify "
            "that sort order, active status, and free-text allowance are fully represented in the Lookup item model "
            "and that order data is validated against it."
        ),
        "rationale": (
            "The legacy table contains the domain ASG drop-off location selection list. The client has confirmed "
            "that this list is managed in the C# system via LookupConfiguration; technically this is the existing "
            "Lookups table with the key asg-drop-off-location."
        ),
        "requirement_terms": ["ASG", "Abstell", "Abstellgenehmigung", "Drop-off"],
        "requirement_prefixes": ["REQ-ASG-"],
    },
    "app.TPermission": {
        "priority": "high",
        "decision": "Migrate legacy permissions into the existing C# RBAC schema",
        "target_model": "auth.RolePermissions",
        "recommendation": (
            "Take the domain-confirmed legacy rights as data into the existing roles and permissions model. "
            "DB constraints enforce unique permission names and consistent role assignments."
        ),
        "rationale": (
            "C# already has a structurally different roles/permissions schema. What matters is domain role parity, "
            "not an identical table structure."
        ),
        "requirement_terms": ["Berechtigung", "Rolle", "Permission", "authorization", "RBAC"],
        "requirement_prefixes": ["REQ-AUTH-", "REQ-RBAC-"],
    },
    "app.TDestination": {
        "priority": "high",
        "decision": "Use existing OrderRoutingAddresses and OrderRoutingPostOfficeBoxes",
        "target_model": "OrderRoutingAddresses",
        "target_model_label": "OrderRoutingAddresses / OrderRoutingPostOfficeBoxes",
        "recommendation": (
            "Do not introduce a new generic OrderRouting table. The existing C# entities "
            "OrderRoutingAddresses, OrderRoutingPostOfficeBoxes, and Addresses remain the target for origin, "
            "destination, PAC/postal code, and post-box routing; missing TDestination fields are added there directly."
        ),
        "rationale": (
            "The C# backend code uses TPC entities for routing instead of a single table. These existing entities "
            "are the appropriate target surface for TDestination semantics."
        ),
        "requirement_terms": ["Adresse", "Routing", "Destination", "Postlagernd", "PAC", "PLZ", "Standort"],
        "requirement_prefixes": ["REQ-FUZZY-", "REQ-SITE-", "REQ-PF-"],
    },
    "app.TOrderChangeReason": {
        "priority": "medium",
        "decision": "Maintain change and cancellation reasons in the existing Lookups model",
        "target_model": "Lookups",
        "recommendation": (
            "Do not introduce a separate OrderChangeReasons table. The controlled list is maintained as a new "
            "lookup type in Lookups; audit and cancellation data store the confirmed reason code."
        ),
        "rationale": (
            "The C# backend code already has Lookups as a generic, configured surface for controlled catalog values. "
            "TOrderChangeReason fits that existing pattern."
        ),
        "requirement_terms": ["Storno", "Änderung", "Aenderung", "Widerruf", "Grund", "Audit"],
        "requirement_prefixes": ["REQ-LOG-"],
        "requirement_ids": ["REQ-AUDIT-001", "REQ-DACT-003", "REQ-DACT-004"],
    },
    "app.TOrderDetail": {
        "priority": "high",
        "decision": "Use existing Customers and Companies participant entities",
        "target_model": "Customers",
        "target_model_label": "Customers / Companies",
        "recommendation": (
            "Do not introduce a separate OrderRecipients table. The existing C# tables Customers and Companies "
            "remain the order participant surface; missing legacy detail semantics such as running number, "
            "new-recipient flag, and validity/cancellation state are added to the existing participant and order data."
        ),
        "rationale": (
            "DirectiveOrder already has Customers and Companies collections with EF tables and a DirectiveOrderId "
            "reference. These existing entities are the appropriate target surface for TOrderDetail semantics; "
            "an additional Recipient clone would be redundant."
        ),
        "requirement_terms": ["Empfänger", "Person", "Mitbewohner", "berechtigte Personen", "Titel", "label"],
    },
    "app.TBoxMasterData": {
        "priority": "high",
        "decision": "Add post-office box master data model",
        "target_model": "PostOfficeBoxes",
        "recommendation": (
            "Persist box inventory, size, status, postal code/box combinations, and availability in a PostOfficeBoxes "
            "table with FKs to location and status."
        ),
        "rationale": (
            "C# knows post-office box product types and routing markers, but has no complete master data table for "
            "box inventory and status."
        ),
        "requirement_terms": ["Postfach", "PF-Stammdaten", "Schließfach", "Offene Fächer", "PostOfficeBox"],
        "requirement_prefixes": ["REQ-PF-", "REQ-PFMD-", "REQ-TYPPF-"],
    },
    "app.TBoxLocation": {
        "priority": "high",
        "decision": "Introduce a relational post-office box location catalog",
        "target_model": "PostOfficeBoxLocations",
        "recommendation": (
            "Store box locations, postal code/city/branch references, and location validity in a PostOfficeBoxLocations "
            "table. PostOfficeBoxes references this table via FK."
        ),
        "rationale": (
            "Legacy SQL has a location catalog; C# has general addresses and routing, but no equivalent "
            "post-office box location inventory."
        ),
        "requirement_terms": ["Postfachstandort", "Standort", "Postfach", "freie Fächer", "Schließfach"],
        "requirement_prefixes": ["REQ-PF-", "REQ-PFMD-"],
    },
    "app.TBoxStatus": {
        "priority": "medium",
        "decision": "Maintain post-office box status in the existing Lookups model",
        "target_model": "Lookups",
        "recommendation": (
            "Do not introduce a separate PostOfficeBoxStatuses table. Box status values are maintained as a "
            "controlled lookup type in Lookups; PostOfficeBoxes stores the confirmed status code."
        ),
        "rationale": "The legacy table contains status values; C# has no dedicated model for this, but already has the generic Lookups surface.",
        "requirement_terms": ["Postfachstatus", "Status", "Postfach", "freie Fächer"],
        "requirement_prefixes": ["REQ-PF-", "REQ-PFMD-"],
    },
    "app.TRegistrationFeedback": {
        "priority": "low",
        "decision": "Introduce RegistrationFeedbackEvents as an append-only integration log",
        "target_model": "RegistrationFeedbackEvents",
        "recommendation": (
            "Store registration and customer-number feedback as append-only events so that each external feedback "
            "is atomically traceable to the affected order."
        ),
        "rationale": (
            "The legacy table acts like integration feedback; no equivalent domain surface is visible in the current "
            "C# persistence model. The spec contains no feedback/registration domain requirement; the table remains "
            "pure legacy integration evidence."
        ),
        "requirement_terms": ["Registrierung", "Feedback", "Kundennummer", "SSO", "ExampleCrm"],
        "requirement_prefixes": ["REQ-IDM-", "REQ-AUTH-"],
    },
    "app.TSsoIdentification": {
        "priority": "medium",
        "decision": "Introduce SsoIdentifications as a relational identification history",
        "target_model": "SsoIdentifications",
        "recommendation": (
            "Persist SSO assignment, Level-90 evidence, editor, and capture timestamp in SsoIdentifications "
            "and bind it via FK to Orders and CustomerIdentifications."
        ),
        "rationale": (
            "C# contains identification and integration fields, but no direct legacy equivalent for "
            "SSO identification rows."
        ),
        "requirement_terms": ["SSO", "Identifizierung", "ExampleCrm", "Level 90", "Kundennummer"],
        "requirement_prefixes": ["REQ-IDM-", "REQ-AUTH-"],
    },
    "app.TSsoDeletion": {
        "priority": "medium",
        "decision": "Introduce SsoDeletionEvents as an append-only audit table",
        "target_model": "SsoDeletionEvents",
        "recommendation": (
            "Each SSO deletion is stored as an immutable event with FK to CustomerIdentifications and Orders. "
            "Deletion of the active assignment always produces the same audit record."
        ),
        "rationale": "The legacy table is deletion- and audit-adjacent; C# has no direct persistence evidence for this.",
        "requirement_terms": ["SSO", "Löschung", "Loeschung", "Audit", "Datenschutz"],
        "requirement_prefixes": ["REQ-IDM-", "REQ-LOG-"],
    },
    "app.TBatchOrder": {
        "priority": "high",
        "decision": "Introduce BatchImports as an ACID import aggregate",
        "target_model": "BatchImports",
        "recommendation": (
            "SAM CSV imports are persisted via BatchImports, BatchImportRows, and BatchImportErrors. The single "
            "legacy staging table is intentionally normalized into three tables: the legacy table repeats batch "
            "header data (company, SAP debtor number) on every row, has no batch status, and squeezes multiple "
            "validation errors into individual text columns (error, duplicates). In the target model BatchImports "
            "carries the job/upload (one record per bulk-customer import), BatchImportRows carries status and "
            "order FK per CSV row, BatchImportErrors carries any number of structured errors per row. Only "
            "successfully validated rows produce Orders; job status, row status, and errors remain transactionally "
            "traceable."
        ),
        "rationale": (
            "C# knows the SAM product type, but has no staging and row-level model for bulk imports. "
            "The flat legacy table mixes three lifecycles (import job, CSV row, error) in one record."
        ),
        "requirement_terms": ["SAM", "BatchOrder", "Massenimport", "CSV", "Import"],
        "requirement_prefixes": ["REQ-SAM-"],
    },
    "app.TShipmentTypeAssignment": {
        "priority": "medium",
        "decision": "Introduce OrderShipmentTypeSelections as a join table",
        "target_model": "OrderShipmentTypeSelections",
        "recommendation": (
            "Shipment types selected per order are stored in a normalized join table. "
            "The table references Orders and ShipmentTypes via FK and carries the selection for filtering, printing, "
            "and reporting."
        ),
        "rationale": (
            "C# has shipment type catalogs, but no clear normalized per-order equivalent to the legacy assignment."
        ),
        "requirement_terms": ["Sendungsarten", "Sendungstyp", "shipment types", "mail-piece"],
        "requirement_prefixes": ["REQ-START-", "REQ-TYP"],
    },
    "app.TServiceInfo": {
        "priority": "low",
        "decision": "Do not port ServiceInformation as a C# domain table",
        "target_model": "NoCSharpDomainTable",
        "recommendation": (
            "Do not create a new C# domain table. Service information remains outside the ACID domain model "
            "until a confirmed requirement demands explicit management of this data."
        ),
        "rationale": (
            "The table is a service endpoint registry (service name -> URL), i.e. runtime configuration rather "
            "than domain data. In the new application this belongs in appsettings/environment configuration; "
            "the spec contains no requirement for domain management of this data."
        ),
        "requirement_terms": ["ServiceInfo", "Serviceinformation", "Hinweis", "Info"],
    },
    "app.TTitle": {
        "priority": "low",
        "decision": "Keep title columns, maintain title catalogs as lookup types",
        "target_model": "Lookups",
        "recommendation": (
            "Do not introduce a dedicated title table. Titles remain as length-limited columns on the existing person "
            "and identity tables; the selection lists 'title prefix' and 'title suffix' (Spec chapter 11.5.3/11.5.4, "
            "new in V1.9) are maintained as lookup types in Lookups."
        ),
        "rationale": (
            "C# already stores titles on person/identification data (TitlePrefix/TitleSuffix); the spec additionally "
            "requires maintained drop-down catalogs for prefix and suffix titles."
        ),
        "requirement_terms": ["Titel", "Nachgestellter Titel", "Personendaten"],
        "requirement_ids": ["REQ-ERF-006"],
    },
    "app.TBilling": {
        "priority": "high",
        "decision": "Introduce BillingRecords as the billing aggregate",
        "target_model": "BillingRecords",
        "recommendation": (
            "Store fees, payment status, open collection cases, and export references in BillingRecords. "
            "Orders references the current BillingRecord; detail history is tracked via BillingEvents. "
            "Spec chapter 19: open cases carry the {EXTERNAL-SYSTEM} error text and are resolved as courtesy "
            "adjustment vs. invoice (each with an annotation)."
        ),
        "rationale": (
            "The legacy table contains detailed billing data; C# currently only has a compact "
            "PaymentStatus on Orders."
        ),
        "requirement_terms": ["Verrechnung", "Inkasso", "Payment", "Zahlung", "Gebühr", "offene Inkassofälle"],
        "requirement_prefixes": ["REQ-COLL-"],
    },
    "app.TBillingStatus": {
        "priority": "medium",
        "decision": "Use the existing DirectivePaymentStatus / Orders.PaymentStatus",
        "target_model": "Orders",
        "target_model_label": "Orders.PaymentStatus / DirectivePaymentStatus",
        "recommendation": (
            "Do not introduce a separate BillingStatuses table. The existing status anchor remains "
            "DirectivePaymentStatus on Orders.PaymentStatus; BillingRecords and BillingEvents carry the confirmed "
            "status value as a transactional field."
        ),
        "rationale": "The C# backend code already has a PaymentStatus column and a DirectivePaymentStatus enum. An additional status catalog would be redundant without confirmed new status maintenance requirements.",
        "requirement_terms": ["VerrechnungStatus", "Verrechnung", "Inkasso", "PaymentStatus", "Zahlungsstatus"],
        "requirement_prefixes": ["REQ-COLL-"],
    },
    "app.TBilling_Deleted_CurrentBackup": {
        "priority": "low",
        "decision": "Do not port as a business table",
        "target_model": "NoCSharpDomainTable",
        "recommendation": (
            "Do not adopt this backup/deleted table as an active C# domain table. Domain history is "
            "covered via BillingEvents; technical retention remains outside the {PROJECT-NAME} domain model."
        ),
        "rationale": (
            "The table is a trigger-maintained backup copy of deleted billing rows, not an independent domain "
            "dataset. In the target model deletion is an append-only BillingEvents event, which provides the "
            "same traceability without a duplicate backup table; technical backup/retention is the responsibility "
            "of the database platform."
        ),
        "requirement_terms": ["Verrechnung", "Historie", "Löschung", "Backup", "Audit"],
        "requirement_prefixes": ["REQ-COLL-", "REQ-LOG-"],
    },
    "app.TBilling_History": {
        "priority": "medium",
        "decision": "Introduce BillingEvents as an append-only history table",
        "target_model": "BillingEvents",
        "recommendation": (
            "Every domain change to BillingRecords is stored as an immutable BillingEvents record. "
            "Status transitions, amount changes, and user context remain revision-safe."
        ),
        "rationale": "C# has no direct evidence of detailed billing history.",
        "requirement_terms": ["Verrechnung", "Historie", "Inkasso", "Audit", "Payment"],
        "requirement_prefixes": ["REQ-COLL-", "REQ-LOG-"],
    },
    "dbo.Import_LabelPrint": {
        "priority": "medium",
        "decision": "Introduce PrintJobs as an ACID job table",
        "target_model": "PrintJobs",
        "recommendation": (
            "Store print and label runs as PrintJobs plus PrintJobOrders; the single legacy import table is "
            "normalized into two because one print run bundles many orders (m:n). PrintJobs carries the run with "
            "status, creation time, handoff time, label sheet count, and delivery postal code (Spec chapter 16.3.5); "
            "PrintJobOrders links the run to the affected Orders so that reruns and reprints are transactionally "
            "traceable."
        ),
        "rationale": "The legacy table is print-adjacent; C# currently shows no direct print import persistence model.",
        "requirement_terms": ["Etikett", "Druck", "Nachdruck", "Kuvert", "print"],
        "requirement_prefixes": ["REQ-PRT-"],
    },
    "dbo.TAusnahmetabellePP": {
        "priority": "high",
        "decision": "Introduce ParcelPostExceptions as a rules exception table",
        "target_model": "ParcelPostExceptions",
        "recommendation": (
            "Store partner exceptions relationally with product/order type references (exception types PFU, WUN, PFP) "
            "and postal code references. Unique constraints prevent duplicate exception rows; synchronization to the "
            "online service (effective the following day) remains an interface question."
        ),
        "rationale": (
            "Spec V1.9 chapter 2 explicitly requires integration of the partner exception table into the legacy DB; "
            "maintenance previously ran as its own legacy codebase form."
        ),
        "requirement_terms": ["Ausnahme", "Paket", "Paketpost", "PP", "Regel", "Post.Partner"],
    },
    "dbo.TAutoNummer": {
        "priority": "medium",
        "decision": "Do not adopt as a C# domain table; resolve number assignment via database sequences",
        "target_model": "NoCSharpDomainTable",
        "recommendation": (
            "Do not introduce a dedicated number-range domain table. Form numbers are assigned via native database "
            "sequences per product code and registration year (Spec chapter 11.13.11) — analogous to the existing "
            "legacy sequences; uniqueness is guaranteed by the database, not a domain table."
        ),
        "rationale": (
            "C# has form number logic, but no legacy-equivalent counter table; a standalone table "
            "would have no relationships to the rest of the domain model and was therefore deliberately excluded from the target model."
        ),
        "requirement_terms": ["Formularnummer", "Formularnr", "AutoNummer", "Nummernkreis", "Sequence"],
        "requirement_ids": ["REQ-ERF-028", "REQ-ERF-029"],
    },
    "dbo.TLog": {
        "priority": "high",
        "decision": "Introduce AuditLog as an append-only domain audit table",
        "target_model": "AuditLog",
        "recommendation": (
            "Store create, update, cancel, and admin actions in AuditLog. The table is append-only, references "
            "domain aggregates by stable key, and stores user, organization, IP, and time context (Spec chapter 7). "
            "Action domain per chapters 16.3.6/21.2: new, data correction, extension, extension with address change, "
            "cancellation, revocation, label reprint, billing."
        ),
        "rationale": "Legacy SQL writes log data; C# currently shows no equivalent domain audit persistence.",
        "requirement_terms": ["Log", "Audit", "Historie", "Storno", "Änderung", "User"],
        "requirement_prefixes": ["REQ-LOG-"],
        "requirement_ids": ["REQ-AUDIT-001", "REQ-DACT-004"],
    },
    "dbo._DBSchema_Log": {
        "priority": "low",
        "decision": "Do not port as a C# domain table",
        "target_model": "NoCSharpDomainTable",
        "recommendation": (
            "Do not adopt into the C# domain model. EF migration history remains the authoritative technical "
            "schema history for the new application."
        ),
        "rationale": (
            "The table logs DDL/schema changes to the legacy database via database trigger — an "
            "infrastructure audit entity, not a {PROJECT-NAME} domain entity. In the new application EF Core "
            "migrations plus version control provide the same schema history authoritatively; porting it would "
            "duplicate deployment concerns into the domain model."
        ),
        "requirement_terms": ["Schema", "Migration", "Deployment"],
    },
    "ref.RLocation": {
        "priority": "high",
        "decision": "Introduce ProviderLocations as a synchronized location read model",
        "target_model": "ProviderLocations",
        "recommendation": (
            "Synchronize provider and branch locations into ProviderLocations. PAC, postal code, validity, and "
            "location type receive unique keys and are referenced by routing and post-box data via FK."
        ),
        "rationale": (
            "Legacy SQL uses provider-side location data; C# has general addresses, but no direct "
            "ref.RLocation equivalent."
        ),
        "requirement_terms": ["Standort", "Filiale", "PAC", "PLZ", "Routing", "Dienststelle"],
        "requirement_prefixes": ["REQ-SITE-", "REQ-FUZZY-", "REQ-PF-"],
    },
}

DEFAULT_DB_TABLE_RECOMMENDATION_RULE = {
    "priority": "medium",
    "decision": "Clarify domain ownership",
    "target_model": "ReviewRequired",
    "recommendation": (
        "This legacy table needs an explicit ACID decision before it is adopted into C# persistence."
    ),
    "rationale": "The static scan found no clear C# coverage and no specific recommendation rule.",
    "requirement_terms": [],
}

# Concrete field-level guidance per legacy table: which fields to add on the
# target model (or as lookup-item attributes) and why. Rendered as the
# "Field changes" section of the Recommendation cards on the SQL Landscape
# page. Tables that need no schema change (data import only, pure lookups,
# no-port decisions) have no entry. Tuples: (field, type, reason).
DB_TABLE_TARGET_FIELDS = {
    "app.TDropOffLocation": [
        ("sortOrder", "INT (lookup item)", "Legacy Sortierung — controls the drop-off drop-down order."),
        ("isActive", "BIT (lookup item)", "Legacy aktiv — inactive locations stay readable on old orders but are no longer selectable."),
        ("allowsFreeText", "BIT (lookup item)", "Legacy Freitext_Zusatz — enables the free-text drop-off place (max 93 chars, the word 'Code' is forbidden, spec 11.10.1.15)."),
    ],
    "app.TDestination": [
        ("OrderRoutingAddresses.IsPosteRestante", "BIT", "Legacy postlagernd — general-delivery routing variant (spec 11.10.1.8)."),
        ("OrderRoutingAddresses.PosteRestanteBranchId", "UNIQUEIDENTIFIER FK", "Legacy Dienststelle_Postlagernd — the branch (ProviderLocations) that holds general-delivery mail."),
        ("OrderRoutingAddresses.SequenceNumber", "TINYINT", "Legacy nach_nr — supports multiple forwarding destinations per order."),
        ("OrderRoutingPostOfficeBoxes.BoxNumber", "VARCHAR(10)", "Legacy Postfach — box number for PF routing (spec 11.10.1.4: max 10 for foreign boxes)."),
        ("OrderRoutingPostOfficeBoxes.PostalCode", "VARCHAR(20)", "Legacy PLZ of the box — domestic exactly 4 digits, foreign up to 20."),
        ("OrderRoutingPostOfficeBoxes.PostOfficeBoxId", "UNIQUEIDENTIFIER FK", "Link to the PostOfficeBoxes inventory so PF orders bind to a managed box."),
    ],
    "app.TOrderChangeReason": [
        ("code / name", "lookup item", "Legacy Bezeichnung — controlled change/cancel reason shown in Logdaten and audit."),
        ("isHeaderChange", "BIT (lookup item)", "Legacy Kopf_Neu — reason forces a new order header version."),
        ("isFullCancellation", "BIT (lookup item)", "Legacy Gesamt_Storno — reason cancels the entire order."),
        ("isActive", "BIT (lookup item)", "Legacy Aktiv — retire reasons without losing audit references."),
    ],
    "app.TOrderDetail": [
        ("SequenceNumber", "INT", "Legacy LFD_Nr — stable person position for labels and the order data file ('one record per name')."),
        ("ParticipantRole", "TINYINT", "Legacy NeuerEmpfaenger — distinguishes applicant, new recipient (PUM/REC/PV) and roommate (ASG, max 4)."),
        ("ValidityStatus", "TINYINT", "Legacy OrderValid — per-person validity state independent of the order."),
        ("CancelledAt / CancelledBy / CancellationReason", "DATETIME2 / VARCHAR(80) / NVARCHAR(100)", "Legacy StornoAm/StornoDurch/StornoGrund — a single person can be cancelled without cancelling the order."),
    ],
    "app.TBoxMasterData": [
        ("BoxNumber", "VARCHAR(4)", "Legacy PF — 4 digits, unique per location, 9999 reserved for the head office (Spec chapter 18)."),
        ("PostalCode", "VARCHAR(20)", "Legacy PLZ — unique together with BoxNumber."),
        ("SizeCode", "VARCHAR(20)", "Legacy Size — klein/groß; Art adds offen/Paket when selecting in an order (spec 11.7)."),
        ("FacilityCode", "VARCHAR(20)", "GAS locker-system assignment from the legacy PF-Stammdaten screens."),
        ("TariffCode", "VARCHAR(40)", "Tariff domain: Privat, Privat Plus, Business, Business Plus, Aufgabe, Paket Business, Paket Privat (Spec chapter 18)."),
        ("StatusCode", "VARCHAR(40)", "TBoxStatus domain frei/belegt/belegt-Nachfrist/ausgelaufen/inaktiv/reserviert incl. automatic Nachfrist transitions."),
        ("LocationId", "UNIQUEIDENTIFIER FK", "Replaces legacy PLZ-only location binding with a PostOfficeBoxLocations reference."),
        ("CurrentOrderId", "UNIQUEIDENTIFIER", "Legacy FK_OrderHead — the order currently occupying the box."),
    ],
    "app.TBoxLocation": [
        ("ProviderLocationId", "UNIQUEIDENTIFIER FK", "Binds the box location to the PAI/Provider-DB-synchronized branch."),
        ("PostalCode / City / Street / HouseNumber", "VARCHAR", "Legacy PLZ/Ort/Strasse/Hnr — the location address block shown in PF-Stammdaten."),
        ("LocationType", "VARCHAR(64)", "Legacy Typ_Bezeichnung — Filiale vs. Post.Partner."),
        ("IsActive / IsDeleted", "BIT", "Legacy Aktiv/deleted — soft delete keeps history for old boxes."),
        ("ValidFrom", "DATETIME2", "Legacy Gueltig_Von — location validity."),
        ("FreeText", "NVARCHAR(4000)", "Legacy Freitext — operational notes per location."),
    ],
    "app.TBoxStatus": [
        ("status lookup items", "lookup item", "Legacy Statustext — frei, belegt, belegt-Nachfrist, ausgelaufen, inaktiv, reserviert; drives the PF grids and the automatic transitions of Spec chapter 18."),
    ],
    "app.TRegistrationFeedback": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy FK_OrderHead — feedback always belongs to one order."),
        ("SsoUserId / SsoCustomerId / CustomerNumber", "BIGINT", "Legacy idbenutzer/idkunde/kundennummer — the SSO identities reported back."),
        ("ClerkUserId", "VARCHAR(10)", "Legacy uuser — who triggered the registration."),
        ("CostCenter", "VARCHAR(50)", "Legacy Kostenstelle — billing attribution."),
        ("CreatedAt", "DATETIME2", "Legacy tstamp — append-only event time."),
    ],
    "app.TSsoIdentification": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy FK_OrderheadID — identification evidence per order."),
        ("SsoCustomerNumber", "BIGINT", "Legacy SSOKundennr — max 7 digits, explicitly not the SSO-ID (Spec chapter 10)."),
        ("OrgUnit / CostCenter", "BIGINT", "Legacy Dienststelle/Kostenstelle — where the identification happened."),
        ("ClerkUserId", "VARCHAR(10)", "Legacy Bearbeiter — who identified the customer."),
        ("IsFirstCapture / IsIdentified", "BIT", "Legacy Ersterfassung/Identifiziert — Level-90 evidence; PUM may only be captured for identified customers."),
        ("CapturedAt", "DATETIME2", "Legacy Erfassungsdatum — audit time."),
    ],
    "app.TSsoDeletion": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy FK_OrderHeadID — order whose SSO customer was deleted."),
        ("DeletedAt", "DATETIME2", "Legacy insertDate — immutable deletion audit timestamp."),
    ],
    "app.TBatchOrder": [
        ("BatchImports.SapDebtorNumber", "CHAR(10)", "spec 13.2 — exactly 10 digits, validated against SAP ('Debitorennummer gibt es nicht.')."),
        ("BatchImports.CompanyName", "NVARCHAR(100)", "spec 13.2 — Firmenname, mandatory, max 100 chars."),
        ("BatchImports.GoodwillText", "NVARCHAR(200)", "spec 13.2 — 'Text für Kulanz', mandatory, max 200 chars."),
        ("BatchImports.CsvFileName", "NVARCHAR(260)", "spec 13.1 — uploaded Adress-CSV reference."),
        ("BatchImportRows.LineNumber", "SMALLINT", "Legacy Zeile — CSV line for error reporting."),
        ("BatchImportRows von/nach address columns", "VARCHAR", "spec 13.1 CSV layout incl. Postfach and Postlagernd variants."),
        ("BatchImportRows.ValidationStatus", "VARCHAR(20)", "Legacy pruefung — row-level validation state."),
        ("BatchImportRows.Duplicates", "NVARCHAR(500)", "Legacy Dubletten — duplicate hits found during validation."),
        ("BatchImportRows.OrderId", "UNIQUEIDENTIFIER FK", "Created order when the row imports successfully."),
    ],
    "app.TShipmentTypeAssignment": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy FK_OrderHead — selection belongs to one order."),
        ("ShipmentTypeId", "UNIQUEIDENTIFIER FK", "Legacy FK_SendungTyp — reuses the existing C# ShipmentTypes catalog."),
        ("IsChargeable", "BIT", "Carries the 'Zusätzliche Entgeltpauschale' selection (spec 11.12, e.g. 'Pakete und Post Express')."),
    ],
    "app.TTitle": [
        ("title-prefix lookup items", "lookup item", "Legacy Titel — drop-down 'Titel vorangestellt', alphabetically sorted (spec 11.5.3)."),
        ("title-suffix lookup items", "lookup item", "New 'Titel danach' catalog (spec 11.5.4, new in V1.9; interface extension to Online-Services)."),
    ],
    "app.TBilling": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy FK_OrderHead — billing record per order."),
        ("PaymentStatus", "INT", "Legacy FK_Status — anchored on the existing DirectivePaymentStatus enum."),
        ("ValidFrom / ValidTo", "DATETIME2", "Legacy GueltigAb/GueltigBis — the billed period."),
        ("ProductId", "SMALLINT", "Legacy product ID — {EXTERNAL-SYSTEM} product reference."),
        ("IsBusiness", "BIT", "Legacy Business — tariff flag."),
        ("CreatedOrgId / CreatedUserId", "VARCHAR(50)", "Legacy Anlage_OrgID/Anlage_UserID — Kap. 19 list columns Anlage-OrgID/Anlage-UserID."),
        ("CompletedAt", "DATETIME2", "Legacy Timestamp_Erledigt — when billing finished."),
        ("OpalError", "NVARCHAR(1000)", "Legacy error code — standardized {EXTERNAL-SYSTEM} error text that classifies a case as an open collection case."),
        ("ResolutionOutcome", "VARCHAR(40)", "Kap. 19 actions — Kulanz or Rechnung ausgelöst closes the open case."),
        ("ResolutionRemark", "NVARCHAR(1000)", "Kap. 19 — Anmerkung captured with either resolution."),
        ("PaidUnits / RatePerExampleRefod / TotalAmountPaid", "SMALLINT / INT / INT", "Legacy Bezahlte_Einheiten/RatePerExampleRefod/TotalAmountPaid — paid amounts."),
        ("SecurityDeposit", "INT", "Legacy PF_Sicherstellung — PF box security deposit (also in the Kap. 21.2 Verrechnung log record)."),
        ("KeyCount / KeyAmount", "TINYINT / INT", "Legacy PF_AnzSchl/PF_BetragSchl — box key handling."),
    ],
    "app.TBilling_History": [
        ("BillingRecordId", "UNIQUEIDENTIFIER FK", "Parent billing record the event belongs to."),
        ("EventType", "VARCHAR(40)", "Status change, amount change, or archive event."),
        ("OldStatus / NewStatus", "INT", "Auditable status transition."),
        ("ActorUserId / ActorOrgId", "VARCHAR(50)", "Who changed the billing record."),
        ("CreatedAt", "DATETIME2", "Legacy ArchivierungsDatum equivalent — append-only event time."),
        ("FormulaNumber", "VARCHAR(20)", "Legacy FormularNr — kept so archived billing stays searchable by order number."),
    ],
    "dbo.Import_LabelPrint": [
        ("LabelSheetCount", "INT", "spec 16.3.5 — number of Etikettenblätter computed for the order."),
        ("ZubaPostalCode", "VARCHAR(10)", "spec 16.3.5 — 4-digit PLZ of the Zustellbasis responsible for the bisherige Adresse."),
        ("PrintReason", "VARCHAR(40)", "First print vs. Etikettennachdruck — feeds the History/Logdaten action (spec 16.3.6/21.2)."),
        ("Status", "VARCHAR(40)", "Job lifecycle so reprints are transactionally traceable."),
        ("RequestedBy / RequestedAt / HandedOffAt", "VARCHAR(80) / DATETIME2", "Print audit: who ordered labels, when, and when the job was handed off."),
        ("PrintJobOrders.OrderId", "UNIQUEIDENTIFIER FK", "Links each label run to the affected order(s)."),
    ],
    "dbo.TAusnahmetabellePP": [
        ("PostalCode", "VARCHAR(20)", "Legacy PLZ — the Post.Partner location the exception applies to."),
        ("ExceptionCode", "VARCHAR(40)", "Exception types seen in the legacy screen: PFU, WUN, PFP."),
        ("DirectiveId", "UNIQUEIDENTIFIER FK", "Product/order type the exception switches off for that location."),
        ("IsActive / ValidFrom / ValidTo", "BIT / DATETIME2", "Lifecycle — effective immediately in the legacy app, next day in the Online-Service."),
    ],
    "dbo.TLog": [
        ("OrderId", "UNIQUEIDENTIFIER FK", "Legacy Datensatz_ID — audit entries reference the affected order."),
        ("Action", "VARCHAR(60)", "spec 16.3.6/21.2 domain: Neu, Datenkorrektur, Verlängerung, Verlängerung und Adressänderung, Storno, Widerruf, Etikettennachdruck, Verrechnung."),
        ("ChangeReasonCode", "VARCHAR(40)", "Legacy FK_LogTyp — confirmed change reason from the Lookups catalog."),
        ("ActorUserId", "VARCHAR(80)", "Spec chapter 7 — U-/S-User of every create/change/cancellation."),
        ("ActorOrgUnit", "VARCHAR(80)", "Dienststelle column of the History view (spec 16.3.6)."),
        ("ActorIpAddress", "VARCHAR(64)", "Spec chapter 7 explicitly demands IP address logging."),
        ("CreatedAt", "DATETIME2", "Spec chapter 7 — date and time of the action."),
        ("Snapshot", "NVARCHAR(MAX)", "Legacy Nachricht XML — log data must show the blocks {LEGACY-SYSTEM} / person data / {LEGACY-SYSTEM} before / {LEGACY-SYSTEM} after per action (Spec chapter 21)."),
    ],
    "ref.RLocation": [
        ("Pac", "BIGINT", "Legacy PAC — unique location key used by routing and PF data."),
        ("PostalCode / OrgPostalCode", "BIGINT / INT", "Legacy PLZ/OrgPLZ — location and organisational postal codes."),
        ("Name", "NVARCHAR(255)", "Legacy Bezeichnung — branch display name (e.g. 'Filiale - PA 1006 Wien')."),
        ("LocationType", "VARCHAR(64)", "Legacy Bezeichnung_Typ — Filiale, Post.Partner, Zustellbasis; drives PF and Postlagernd pickers."),
        ("City / Street / HouseNumber / Email", "VARCHAR", "Legacy address and contact block."),
        ("IsActive / ValidFrom", "BIT / DATETIME2", "Legacy Aktiv/Gueltig_Von — only active locations are selectable."),
        ("SyncedAt", "DATETIME2", "Read-model bookkeeping — when the row was last synchronized from the Provider-DB/PAI feed."),
    ],
}

ACID_RECOMMENDED_TABLES = {
    "Orders": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderHead"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "CustomerIdentificationId", "FK"),
            ("UNIQUEIDENTIFIER", "OwnerId", ""),
            ("TINYINT", "Type", ""),
            ("NVARCHAR_MAX", "FormulaNumber", ""),
            ("DATETIME2", "ValidFrom", ""),
            ("DATETIME2", "ValidTo", ""),
            ("UNIQUEIDENTIFIER", "OriginId", "FK"),
            ("UNIQUEIDENTIFIER", "DestinationId", "FK"),
            ("INT", "PaymentStatus", ""),
            ("NVARCHAR_MAX", "Data", ""),
            ("BIT", "ValidUntilRevoked", "NEU"),
            ("DATETIME2", "AcceptedAt", "NEU"),
            ("DATETIME2", "CancelledAt", "NEU"),
            ("DATETIME2", "CancelledFrom", "NEU"),
            ("NVARCHAR_100", "CancellationReason", "NEU"),
            ("VARCHAR_80", "CancelledBy", "NEU"),
            ("BIT", "Consent", "NEU"),
            ("VARCHAR_40", "Channel", "NEU"),
            ("VARCHAR_80", "ExternalOrderId", "NEU"),
            ("VARCHAR_60", "SapDebtorNumber", "NEU"),
            ("VARCHAR_12", "PromoCode", "NEU"),
            ("VARCHAR_50", "ResponsibleOrgUnit", "NEU"),
            ("NVARCHAR_MAX", "ContactDetails", "NEU"),
        ],
        "note": "Current C# Orders table from the client schema; it remains the ACID anchor and is extended, never renamed. Deliberate specification extensions (marked NEU): cancellation fields incl. 'Stornieren ab' (ch. 16.3.4), acceptance date 'Übernommen am' (ch. 11.13.1), capture channel legacy-DB vs. Internet (ch. 22), external order id, SAP debtor number (Kap. 20: exactly 10 digits), U-/S-User promo code for ASG and PUM (Kap. 11.13.10), consent flag, responsible org unit, open-ended validity 'Gültig bis Widerruf', and the Erreichbarkeit contact block (Kap. 11.11). Product-specific payloads such as ASG drop-off selection, PFU hand-over variant, and PUM redirection variant stay in the polymorphic Data JSON.",
    },
    "Directives": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderType"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("TINYINT", "Type", ""),
            ("NVARCHAR_32", "Code", ""),
            ("NVARCHAR_128", "Name", ""),
            ("INT", "Order", ""),
            ("UNIQUEIDENTIFIER", "ParentId", "FK"),
            ("NVARCHAR_MAX", "Settings", ""),
        ],
        "note": "Current C# product/catalog table. Use it as the reference surface for directive type, subtypes, product settings, import, print, and rule references.",
    },
    "Addresses": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TDestination"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("BIGINT", "Pac", "UK"),
            ("NVARCHAR_128", "Type", ""),
            ("NVARCHAR_128", "PostalCode", ""),
            ("NVARCHAR_MAX", "Country", ""),
            ("NVARCHAR_2048", "CityFullName", ""),
            ("NVARCHAR_2048", "CityInternalName", ""),
            ("BIGINT", "CityIdentificationSign", ""),
            ("NVARCHAR_2048", "StreetFullName", ""),
            ("NVARCHAR_2048", "StreetShortName", ""),
            ("BIGINT", "StreetIdentificationSign", ""),
            ("NVARCHAR_2048", "HouseNumberFullName", ""),
            ("NVARCHAR_2048", "HouseNumberShortName", ""),
            ("NVARCHAR_2048", "HouseNumberSortableNumber", ""),
            ("DATETIME2", "ValidTo", ""),
            ("NVARCHAR_MAX", "RowHash", ""),
        ],
        "note": "Current C# address aggregate table. Keep this exact entity for PAC/postal/street/house-number data instead of introducing a renamed address table.",
    },
    "CustomerIdentifications": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TSsoIdentification", "app.TTitle"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_32", "TitlePrefix", ""),
            ("NVARCHAR_512", "FirstName", ""),
            ("NVARCHAR_512", "LastName", ""),
            ("NVARCHAR_32", "TitleSuffix", ""),
            ("NVARCHAR_128", "Type", ""),
            ("NVARCHAR_256", "Number", ""),
            ("DATETIME2", "IssuedAt", ""),
            ("NVARCHAR_512", "IssuingAuthority", ""),
            ("NVARCHAR_2048", "Remarks", ""),
        ],
        "note": "Current C# identity table extended by recommendation. Keep titles as constrained columns; add SSO/history evidence through related event tables instead of a duplicate identity entity.",
    },
    "Customers": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderDetail"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_32", "Salutation", ""),
            ("NVARCHAR_32", "TitlePrefix", ""),
            ("NVARCHAR_512", "FirstName", ""),
            ("NVARCHAR_512", "LastName", ""),
            ("NVARCHAR_32", "TitleSuffix", ""),
            ("DATETIME2", "BirthDate", ""),
            ("NVARCHAR_MAX", "CorrelationId", ""),
            ("UNIQUEIDENTIFIER", "DirectiveOrderId", "FK"),
            ("INT", "PrintSequence", ""),
            ("BIT", "IsNewRecipient", ""),
        ],
        "note": "Current C# participant table. Extend this existing entity for legacy detail semantics such as print sequence and new-recipient markers instead of introducing OrderRecipients.",
    },
    "Companies": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderDetail"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_512", "Name", ""),
            ("NVARCHAR_256", "RegistrationNumber", ""),
            ("UNIQUEIDENTIFIER", "DirectiveOrderId", "FK"),
            ("INT", "PrintSequence", ""),
            ("BIT", "IsNewRecipient", ""),
        ],
        "note": "Current C# company participant table. Extend this existing entity for company recipient/detail semantics instead of introducing a parallel legacy clone.",
    },
    "OrderOwnerPersons": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderHead"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_1024", "CorrelationId", ""),
            ("NVARCHAR_MAX", "Legitimation", ""),
            ("NVARCHAR_64", "FirstName", ""),
            ("NVARCHAR_64", "LastName", ""),
            ("NVARCHAR_MAX", "TitlePrefix", ""),
            ("NVARCHAR_MAX", "TitleSuffix", ""),
        ],
        "note": "Bestehende TPC-Tabelle für private Auftraggeber; Orders.OwnerId zeigt konzeptionell auf Auftraggeberdaten.",
    },
    "OrderOwnerCompanies": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TOrderHead"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_1024", "CorrelationId", ""),
            ("NVARCHAR_MAX", "Legitimation", ""),
            ("NVARCHAR_128", "Name", ""),
            ("NVARCHAR_MAX", "IdType", ""),
            ("NVARCHAR_MAX", "IdNumber", ""),
        ],
        "note": "Bestehende TPC-Tabelle für Firmen-Auftraggeber; keine neue Owner-Tabelle empfohlen.",
    },
    "ShipmentTypeGroups": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TShipmentOrder", "app.TShipmentTypeAssignment"],
        "columns": [
            ("UNIQUEIDENTIFIER", "ShipmentTypeGroupId", "PK"),
            ("UNIQUEIDENTIFIER", "DirectiveId", "PK"),
            ("NVARCHAR_128", "Code", ""),
            ("BIT", "IsChoosable", ""),
            ("BIT", "IsChargeable", ""),
            ("INT", "Order", ""),
        ],
        "note": "Bestehende C#-Gruppierung für Sendungsarten je Directive; auftragsbezogene Auswahl bleibt separat zu prüfen.",
    },
    "ShipmentTypes": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TShipmentTypeAssignment"],
        "columns": [
            ("UNIQUEIDENTIFIER", "ShipmentTypeId", "PK"),
            ("UNIQUEIDENTIFIER", "ShipmentTypeGroupId", "PK"),
            ("UNIQUEIDENTIFIER", "DirectiveId", "PK"),
            ("NVARCHAR_MAX", "Translations", ""),
            ("NVARCHAR_128", "Name", ""),
            ("INT", "Order", ""),
        ],
        "note": "Bestehender Sendungsartkatalog; auftragsbezogene Auswahl wird normalisiert ergänzt.",
    },
    "auth.Roles": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TPermission"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_128", "Name", "UK"),
            ("NVARCHAR_1024", "Description", ""),
            ("NVARCHAR_MAX", "GroupId", ""),
            ("INT", "Priority", ""),
        ],
        "note": "Bestehende Rollentabelle; Legacy-Rollen werden als bestätigte Rollendaten migriert.",
    },
    "auth.Permissions": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TPermission"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_128", "Name", "UK"),
            ("NVARCHAR_1024", "Description", ""),
        ],
        "note": "Bestehende Permission-Tabelle; Legacy-Rechte werden als bestätigte Permission-Daten migriert.",
    },
    "auth.RolePermissions": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TPermission"],
        "columns": [
            ("UNIQUEIDENTIFIER", "PermissionsId", "PK"),
            ("UNIQUEIDENTIFIER", "RoleId", "PK"),
        ],
        "note": "Zieltabelle für rollenbasierte Legacy-Rechte; verbindet Rollen und Permissions referenziell.",
    },
    "Lookups": {
        "kind": "Existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TDropOffLocation", "app.TOrderChangeReason", "app.TBoxStatus"],
        "columns": [
            ("NVARCHAR_450", "Id", "PK"),
            ("NVARCHAR_MAX", "Data", ""),
        ],
        "note": "Current C# lookup table configured through LookupConfiguration. ASG drop-off values already live under asg-drop-off-location; add further controlled legacy catalogs as lookup keys, not as renamed tables.",
    },
    "OrderRoutingAddresses": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TDestination"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "AddressId", "FK"),
            ("NVARCHAR_MAX", "DoorNumber", ""),
            ("NVARCHAR_MAX", "CareOfInformation", ""),
        ],
        "note": "Current C# routing-address table. The current schema stores AddressId plus door/care-of details; the ACID recommendation is to keep this entity and make address integrity explicit.",
    },
    "OrderRoutingPostOfficeBoxes": {
        "kind": "Extend existing C# table",
        "source": "csharp/src/backend",
        "legacy_tables": ["app.TDestination", "app.TBoxMasterData"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "PostOfficeBoxId", "FK"),
        ],
        "note": "Current C# post-office-box routing marker table. Extend this existing entity with a PostOfficeBoxId once the postbox master-data table is implemented.",
    },
    "OrderShipmentTypeSelections": {
        "kind": "New recommended ACID table",
        "source": "app.TShipmentTypeAssignment",
        "legacy_tables": ["app.TShipmentTypeAssignment"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("UNIQUEIDENTIFIER", "ShipmentTypeId", "FK"),
            ("BIT", "IsSelected", ""),
            ("DATETIME2", "SelectedAt", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Normalisierte auftragsbezogene Sendungsartauswahl für Filter, Druck und Reporting.",
    },
    "AuditLog": {
        "kind": "New recommended ACID table",
        "source": "dbo.TLog",
        "legacy_tables": ["dbo.TLog"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("VARCHAR_40", "ChangeReasonCode", ""),
            ("VARCHAR_60", "Action", ""),
            ("VARCHAR_80", "ActorUserId", ""),
            ("VARCHAR_80", "ActorOrgUnit", ""),
            ("VARCHAR_64", "ActorIpAddress", ""),
            ("DATETIME2", "CreatedAt", ""),
            ("NVARCHAR_MAX", "Snapshot", ""),
            ("VARBINARY_32", "PayloadHash", ""),
        ],
        "note": "Append-only domain audit for create, update, cancel, and admin actions. Spec chapter 7: per action U-/S-User, IP address, date and time. Action domain per chapters 16.3.6/21.2: new, data correction, extension, extension with address change, cancellation, revocation, label reprint, billing; the log data view requires snapshot blocks {LEGACY-SYSTEM} / person data / {LEGACY-SYSTEM} before / {LEGACY-SYSTEM} after.",
    },
    "ParcelPostExceptions": {
        "kind": "New recommended ACID table",
        "source": "dbo.TAusnahmetabellePP",
        "legacy_tables": ["dbo.TAusnahmetabellePP"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "DirectiveId", "FK"),
            ("VARCHAR_20", "PostalCode", ""),
            ("VARCHAR_40", "ExceptionCode", "UK"),
            ("DATETIME2", "ValidFrom", ""),
            ("DATETIME2", "ValidTo", ""),
            ("BIT", "IsActive", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Rule exceptions for parcel-post-adjacent special cases with a unique domain code. Spec chapter 2 requires integration of the partner exception table into the legacy DB; exception types per legacy form: PFU, WUN, PFP; changes take effect immediately in the {LEGACY-SYSTEM} application, in the online service only the following day.",
    },
    "OrderDocuments": {
        "kind": "New recommended ACID table",
        "source": "Spec chapters 17 / 16.3.9 (person DB migration, FMS)",
        "legacy_tables": [],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("VARCHAR_20", "FormulaNumber", ""),
            ("VARCHAR_40", "DocumentType", ""),
            ("NVARCHAR_400", "FmsReference", ""),
            ("NVARCHAR_260", "FileName", ""),
            ("BIT", "IsSigned", ""),
            ("VARCHAR_40", "Source", ""),
            ("VARCHAR_80", "CreatedBy", ""),
            ("DATETIME2", "CreatedAt", ""),
        ],
        "note": "Document metadata in the {PROJECT-NAME} database. Spec chapter 17: PDFs (order confirmations, signed files) are stored in FMS; metadata stored in the {PROJECT-NAME} DB rather than the person DB; API POST /documents/{FormularNr}/. Chapter 16.3.9: REC button 'Documents' stores decisions on legal matters.",
    },
    "ProviderLocations": {
        "kind": "New recommended ACID read-model table",
        "source": "ref.RLocation",
        "legacy_tables": ["ref.RLocation"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("VARCHAR_40", "ProviderLocationKey", "UK"),
            ("VARCHAR_20", "Pac", ""),
            ("VARCHAR_20", "PostalCode", ""),
            ("NVARCHAR_120", "City", ""),
            ("NVARCHAR_200", "Name", ""),
            ("VARCHAR_40", "LocationType", ""),
            ("DATETIME2", "ValidFrom", ""),
            ("DATETIME2", "ValidTo", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Synchronisiertes Standort-Read-Model für PAC-, Filial-, Routing- und Postfachbezüge.",
    },
    "PostOfficeBoxLocations": {
        "kind": "New recommended ACID table",
        "source": "app.TBoxLocation",
        "legacy_tables": ["app.TBoxLocation"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "ProviderLocationId", "FK"),
            ("VARCHAR_20", "PostalCode", ""),
            ("NVARCHAR_120", "City", ""),
            ("NVARCHAR_200", "Name", ""),
            ("VARCHAR_40", "BranchCode", ""),
            ("DATETIME2", "ValidFrom", ""),
            ("DATETIME2", "ValidTo", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Standortkatalog für Postfachbestand, Nummernkreise und Verfügbarkeit.",
    },
    "PostOfficeBoxes": {
        "kind": "New recommended ACID table",
        "source": "app.TBoxMasterData",
        "legacy_tables": ["app.TBoxMasterData"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "LocationId", "FK"),
            ("VARCHAR_40", "StatusCode", ""),
            ("VARCHAR_40", "BoxNumber", "UK"),
            ("VARCHAR_20", "PostalCode", ""),
            ("VARCHAR_20", "SizeCode", ""),
            ("VARCHAR_20", "FacilityCode", ""),
            ("VARCHAR_40", "TariffCode", ""),
            ("BIT", "IsReserved", ""),
            ("DATETIME2", "ReservedUntil", ""),
            ("DATETIME2", "ValidFrom", ""),
            ("DATETIME2", "ValidTo", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Post-office box inventory with location, status, size, compartment system, and tariff. Status domain per Spec chapter 18: frei, belegt, belegt-Nachfrist, ausgelaufen, inaktiv, reserviert (as lookup type); PF-Nr 9999 is reserved per head office, grace period = valid-to + 1 month.",
    },
    "SsoIdentifications": {
        "kind": "New recommended ACID table",
        "source": "app.TSsoIdentification",
        "legacy_tables": ["app.TSsoIdentification"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("UNIQUEIDENTIFIER", "CustomerIdentificationId", "FK"),
            ("VARCHAR_60", "SsoCustomerNumber", ""),
            ("VARCHAR_40", "IdentificationLevel", ""),
            ("VARCHAR_60", "CostCenter", ""),
            ("VARCHAR_80", "ClerkUserId", ""),
            ("DATETIME2", "IdentifiedAt", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Historisiert SSO-Identifikationsnachweise mit Bezug zu Auftrag und Kunde.",
    },
    "SsoDeletionEvents": {
        "kind": "New recommended ACID table",
        "source": "app.TSsoDeletion",
        "legacy_tables": ["app.TSsoDeletion"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("UNIQUEIDENTIFIER", "CustomerIdentificationId", "FK"),
            ("VARCHAR_60", "SsoCustomerNumber", ""),
            ("VARCHAR_80", "DeletedBy", ""),
            ("DATETIME2", "DeletedAt", ""),
            ("VARBINARY_32", "PayloadHash", ""),
        ],
        "note": "Append-only Ereignis für SSO-Löschungen mit revisionssicherem Hash.",
    },
    "RegistrationFeedbackEvents": {
        "kind": "New recommended ACID table",
        "source": "app.TRegistrationFeedback",
        "legacy_tables": ["app.TRegistrationFeedback"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("UNIQUEIDENTIFIER", "CustomerIdentificationId", "FK"),
            ("VARCHAR_80", "ExternalCustomerNumber", ""),
            ("VARCHAR_40", "Status", ""),
            ("DATETIME2", "ReceivedAt", ""),
            ("VARBINARY_32", "PayloadHash", ""),
        ],
        "note": "Append-only Feedbackprotokoll für externe Registrierungs- und Kundennummernrückmeldungen.",
    },
    "BillingRecords": {
        "kind": "New recommended ACID table",
        "source": "app.TBilling",
        "legacy_tables": ["app.TBilling"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("INT", "PaymentStatus", ""),
            ("VARCHAR_60", "DebtorNumber", ""),
            ("DECIMAL_18_2", "Amount", ""),
            ("CHAR_3", "Currency", ""),
            ("DATETIME2", "DueDate", ""),
            ("DATETIME2", "LastExportedAt", ""),
            ("VARCHAR_40", "ResolutionOutcome", ""),
            ("NVARCHAR_1000", "ResolutionRemark", ""),
            ("NVARCHAR_1000", "OpalError", ""),
            ("VARCHAR_50", "CreatedOrgId", ""),
            ("VARCHAR_50", "CreatedUserId", ""),
            ("INT", "SecurityDeposit", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Domain billing aggregate for amount, status, debtor, and export status. Spec chapter 19 (open collection cases): standardized {EXTERNAL-SYSTEM} error text, creation OrgID/UserID, and resolution domain courtesy vs. invoice with annotation; box security deposit per chapter 21.2.",
    },
    "BillingEvents": {
        "kind": "New recommended ACID table",
        "source": "app.TBilling_History",
        "legacy_tables": ["app.TBilling_History"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "BillingRecordId", "FK"),
            ("INT", "PaymentStatus", ""),
            ("VARCHAR_60", "EventType", ""),
            ("DECIMAL_18_2", "Amount", ""),
            ("VARCHAR_80", "ActorUserId", ""),
            ("DATETIME2", "CreatedAt", ""),
            ("VARBINARY_32", "PayloadHash", ""),
        ],
        "note": "Append-only Historie für Statuswechsel, Betragsänderungen und fachliche Löschereignisse.",
    },
    "BatchImports": {
        "kind": "New recommended ACID aggregate",
        "source": "app.TBatchOrder",
        "legacy_tables": ["app.TBatchOrder"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "DirectiveId", "FK"),
            ("NVARCHAR_260", "SourceFileName", ""),
            ("VARBINARY_32", "SourceChecksum", ""),
            ("VARCHAR_40", "Status", ""),
            ("VARCHAR_80", "CreatedBy", ""),
            ("DATETIME2", "CreatedAt", ""),
            ("DATETIME2", "CompletedAt", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Transaktionaler Kopf für SAM- und Massenimportläufe.",
    },
    "BatchImportRows": {
        "kind": "New recommended ACID table",
        "source": "app.TBatchOrder",
        "legacy_tables": ["app.TBatchOrder"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "BatchImportId", "FK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("INT", "RowNumber", ""),
            ("VARCHAR_40", "Status", ""),
            ("NVARCHAR_MAX", "RawPayload", ""),
            ("VARBINARY_32", "PayloadHash", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Zeilenebene des Imports; erfolgreiche Zeilen referenzieren den erzeugten Auftrag.",
    },
    "BatchImportErrors": {
        "kind": "New recommended ACID table",
        "source": "app.TBatchOrder",
        "legacy_tables": ["app.TBatchOrder"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "BatchImportRowId", "FK"),
            ("NVARCHAR_120", "FieldName", ""),
            ("VARCHAR_80", "ErrorCode", ""),
            ("NVARCHAR_500", "Message", ""),
            ("DATETIME2", "CreatedAt", ""),
        ],
        "note": "Validierungsfehler je Importzeile, ohne fehlerhafte Nutzdaten zu verlieren.",
    },
    "PrintJobs": {
        "kind": "New recommended ACID table",
        "source": "dbo.Import_LabelPrint",
        "legacy_tables": ["dbo.Import_LabelPrint"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "DirectiveId", "FK"),
            ("VARCHAR_40", "Status", ""),
            ("VARCHAR_40", "PrintReason", ""),
            ("NVARCHAR_260", "ProviderFileName", ""),
            ("VARCHAR_80", "RequestedBy", ""),
            ("DATETIME2", "RequestedAt", ""),
            ("DATETIME2", "HandedOffAt", ""),
            ("INT", "LabelSheetCount", ""),
            ("VARCHAR_10", "ZubaPostalCode", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Transactional print and label run with status and handoff time. Spec chapter 16.3.5: number of label sheets and 4-digit delivery-base postal code for the previous address; reprints appear as 'label reprint' in history and log data.",
    },
    "PrintJobOrders": {
        "kind": "New recommended ACID table",
        "source": "dbo.Import_LabelPrint",
        "legacy_tables": ["dbo.Import_LabelPrint"],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("UNIQUEIDENTIFIER", "PrintJobId", "FK"),
            ("UNIQUEIDENTIFIER", "OrderId", "FK"),
            ("INT", "EnvelopeNumber", ""),
            ("INT", "LabelCount", ""),
            ("INT", "PrintSequence", ""),
            ("ROWVERSION", "RowVersion", ""),
        ],
        "note": "Verbindet Druckläufe mit Aufträgen, Kuverts und Etikettenzahlen.",
    },
    "work.Lock": {
        "kind": "Existing C# infrastructure table",
        "source": "csharp/src/backend",
        "legacy_tables": [],
        "columns": [
            ("NVARCHAR_256", "Name", "PK"),
            ("UNIQUEIDENTIFIER", "Id", ""),
            ("DATETIME2", "ExpirationDate", ""),
            ("INT", "Duration", ""),
        ],
        "note": "Current C# worker-host lock table from the work schema. It is operational infrastructure, not a replacement for legacy business tables.",
    },
    "work.Queue": {
        "kind": "Existing C# infrastructure table",
        "source": "csharp/src/backend",
        "legacy_tables": [],
        "columns": [
            ("UNIQUEIDENTIFIER", "Id", "PK"),
            ("NVARCHAR_450", "QueueName", ""),
            ("NVARCHAR_MAX", "Payload", ""),
            ("DATETIME2", "QueuedAt", ""),
            ("INT", "DequeueCount", ""),
            ("INT", "State", ""),
        ],
        "note": "Current C# queue table from the work schema. Use it for technical message execution; do not rename batch-import or print business persistence to Queue.",
    },
    "work.ScheduledTask": {
        "kind": "Existing C# infrastructure table",
        "source": "csharp/src/backend",
        "legacy_tables": [],
        "columns": [
            ("NVARCHAR_450", "Id", "PK"),
            ("NVARCHAR_450", "WorkerId", ""),
            ("NVARCHAR_MAX", "Group", ""),
            ("NVARCHAR_MAX", "Description", ""),
            ("NVARCHAR_450", "Type", ""),
            ("DATETIMEOFFSET", "LastExecution", ""),
            ("DATETIMEOFFSET", "NextExecution", ""),
            ("INT", "ExecutionCount", ""),
            ("INT", "Status", ""),
            ("NVARCHAR_MAX", "Errors", ""),
            ("DATETIMEOFFSET", "LastErrorDate", ""),
            ("NVARCHAR_MAX", "Payload", ""),
            ("FLOAT", "Progress", ""),
            ("BIT", "Enabled", ""),
        ],
        "note": "Current C# scheduled-task table from the work schema. It may schedule processing, but it is not the domain table for SAM imports or print jobs.",
    },
    "__EFMigrationsHistory": {
        "kind": "Existing EF Core table",
        "source": "csharp/src/backend",
        "legacy_tables": [],
        "columns": [
            ("NVARCHAR_150", "MigrationId", "PK"),
            ("NVARCHAR_32", "ProductVersion", ""),
        ],
        "note": "Current EF Core schema-history table. It is included for completeness because the client schema diagram shows it, but it is not a {PROJECT-NAME} domain entity.",
    },
}

ACID_RECOMMENDED_RELATIONSHIPS = [
    ("Orders", "Directives", "Type", "lookup", "Orders.Type corresponds to the Directive catalog, but not as an FK column."),
    ("Directives", "Directives", "ParentId", "existing", "Directive subtypes already use the current C# Directives.ParentId self-reference."),
    ("Orders", "CustomerIdentifications", "CustomerIdentificationId", "existing", "Orders retain the customer/identity anchor."),
    ("Orders", "OrderOwnerPersons", "OwnerId", "existing", "Private order owners are in the existing TPC table OrderOwnerPersons."),
    ("Orders", "OrderOwnerCompanies", "OwnerId", "existing", "Company order owners are in the existing TPC table OrderOwnerCompanies."),
    ("Orders", "OrderRoutingAddresses", "OriginId", "existing", "Origin can be an existing OrderRoutingAddress."),
    ("Orders", "OrderRoutingAddresses", "DestinationId", "existing", "Destination can be an existing OrderRoutingAddress."),
    ("Orders", "OrderRoutingPostOfficeBoxes", "OriginId", "existing", "Origin can be an existing OrderRoutingPostOfficeBox."),
    ("Orders", "OrderRoutingPostOfficeBoxes", "DestinationId", "existing", "Destination can be an existing OrderRoutingPostOfficeBox."),
    ("OrderRoutingAddresses", "Addresses", "AddressId", "recommended", "OrderRoutingAddresses already stores AddressId; the current migration dropped the DB FK, so the ACID target should explicitly decide whether to enforce it."),
    ("Orders", "Lookups", "DropOffLocationCode", "lookup", "ASG order data validates the selected drop-off location against LookupType.AsgDropOffLocation; no separate DropOffLocations table."),
    ("Customers", "Orders", "DirectiveOrderId", "existing", "Person participants are already attached to Orders."),
    ("Companies", "Orders", "DirectiveOrderId", "existing", "Company participants are already attached to Orders."),
    ("ShipmentTypeGroups", "Directives", "DirectiveId", "existing", "Shipment type groups belong to the Directive catalog."),
    ("ShipmentTypes", "ShipmentTypeGroups", "ShipmentTypeGroupId", "existing", "Shipment types are attached to existing shipment type groups."),
    ("OrderShipmentTypeSelections", "Orders", "OrderId", "recommended", "Shipment type selection is attached to the order."),
    ("OrderShipmentTypeSelections", "ShipmentTypes", "ShipmentTypeId", "recommended", "Shipment type selection uses the existing catalog."),
    ("AuditLog", "Orders", "OrderId", "recommended", "Audit entries reference the affected order."),
    ("AuditLog", "Lookups", "ChangeReasonCode", "lookup", "Audit entries use the existing Lookups catalog for change reasons."),
    ("ParcelPostExceptions", "Directives", "DirectiveId", "recommended", "Exception rules are scoped by product."),
    ("PostOfficeBoxLocations", "ProviderLocations", "ProviderLocationId", "recommended", "Box locations are attached to the synchronized provider location."),
    ("PostOfficeBoxes", "PostOfficeBoxLocations", "LocationId", "recommended", "Post-office boxes belong to a location."),
    ("PostOfficeBoxes", "Lookups", "StatusCode", "lookup", "Post-office box status uses the existing Lookups catalog."),
    ("OrderRoutingPostOfficeBoxes", "PostOfficeBoxes", "PostOfficeBoxId", "recommended", "Post-box routing can reference the recommended box inventory."),
    ("SsoIdentifications", "Orders", "OrderId", "recommended", "SSO evidence can reference the order."),
    ("SsoIdentifications", "CustomerIdentifications", "CustomerIdentificationId", "recommended", "SSO evidence is attached to the identity anchor."),
    ("SsoDeletionEvents", "Orders", "OrderId", "recommended", "SSO deletion events can reference the order."),
    ("SsoDeletionEvents", "CustomerIdentifications", "CustomerIdentificationId", "recommended", "SSO deletion events are attached to the identity anchor."),
    ("RegistrationFeedbackEvents", "Orders", "OrderId", "recommended", "Registration feedback can reference the order."),
    ("RegistrationFeedbackEvents", "CustomerIdentifications", "CustomerIdentificationId", "recommended", "Registration feedback is attached to the identity anchor."),
    ("auth.RolePermissions", "auth.Roles", "RoleId", "existing", "Role permissions reference a role."),
    ("auth.RolePermissions", "auth.Permissions", "PermissionsId", "existing", "Role permissions reference a permission."),
    ("BillingRecords", "Orders", "OrderId", "recommended", "Billing data belongs to an order."),
    ("BillingEvents", "BillingRecords", "BillingRecordId", "recommended", "History is attached to the billing record."),
    ("BatchImports", "Directives", "DirectiveId", "recommended", "Import runs are product-scoped."),
    ("BatchImportRows", "BatchImports", "BatchImportId", "recommended", "Import rows belong to an import run."),
    ("BatchImportRows", "Orders", "OrderId", "recommended", "Successfully validated import rows reference the created order."),
    ("BatchImportErrors", "BatchImportRows", "BatchImportRowId", "recommended", "Errors are attached to the concrete import row."),
    ("PrintJobs", "Directives", "DirectiveId", "recommended", "Print runs are product-scoped."),
    ("PrintJobOrders", "PrintJobs", "PrintJobId", "recommended", "Print positions belong to a print run."),
    ("PrintJobOrders", "Orders", "OrderId", "recommended", "Print positions reference the order."),
    ("OrderDocuments", "Orders", "OrderId", "recommended", "Document metadata (FMS storage) is attached to the order and replaces the person DB storage (Spec chapter 17)."),
]

ACID_ER_DIAGRAM_SPECS = [
    {
        "id": "core-order-acid-er",
        "title": "ACID Target Model: Orders, Routing, ASG, And Recipients",
        "description": "Recommended relational tables around orders, existing participants, routing, shipment types, and audit. Existing C# tables are used where present; ASG drop-off permissions remain in Lookups.",
        "tables": [
            "Orders",
            "Directives",
            "CustomerIdentifications",
            "Addresses",
            "Customers",
            "Companies",
            "OrderOwnerPersons",
            "OrderOwnerCompanies",
            "ShipmentTypeGroups",
            "ShipmentTypes",
            "Lookups",
            "OrderRoutingAddresses",
            "OrderRoutingPostOfficeBoxes",
            "OrderShipmentTypeSelections",
            "AuditLog",
            "ParcelPostExceptions",
            "OrderDocuments",
        ],
    },
    {
        "id": "postbox-provider-acid-er",
        "title": "ACID Target Model: Postbox, Location, And Provider",
        "description": "Recommended tables for postbox locations, postbox inventory, provider locations, and the existing C# postbox-routing marker. Postbox status values use Lookups.",
        "tables": [
            "Orders",
            "Addresses",
            "Lookups",
            "OrderRoutingAddresses",
            "OrderRoutingPostOfficeBoxes",
            "ProviderLocations",
            "PostOfficeBoxLocations",
            "PostOfficeBoxes",
        ],
    },
    {
        "id": "identity-billing-acid-er",
        "title": "ACID Target Model: Identity, Authorization, Billing, And Audit",
        "description": "Recommended tables for SSO evidence, registration feedback, role parity, billing, status history, and audit-safe events. Existing status and lookup surfaces are reused.",
        "tables": [
            "Orders",
            "CustomerIdentifications",
            "Lookups",
            "auth.Roles",
            "auth.Permissions",
            "auth.RolePermissions",
            "SsoIdentifications",
            "SsoDeletionEvents",
            "RegistrationFeedbackEvents",
            "BillingRecords",
            "BillingEvents",
            "AuditLog",
        ],
    },
    {
        "id": "import-print-acid-er",
        "title": "ACID Target Model: Batch Import, Print, And Labels",
        "description": "Recommended tables for CSV/SAM imports, import errors, print runs, print positions, and form numbers.",
        "tables": [
            "Orders",
            "Directives",
            "BatchImports",
            "BatchImportRows",
            "BatchImportErrors",
            "PrintJobs",
            "PrintJobOrders",
        ],
    },
]

COMPLETE_ACID_ER_DIAGRAM_ID = "complete-acid-er"
ACID_COMPLETE_ONLY_TABLES = [
    "work.Lock",
    "work.Queue",
    "work.ScheduledTask",
    "__EFMigrationsHistory",
]


def complete_acid_er_table_names() -> list[str]:
    seen = set()
    table_names = []
    for spec in ACID_ER_DIAGRAM_SPECS:
        for table_name in spec["tables"]:
            if table_name in ACID_RECOMMENDED_TABLES and table_name not in seen:
                seen.add(table_name)
                table_names.append(table_name)
    for table_name in ACID_COMPLETE_ONLY_TABLES:
        if table_name in ACID_RECOMMENDED_TABLES and table_name not in seen:
            seen.add(table_name)
            table_names.append(table_name)
    return table_names

FUNCTION_BUSINESS_GROUPS = [
    {
        "name": "Print and datafile helpers",
        "patterns": ["etikett", "druck", "kuvert"],
        "pdf_terms": ["Datenübermittlung an Druckdienstleister", "K-Satz", "N-Satz", "D-Satz", "E-Satz", "example-order-labels"],
        "logic": (
            "Build the legacy print-provider datafile or values used by it: K rows for envelopes, "
            "N rows for orders, D/E rows for persons/authorized recipients, print dates, label-sheet "
            "counts, and orders-per-envelope limits."
        ),
        "review": "Treat these as interface logic: verify every generated field against the Print Spec Document before reproducing it in C#.",
    },
    {
        "name": "Address, PAC, routing, and branch resolution",
        "patterns": ["anschrift", "adresse", "pac", "standort", "zube", "dienststelle", "basenmanager", "lkz", "plz"],
        "pdf_terms": ["Adresse", "PAC", "Postfach", "Dienststelle", "Zustellbasis", "PLZ", "LKZ"],
        "logic": (
            "Resolve or format addresses and operational routing data. These functions prefer PAC/provider "
            "lookups where possible, fall back to stored legacy destination rows when needed, and format output "
            "for search, reports, exports, or print."
        ),
        "review": "Confirm future ownership of PAC/address resolution; several functions depend on external provider/CLR services.",
    },
    {
        "name": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
        "patterns": ["suche", "search", "pabd", "person", "detail", "dwg", "poquery"],
        "pdf_terms": ["Suchmaske", "Trefferliste", "{EXTERNAL-SEARCH-API}", "FUZZY", "Empfänger", "Person"],
        "logic": (
            "Connect legacy orders to person data and search results. This includes CLR wrappers around external "
            "person search/get-person calls, search-result shaping, scoring, and XML detail generation."
        ),
        "review": "Search API behavior and person lookup semantics must be confirmed at integration level.",
    },
    {
        "name": "Validity, current-order filters, and eligibility",
        "patterns": ["gueltig", "gültig", "aktuell", "ohnepac"],
        "pdf_terms": ["Gültig ab", "Gültig bis", "Storno", "Widerruf", "Suchmaske"],
        "logic": (
            "Calculate whether an order is future-valid, currently valid, expired, cancelled/revoked, "
            "or eligible for downstream selection such as print and household-database exports."
        ),
        "review": "Compare date/state transitions with the official spec before changing C# cancellation or validity behavior.",
    },
    {
        "name": "Reports and exports",
        "patterns": ["report", "bericht", "export", "historie", "vacation", "postvollmacht", "wun", "temporder"],
        "pdf_terms": ["History", "Logdatenanalyse", "Bericht", "Suche erfolgreich", "Postvollmacht", "VacationBox"],
        "logic": (
            "Project order, destination, person, validity, and log data into report/export result sets. "
            "These functions are read models for operational reports, history views, and data subject reports."
        ),
        "review": "Separate regulatory/reporting requirements from legacy convenience reports before adding C# endpoints.",
    },
    {
        "name": "Import and transformation",
        "patterns": ["import", "split2xml"],
        "pdf_terms": ["BatchOrder", "CSV", "Import"],
        "logic": (
            "Transform imported or old-format detail data into XML structures consumed by the legacy save path."
        ),
        "review": "Validate against official import/BatchOrder requirements and real import examples.",
    },
    {
        "name": "Configuration and external master-data wrappers",
        "patterns": ["applikationsparameter", "provider", "clr_", "basenmanager", "amtlich", "poquery"],
        "pdf_terms": ["Handbücher", "technische Daten", "Berechtigungskonzept", "Druckdienstleister"],
        "logic": (
            "Expose application parameters or external master-data lookups to SQL. These are integration boundaries, "
            "not simple local calculations."
        ),
        "review": "Confirm which provider services remain authoritative in the new C# architecture.",
    },
]

FUNCTION_ROLE_HINTS = {
    "filterbycurrentorders": "Selects currently relevant legacy orders for downstream consumers, including type code, form number, validity dates, responsible branch, PAC, and old/new address fields.",
    "filterbyorderdestination": "Looks up recent legacy order summaries for a destination PAC and includes formatted form number and computed validity status.",
    "filterbyorderlabels": "Builds the K and N print-file rows and D-row skeletons for label/envelope printing, including envelope counters, print reason, old/new address, label counts, ASG location, barcode, and source channel.",
    "filterbyorderwithoutpac": "Finds active/current orders whose destination PAC is missing from the reporting address source, with a seven-day pre-validity lead time.",
    "filterbytstandort": "Filters active branch/location master data by branch id, postal code, and unit group such as Filialnetz, Distribution, or KEP.",
    "filterby_dwg": "Wraps the external search API fuzzy/person search for a DWG-style search result, joining found persons back to legacy detail/head rows and formatting old/new addresses.",
    "getcurrentorders": "Returns active legacy orders for the household database/export style use case, including responsible branch, PAC, addresses, and product code derivation.",
    "getaktuellepostfachstandorte": "Returns current postbox locations and availability/occupancy information for postbox-related workflows.",
    "getanschrift": "Formats an address string. It tries PAC/provider address lookup first, falls back to stored legacy destination rows, supports old/new address selection, separators, length limits, and country names.",
    "getanschrift_export": "Returns address components as rows for export/reporting, using the same PAC/provider and stored-destination fallback ideas as GetAnschrift.",
    "getanzahletiketten": "Calculates how many label sheets an order needs based on validity end date, cancellation state, and product label-print eligibility, capped at three.",
    "getbriefdienststelle": "Resolves the responsible letter-mail branch for an order or supplied address/PAC inputs.",
    "getbriefzubego": "Resolves delivery district/group-order information used for print sorting and operational routing.",
    "getdetail": "Builds XML detail output for an order by combining legacy detail rows with external search API/CLR person data.",
    "getdruckdatum": "Computes the effective print date from application parameters and the requested date/current date.",
    "geterfasser": "Returns the latest creator/change-user information for an order as XML from the log table and change-reason lookup.",
    "getordervalidity": "Maps order/person validity dates and cancellation/revocation date to status codes: future, current, expired, cancelled/revoked, or unknown.",
    "getitemsperenvelope": "Reads the configured number of order items per envelope for print batching.",
    "import_split2xml": "Transforms old/imported detail strings into XML detail nodes for the legacy import/save workflow.",
    "orderhistory": "Builds an order history list across successor/predecessor order chains and joins log entries with change reasons.",
    "ordersearch": "Searches legacy orders directly or through fuzzy/external search API and returns ranked result-list-style rows with person, order, address, validity, and branch fields.",
    "poquery": "Calls the external provider service to resolve PO object metadata such as descriptions and cost center.",
    "tempgetperson_old": "Legacy/old helper for retrieving person data; keep as historical evidence until call sites are known.",
    "clr_extperson_getperson": "CLR wrapper for direct external search API person retrieval.",
    "clr_extperson_getPerson_tran": "CLR wrapper for transaction-based external search API person retrieval used by print processing.",
    "clr_extperson_searchorder": "CLR wrapper for external search API person search scoped to legacy search criteria.",
    "fn_clr_basenmanager_plz": "CLR wrapper for postal-code master data with addressability/postbox/branch flags.",
    "fn_clr_amtlich_lkz": "CLR wrapper for official country-code data used when formatting foreign addresses.",
    "fn_clr_basenmanager_zd": "Provider wrapper for delivery-base, district, group, cost-center, and routing-order data by PAC.",
    "fn_clr_extperson_search": "CLR wrapper for external search API person search returning scoring and person identity fields.",
    "fn_getetikettenanzahl": "Returns label-sheet count and responsible branch for a given order, capped at three and zeroed for expired/cancelled orders.",
    "getadresse4pac": "Provider wrapper for resolving structured address data by PAC.",
    "getapplikationsparameter": "Provider wrapper for reading application parameters used by print, defaults, and configuration-driven behavior.",
    "getorder_dsrreport": "Returns high-level orders for a person, likely for data subject/reporting views.",
    "getorder_dsrreportdetails": "Returns detailed order, destination, and cancellation fields for a person, likely for data subject/reporting views.",
    "get_location4plz_order": "Provider wrapper for resolving a branch/location by postal code, date, and type.",
    "report_validorders": "Report rowset for valid legacy orders with person XML and old/new addresses.",
    "report_validorders_export": "Export rowset for valid legacy orders with addresses and validity labels.",
    "report_gueltigepostvollmachten": "Report rowset for valid postal authorizations.",
    "report_gueltigewun": "Report rowset for valid WUN/Wunschfiliale legacy data.",
    "report_temporders": "Report rowset for temporary legacy orders.",
    "report_vacationorders": "Report rowset for holiday/VacationBox legacy orders.",
}

FUNCTION_GROUP_OVERRIDES = {
    "filterbycurrentorders": "Validity, current-order filters, and eligibility",
    "filterbyorderdestination": "Validity, current-order filters, and eligibility",
    "filterbyorderlabels": "Print and datafile helpers",
    "filterbyorderwithoutpac": "Validity, current-order filters, and eligibility",
    "filterby_dwg": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "getcurrentorders": "Validity, current-order filters, and eligibility",
    "getaktuellepostfachstandorte": "Address, PAC, routing, and branch resolution",
    "getanschrift": "Address, PAC, routing, and branch resolution",
    "getanschrift_export": "Address, PAC, routing, and branch resolution",
    "getanzahletiketten": "Print and datafile helpers",
    "getbriefdienststelle": "Address, PAC, routing, and branch resolution",
    "getbriefzubego": "Address, PAC, routing, and branch resolution",
    "getdetail": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "getdruckdatum": "Print and datafile helpers",
    "geterfasser": "Reports and exports",
    "getordervalidity": "Validity, current-order filters, and eligibility",
    "getitemsperenvelope": "Print and datafile helpers",
    "import_split2xml": "Import and transformation",
    "orderhistory": "Reports and exports",
    "ordersearch": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "poquery": "Configuration and external master-data wrappers",
    "tempgetperson_old": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "clr_extperson_getperson": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "clr_extperson_getPerson_tran": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "clr_extperson_searchorder": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "fn_clr_basenmanager_plz": "Configuration and external master-data wrappers",
    "fn_clr_amtlich_lkz": "Configuration and external master-data wrappers",
    "fn_clr_basenmanager_zd": "Configuration and external master-data wrappers",
    "fn_clr_extperson_search": "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup",
    "fn_getetikettenanzahl": "Print and datafile helpers",
    "getadresse4pac": "Configuration and external master-data wrappers",
    "getapplikationsparameter": "Configuration and external master-data wrappers",
    "getorder_dsrreport": "Reports and exports",
    "getorder_dsrreportdetails": "Reports and exports",
    "get_location4plz_order": "Configuration and external master-data wrappers",
    "report_validorders": "Reports and exports",
    "report_validorders_export": "Reports and exports",
    "report_gueltigepostvollmachten": "Reports and exports",
    "report_gueltigewun": "Reports and exports",
    "report_temporders": "Reports and exports",
    "report_vacationorders": "Reports and exports",
}

DOMAIN_TERMS = [
    {
        "topic": "{EXTERNAL-SEARCH-API} / person and address database",
        "terms": ["{EXTERNAL-SEARCH-API}", "{ExternalPersonEntity}", "{ExternalPersonEntity}Reporting", "PAC"],
        "review": "Map every external search API/PAC dependency to the future C# integration boundary.",
    },
    {
        "topic": "IDM / SSO identity",
        "terms": ["IDM", "SSO", "SSOKundennr", "SSOIdBenutzer", "TSsoDeletion"],
        "review": "Clarify whether IDM remains upstream identity source or only legacy audit data.",
    },
    {
        "topic": "User and action logging",
        "terms": ["UUser", "SUser", "IP", "Login", "TLog", "WriteLog", "Logdaten"],
        "review": "Verify required audit fields for every create, update, and cancellation flow.",
    },
    {
        "topic": "Form and order types",
        "terms": ["Formular", "Formularnr", "AuftragTyp", "Vorausverfügung", "{PROJECT-NAME}"],
        "review": "Build the product/type catalog from official docs first; use SQL codes as evidence.",
    },
    {
        "topic": "Validity and cancellation",
        "terms": ["Gueltig", "Gültig", "Storno", "Storniert", "Aenderung", "Änderung"],
        "review": "Extract date and cancellation state transitions from procedures and official specification rules.",
    },
    {
        "topic": "Destination and address handling",
        "terms": ["Adresse", "Destination", "Postfach", "Postlagernd", "Abstell", "VacationBox"],
        "review": "Separate old address, new address, postbox, postlagernd, and parcel redirection rules.",
    },
    {
        "topic": "Fuzzy search",
        "terms": ["Fuzzy", "Suche", "Suchmaske", "OrderSearch", "FilterBy_DWG"],
        "review": "Identify what is DB behavior versus external search API behavior.",
    },
    {
        "topic": "BatchOrder / bulk import",
        "terms": ["BatchOrder", "CSV", "Import", "NID", "NAD"],
        "review": "Compare SQL import helpers with official CSV/import sections.",
    },
    {
        "topic": "Print, labels, and envelopes",
        "terms": ["Etikett", "Druck", "Kuvert", "Vormerkkarten", "Druckdienstleister"],
        "review": "Map pipe-delimited output fields to the Druck/Kuvertierung specification.",
    },
    {
        "topic": "Billing and open collection cases",
        "terms": ["Verrechnung", "Inkasso", "Preis", "TotalAmountPaid", "Offene Inkassofälle"],
        "review": "Trace when billing records are created, changed, hidden, or exported.",
    },
    {
        "topic": "Postbox master data",
        "terms": ["PostfachStammdaten", "PostfachStandort", "Offene Fächer", "Schließfächer"],
        "review": "Compare postbox inventory and status semantics to specpostbox sections.",
    },
    {
        "topic": "Permissions and roles",
        "terms": ["Berechtigung", "GRANT", "ROLE", "USER", "Permission"],
        "review": "Map SQL permissions to application roles; do not expose DB roles directly in C# design.",
    },
]

PRINT_FIELDS = [
    ("K1", "DST_BEZ1", ["DST_BEZ", "Dienststelle"]),
    ("K2", "DST_STRASSE", ["DST_STRASSE", "Strasse", "Straße"]),
    ("K3", "DST_ORT", ["DST_ORT", "Ort"]),
    ("K4", "K_AK", ["Akt_Kuvert", "KuvertNr"]),
    ("K5", "K_GES", ["Ges_Kuvert", "KuvertAnzahl"]),
    ("K6", "APP_AK_MIN", ["nk_akt"]),
    ("K7", "APP_AK_MAX", ["nk_anz"]),
    ("K8", "APP_MAX", ["nk_anz"]),
    ("N1", "RAYON", ["Rayon", "Zube", "zube"]),
    ("N2", "APP_FNR", ["AppFnr", "Formularnr", "Formularnummer"]),
    ("N3", "GUELTIG_AB", ["GueltigAb", "Gültig"]),
    ("N4", "GUELTIG_BIS", ["GueltigBis"]),
    ("N5", "INFO", ["NEU", "STORNO", "AENDERUNG", "ÄNDERUNG", "NACHDRUCK"]),
    ("N6", "ALT_STRASSE", ["GetAnschrift", "Alt", "Von"]),
    ("N7", "ALT_ORT", ["GetAnschrift", "Von"]),
    ("N8", "NEU_STRASSE", ["GetAnschrift", "Nach"]),
    ("N9", "NEU_ORT", ["GetAnschrift", "Nach"]),
    ("N10", "NEU_LAND", ["LKZ", "Land"]),
    ("N11", "SAUSED", ["SAUsed"]),
    ("N12", "CO", [" co", ".co", "[co]"]),
    ("N13", "ANZ_ET", ["GetLabelCount", "AnzEtiketten"]),
    ("N14", "ANZ_VM", ["GetItemsPerEnvelope", "Vormerk"]),
    ("N15", "STORNO_AB", ["StornoAm"]),
    ("N16", "AUFTRAG_ID", ["AuftragID_Extern"]),
    ("N17", "TELEFON", ["Telefonnr", "Vorwahl"]),
    ("N18", "ZUSTELLUNG_VON", ["Zustellung", "GueltigAb"]),
    ("N19", "ZUSTELLUNG_BIS", ["Zustellung", "GueltigBis"]),
    ("N20", "FORMULARNUMMER", ["Formularnr", "AppFnr"]),
    ("N21", "ABSTELLORT", ["Abstellort"]),
    ("N22", "BARCODE_ORDER", ["Barcode", "OrderHead_ID"]),
    ("N23", "HERKUNFT", ["Herkunft"]),
    ("D1", "NAME", ["Familienname", "Vorname", "Firmenname", "Name"]),
    ("D2", "GEBDATUM", ["Geburtsdatum"]),
    ("D3", "TITEL", ["Titel"]),
    ("D4", "ANREDE", ["Anrede"]),
    ("E1", "NAME", ["Familienname", "Vorname", "Firmenname", "Name"]),
    ("E2", "GEBDATUM", ["Geburtsdatum"]),
    ("E3", "STRASSE", ["Strasse", "Straße"]),
    ("E4", "ORT", ["Ort", "PLZ"]),
]

SEMANTIC_DOC_MAP = [
    {
        "official_topic": "External search API address/person checks and storage",
        "doc_terms": ["{EXTERNAL-SEARCH-API}", "FUZZY", "Adressen", "Empfänger"],
        "sql_terms": ["{ExternalPersonEntity}", "{ExternalPersonEntity}Reporting", "clr_{external}_person", "PAC"],
        "status": "Strong SQL evidence",
        "action": "Design explicit C# boundary for external search API/PAC lookups and person persistence.",
    },
    {
        "official_topic": "IDM and user traceability",
        "doc_terms": ["Identity Manager", "U-User", "S-User", "IP-Adresse"],
        "sql_terms": ["UUser", "IP", "TLog", "WriteLog", "SSOKundennr"],
        "status": "Partial SQL evidence",
        "action": "Confirm IDM/SSO source and required audit fields with client.",
    },
    {
        "official_topic": "Form types and new {PROJECT-NAME} product variants",
        "doc_terms": ["PF", "REC", "PUM", "ASG", "PV", "BatchOrder"],
        "sql_terms": ["TOrderType", "CodeDruck", "P_STORE_ORDER_XML", "TBatchOrder"],
        "status": "Strong SQL evidence",
        "action": "Extract product/type catalog from official specification, then compare SQL lookup values if data is available.",
    },
    {
        "official_topic": "Validity, change, cancellation, incompatibility",
        "doc_terms": ["Gültig ab", "Gültig bis", "Storno", "Unvereinbarkeitsregeln"],
        "sql_terms": ["GueltigAb", "GueltigBis", "StornoAm", "P_CHK_ORDER", "P_CHK_RECIPIENT"],
        "status": "Requires detailed procedure review",
        "action": "Manually review validation/check procedures against specsections 11 and 14.",
    },
    {
        "official_topic": "Search and Trefferliste",
        "doc_terms": ["Suchmaske", "Trefferliste", "Erweiterte Suche"],
        "sql_terms": ["OrderSearch", "FilterBy_DWG", "OrderHistory", "report_"],
        "status": "Strong SQL evidence",
        "action": "Classify search fields, filters, and report downloads before extending C# search behavior.",
    },
    {
        "official_topic": "Postbox master data and status reports",
        "doc_terms": ["PF-Stammdaten", "Offene Fächer", "Schließfächer", "Statusauswertungen"],
        "sql_terms": ["TBoxMasterData", "TBoxLocation", "TBoxStatus"],
        "status": "Strong SQL evidence",
        "action": "Extract postbox state model and confirm whether C# will own or consume it.",
    },
    {
        "official_topic": "Druckdienstleister file, envelopes, labels",
        "doc_terms": ["Kuvert", "example-order-labels", "K-Satz", "N-Satz", "D-Satz", "E-Satz"],
        "sql_terms": ["LabelPrint", "FilterByOrderLabels", "GetItemsPerEnvelope", "GetAnschrift"],
        "status": "Strong SQL evidence",
        "action": "Treat the print datafile as a formal interface and regression-test every field.",
    },
    {
        "official_topic": "Billing and open collection cases",
        "doc_terms": ["Offene Inkassofälle", "Debitorenfeld"],
        "sql_terms": ["TBilling", "Inkasso", "Produkt_ID", "TotalAmountPaid"],
        "status": "Partial SQL evidence",
        "action": "Confirm billing source of truth and lifecycle before changing C# flows.",
    },
    {
        "official_topic": "Permissions concept",
        "doc_terms": ["Berechtigungskonzept", "wer darf was machen"],
        "sql_terms": ["TPermission", "Security", "RoleMemberships", "GRANT"],
        "status": "SQL evidence exists",
        "action": "Map application roles separately from SQL users/grants.",
    },
]

MANUAL_REVIEW_QUEUE = [
    {
        "area": "Core save/import workflow",
        "objects": [
            "app.P_STORE_ORDER_XML",
            "app.SetDestination",
            "app.SetDetail",
            "app.SetShipmentType",
            "app.setBoxMasterData",
        ],
        "why": "Persists XML into the core head/detail/destination/type tables and contains state-change side effects.",
    },
    {
        "area": "Validation and incompatibility rules",
        "objects": ["app.P_CHK_ORDER", "app.P_CHK_RECIPIENT", "app.GetOrderValidity"],
        "why": "Likely SQL evidence for specvalidation, recipient, and incompatibility behavior.",
    },
    {
        "area": "Print/export interface",
        "objects": [
            "app.LabelPrint",
            "app.FilterByOrderLabels",
            "app.GetAddress",
            "app.GetPrintDate",
            "app.GetItemsPerEnvelope",
            "app.Export_KEP",
        ],
        "why": "Maps directly to the official Druck- und Kuvertierungsanforderungen document.",
    },
    {
        "area": "Search and external search API integration",
        "objects": [
            "app.OrderSearch",
            "app.FilterByFuzzy",
            "app.GetDetail",
            "app.clr_extperson_searchOrder",
            "app.clr_extperson_getPerson",
        ],
        "why": "Contains fuzzy/person lookup behavior that probably depends on external search API services.",
    },
    {
        "area": "Deletion, cancellation, and audit trail",
        "objects": [
            "app.deleteOrder",
            "app.deleteOrderFuzzy",
            "app.WriteLog",
            "dbo.TLog",
            "app.TSsoDeletion",
        ],
        "why": "Carries audit, cancellation, history, and hidden cleanup behavior.",
    },
    {
        "area": "Postbox and billing",
        "objects": [
            "app.TBoxMasterData",
            "app.TBoxLocation",
            "app.TBilling",
            "app.TBilling_History",
        ],
        "why": "Maps to specpostbox management, open collection cases, and billing fields.",
    },
    {
        "area": "Security and operations",
        "objects": ["Security/Permissions.sql", "Security/RoleMemberships.sql", "Database Triggers/DBTR_Log_Schema_Changes.sql"],
        "why": "Reveals operational assumptions, DB users, schema-change logging, and access boundaries.",
    },
]


@dataclass
class SqlFile:
    path: Path
    rel: str
    text: str
    category: str
    in_sqlproj: bool
    generated: bool
    definitions: list[dict] = field(default_factory=list)
    columns: list[dict] = field(default_factory=list)
    fks: list[dict] = field(default_factory=list)
    indexes: int = 0
    stats: int = 0
    grants: int = 0
    mutations: Counter = field(default_factory=Counter)
    dependencies: set[str] = field(default_factory=set)
    external_refs: set[str] = field(default_factory=set)
    risk_flags: list[str] = field(default_factory=list)
    doc_hits: list[str] = field(default_factory=list)

    @property
    def loc(self) -> int:
        return len(self.text.splitlines())

    @property
    def primary_object(self) -> str:
        for definition in self.definitions:
            if definition["kind"] not in {"GRANT", "ALTER ROLE"}:
                return definition["name"]
        return Path(self.rel).stem

    @property
    def primary_kind(self) -> str:
        for definition in self.definitions:
            if definition["kind"] not in {"GRANT", "ALTER ROLE"}:
                return definition["kind"]
        return self.category


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    return path.read_text(errors="replace")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.casefold()


def compact(value: str, limit: int = 180) -> str:
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def run_git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=str(cwd), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def parse_sqlproj_build_files() -> set[str]:
    if not SQLPROJ.exists():
        return set()
    tree = ET.parse(SQLPROJ)
    ns = {"msb": "http://schemas.microsoft.com/developer/msbuild/2003"}
    includes = set()
    for node in tree.findall(".//msb:Build", ns):
        include = node.attrib.get("Include", "").replace("\\", "/")
        if include:
            includes.add((SQL_ROOT / include).relative_to(SQL_ROOT).as_posix())
    return includes


def category_from_path(path: Path) -> str:
    parts = [part.casefold() for part in path.parts]
    mapping = [
        ("tables", "Table"),
        ("stored procedures", "Stored procedure"),
        ("functions", "Function"),
        ("views", "View"),
        ("sequences", "Sequence"),
        ("synonyms", "Synonym"),
        ("security", "Security"),
        ("database triggers", "Database trigger"),
    ]
    for key, label in mapping:
        if key in parts:
            return label
    if "obj" in parts:
        return "Generated SQL"
    return "Other SQL"


def clean_object_name(raw_name: str, inferred_schema: str | None = None) -> str:
    raw_name = raw_name.strip().rstrip(";,(")
    raw_name = re.sub(r"\s+ON\s+.*$", "", raw_name, flags=re.I)
    raw_name = raw_name.replace("[", "").replace("]", "").replace('"', "")
    raw_name = raw_name.strip()
    if "." not in raw_name and inferred_schema:
        raw_name = f"{inferred_schema}.{raw_name}"
    return raw_name


def inferred_schema(path: Path) -> str | None:
    rel_parts = path.relative_to(SQL_ROOT).parts
    if rel_parts and rel_parts[0] in {"app", "dbo", "ref"}:  # EXAMPLE schema folder set — adjust per project
        return rel_parts[0]
    return None


CREATE_PATTERN = re.compile(
    r"\bCREATE\s+(?:(?:OR\s+ALTER|OR\s+REPLACE)\s+)?"
    r"(?P<kind>TABLE|PROCEDURE|PROC|FUNCTION|VIEW|SYNONYM|SEQUENCE|TRIGGER|USER|ROLE|ASSEMBLY)\s+"
    r"(?P<name>(?:\[[^\]]+\]|\w+)(?:\s*\.\s*(?:\[[^\]]+\]|\w+))?)",
    re.I,
)


def extract_definitions(sql_file: SqlFile) -> list[dict]:
    definitions = []
    schema = inferred_schema(sql_file.path)
    for match in CREATE_PATTERN.finditer(sql_file.text):
        kind = match.group("kind").upper()
        if kind == "PROC":
            kind = "PROCEDURE"
        name = clean_object_name(match.group("name"), schema)
        definitions.append({"kind": kind, "name": name, "line": line_number(sql_file.text, match.start())})
    for match in re.finditer(r"\bALTER\s+ROLE\s+(\[[^\]]+\]|\w+)\s+ADD\s+MEMBER\s+(\[[^\]]+\]|\w+)", sql_file.text, re.I):
        definitions.append(
            {
                "kind": "ALTER ROLE",
                "name": clean_object_name(match.group(1)),
                "line": line_number(sql_file.text, match.start()),
            }
        )
    if not definitions and "Security" in sql_file.rel:
        definitions.append({"kind": "SECURITY", "name": Path(sql_file.rel).stem, "line": 1})
    return definitions


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def extract_table_columns_and_fks(text: str) -> tuple[list[dict], list[dict]]:
    columns = []
    fks = []
    table_match = re.search(r"\bCREATE\s+TABLE\s+(?:\[[^\]]+\]|\w+)\s*\.\s*(?:\[[^\]]+\]|\w+)\s*\(", text, re.I)
    if not table_match:
        return columns, fks
    start = table_match.end()
    remainder = text[start:]
    end_match = re.search(r"\n\)\s*;", remainder)
    block = remainder[: end_match.start()] if end_match else remainder
    primary_key_columns = set()
    for pk_match in re.finditer(r"PRIMARY\s+KEY(?:\s+\w+)*\s*\(([^)]*)\)", block, re.I | re.S):
        primary_key_columns.update(re.findall(r"\[([^\]]+)\]", pk_match.group(1)))
    for line in block.splitlines():
        stripped = line.strip().rstrip(",")
        col_match = re.match(r"\[([^\]]+)\]\s+(.+)", stripped)
        if col_match and not stripped.upper().startswith("[CONSTRAINT"):
            column_name = col_match.group(1)
            column_type = col_match.group(2)
            column_type = re.split(r"\s+CONSTRAINT\s+|\s+DEFAULT\s+|\s+NOT\s+NULL|\s+NULL", column_type, flags=re.I)[0]
            columns.append(
                {
                    "name": column_name,
                    "type": " ".join(column_type.split()),
                    "is_primary_key": column_name in primary_key_columns,
                }
            )
        fk_match = re.search(
            r"CONSTRAINT\s+\[?([^\]\s]+)\]?\s+FOREIGN\s+KEY\s+\(\[([^\]]+)\]\)\s+REFERENCES\s+\[([^\]]+)\]\.\[([^\]]+)\]\s+\(\[([^\]]+)\]\)",
            stripped,
            re.I,
        )
        if fk_match:
            fks.append(
                {
                    "name": fk_match.group(1),
                    "column": fk_match.group(2),
                    "target": f"{fk_match.group(3)}.{fk_match.group(4)}",
                    "target_column": fk_match.group(5),
                }
            )
    return columns, fks


def extract_external_refs(text: str) -> set[str]:
    refs = set()
    for match in re.finditer(r"\b[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_+]*", text):
        value = match.group(0)
        first = value.split(".")[0]
        if first.upper() not in KNOWN_SCHEMAS:
            refs.add(value)
    for match in re.finditer(r"\b(ExtPersonDb|ExtPersonReporting|ExtPersonImp|ExtBaseManager|extpersonreporting)\b", text, re.I):
        refs.add(match.group(1))
    return refs


def add_risk_flags(sql_file: SqlFile) -> list[str]:
    t = sql_file.text
    flags = []
    checks = [
        ("External DB/schema dependency", r"\b(ExtPersonDb|ExtPersonReporting|ExtPersonImp|ExtBaseManager|extpersonreporting)\b"),
        ("CLR dependency", r"\bEXTERNAL\s+NAME\b|\bclr_"),
        ("Dynamic SQL", r"\bsp_executesql\b|\bEXEC\s*\("),
        ("XML parsing/persistence", r"\bOPENXML\b|\bsp_xml_preparedocument\b|\bXML\b"),
        ("Mutates state", r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE)\b"),
        ("Security/grants", r"\b(GRANT|CREATE\s+USER|ALTER\s+ROLE|CREATE\s+ROLE)\b"),
        ("Trigger side effects", r"\bCREATE\s+TRIGGER\b"),
        ("NOLOCK reads", r"\bWITH\s*\(\s*NOLOCK\s*\)|\bNOLOCK\b"),
        ("Manual sequence/autonumber", r"\bTAutoNummer\b|\bsp_GetAutoNummer\b|\bSEQUENCE\b"),
        ("Generated artifact", r"\.generated\.sql|/obj/|\\obj\\"),
    ]
    for label, pattern in checks:
        if re.search(pattern, t, re.I) or (label == "Generated artifact" and sql_file.generated):
            flags.append(label)
    return flags


def term_count(text: str, term: str) -> int:
    n_text = normalize(text)
    n_term = normalize(term)
    if not n_term.strip():
        return 0
    return n_text.count(n_term)


def first_line_for_any(text: str, terms: Iterable[str]) -> int | None:
    n_terms = [normalize(term) for term in terms]
    for index, line in enumerate(text.splitlines(), start=1):
        n_line = normalize(line)
        if any(term in n_line for term in n_terms):
            return index
    return None


def snippet_for_term(text: str, term: str, limit: int = 190) -> str:
    n_text = normalize(text)
    n_term = normalize(term)
    index = n_text.find(n_term)
    if index < 0:
        return ""
    start = max(0, index - limit // 2)
    end = min(len(text), index + len(term) + limit // 2)
    snippet = " ".join(text[start:end].split())
    return snippet if len(snippet) <= limit else snippet[: limit - 1] + "..."


def content_start_page(pdf_name: str) -> int:
    if pdf_name.startswith(SPEC_DOCUMENT_1_PREFIX):
        return 6
    if pdf_name.startswith(SPEC_DOCUMENT_2_PREFIX):
        return 4
    return 1


def find_pdf_refs(pdfs: list[dict], terms: Iterable[str], limit: int = 6, min_page: int | None = None) -> list[dict]:
    refs = []
    seen = set()
    for pdf in pdfs:
        start_page = min_page if min_page is not None else content_start_page(pdf["name"])
        for page in pdf.get("pages_text", []):
            if page["page"] < start_page:
                continue
            page_text = page["text"]
            matched_terms = [term for term in terms if term_count(page_text, term)]
            if not matched_terms:
                continue
            key = (pdf["name"], page["page"])
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                {
                    "pdf": pdf["name"],
                    "page": page["page"],
                    "terms": matched_terms[:5],
                    "snippet": snippet_for_term(page_text, matched_terms[0]),
                }
            )
            if len(refs) >= limit:
                return refs
    return refs


def csharp_line_refs(files: list[dict], terms: Iterable[str], limit: int = 8) -> list[dict]:
    refs = []
    for item in files:
        line = first_line_for_any(item["text"], terms)
        if line is not None:
            refs.append({"file": item["rel"], "line": line})
    refs.sort(key=lambda item: ("/Migrations/" in item["file"], item["file"]))
    return refs[:limit]


def file_ref_links(refs: list[dict], limit: int = 6, empty: str = "No file evidence found") -> str:
    if not refs:
        return f'<span class="muted">{html_escape(empty)}</span>'
    parts = []
    for item in refs[:limit]:
        parts.append(f'<span class="code-ref">{html_escape(item["file"])}:{html_escape(item.get("line", 1))}</span>')
    if len(refs) > limit:
        parts.append(f'<span class="muted">+{len(refs) - limit} more</span>')
    return " ".join(parts)


def repo_file_ref(relative_path: str, terms: Iterable[str], fallback_line: int = 1) -> dict:
    path = ROOT / relative_path
    line = fallback_line
    if path.exists():
        text = read_text(path)
        line = first_line_for_any(text, terms) or fallback_line
    return {"file": relative_path, "line": line}


def score_file(text: str, terms: Iterable[str]) -> int:
    score = 0
    for term in terms:
        count = term_count(text, term)
        if count:
            score += min(count, 10) * max(1, min(len(term), 12))
    return score


def analyze_sql_files() -> tuple[list[SqlFile], dict[str, SqlFile]]:
    build_files = parse_sqlproj_build_files()
    files = []
    for path in sorted(SQL_ROOT.rglob("*.sql")):
        rel_to_sql_root = path.relative_to(SQL_ROOT).as_posix()
        sql_file = SqlFile(
            path=path,
            rel=rel(path),
            text=read_text(path),
            category=category_from_path(path),
            in_sqlproj=rel_to_sql_root in build_files,
            generated="/obj/" in path.as_posix() or path.name.endswith(".generated.sql"),
        )
        sql_file.definitions = extract_definitions(sql_file)
        sql_file.columns, sql_file.fks = extract_table_columns_and_fks(sql_file.text)
        sql_file.indexes = len(re.findall(r"\bCREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+|CLUSTERED\s+)?INDEX\b", sql_file.text, re.I))
        sql_file.stats = len(re.findall(r"\bCREATE\s+STATISTICS\b", sql_file.text, re.I))
        sql_file.grants = len(re.findall(r"\bGRANT\b", sql_file.text, re.I))
        sql_file.mutations = Counter(
            match.group(1).upper()
            for match in re.finditer(r"\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE)\b", sql_file.text, re.I)
        )
        sql_file.external_refs = extract_external_refs(sql_file.text)
        sql_file.risk_flags = add_risk_flags(sql_file)
        sql_file.doc_hits = [
            topic["topic"]
            for topic in DOMAIN_TERMS
            if any(term_count(sql_file.text, term) for term in topic["terms"])
        ]
        files.append(sql_file)

    by_object = {}
    for sql_file in files:
        for definition in sql_file.definitions:
            if definition["kind"] not in {"GRANT", "ALTER ROLE", "SECURITY"}:
                by_object[normalize(definition["name"])] = sql_file

    known_aliases = {}
    for obj_name, sql_file in by_object.items():
        real_name = next(
            (definition["name"] for definition in sql_file.definitions if normalize(definition["name"]) == obj_name),
            sql_file.primary_object,
        )
        schema_object = real_name.replace("[", "").replace("]", "")
        variants = {schema_object, schema_object.replace(".", "].["), schema_object.split(".")[-1]}
        for variant in variants:
            known_aliases[normalize(variant)] = schema_object

    for sql_file in files:
        n_text = normalize(sql_file.text)
        self_name = normalize(sql_file.primary_object)
        deps = set()
        for alias, object_name in known_aliases.items():
            if not alias or alias == self_name:
                continue
            if alias in n_text:
                deps.add(object_name)
        sql_file.dependencies = deps
    return files, by_object


def extract_pdf_data() -> list[dict]:
    pdfs = []
    for path in PDF_SOURCES:
        reader = PdfReader(str(path))
        pages = []
        full_text_parts = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": page_number, "text": text})
            full_text_parts.append(text)
        full_text = "\n".join(full_text_parts)
        headings = []
        seen = set()
        for line in full_text.splitlines():
            clean = " ".join(line.strip().split())
            if len(clean) > 180:
                continue
            if re.match(r"^(?:\d+\.)*\d+\s+\S", clean):
                key = normalize(clean)
                if key not in seen:
                    headings.append(clean)
                    seen.add(key)
        pdfs.append(
            {
                "path": rel(path),
                "name": path.name,
                "pages": len(reader.pages),
                "chars": len(full_text),
                "text": full_text,
                "pages_text": pages,
                "headings": headings,
            }
        )
    return pdfs


def build_topic_comparison(files: list[SqlFile], pdfs: list[dict]) -> list[dict]:
    all_docs_text = "\n".join(pdf["text"] for pdf in pdfs)
    comparisons = []
    for topic in DOMAIN_TERMS:
        sql_count = sum(term_count(sql_file.text, term) for sql_file in files for term in topic["terms"])
        doc_count = sum(term_count(all_docs_text, term) for term in topic["terms"])
        evidence = []
        for sql_file in files:
            if any(term_count(sql_file.text, term) for term in topic["terms"]):
                line = first_line_for_any(sql_file.text, topic["terms"])
                evidence.append({"file": sql_file.rel, "line": line or 1, "object": sql_file.primary_object})
        comparisons.append(
            {
                "topic": topic["topic"],
                "terms": topic["terms"],
                "doc_count": doc_count,
                "sql_count": sql_count,
                "pdf_refs": find_pdf_refs(pdfs, topic["terms"]),
                "evidence": evidence[:8],
                "evidence_count": len(evidence),
                "review": topic["review"],
            }
        )
    return comparisons


def build_print_field_mapping(files: list[SqlFile], pdfs: list[dict]) -> list[dict]:
    all_docs_text = "\n".join(pdf["text"] for pdf in pdfs)
    rows = []
    for code, field_name, aliases in PRINT_FIELDS:
        doc_present = term_count(all_docs_text, code) > 0 or term_count(all_docs_text, field_name) > 0
        direct_evidence = []
        alias_evidence = []
        for sql_file in files:
            if term_count(sql_file.text, field_name):
                line = first_line_for_any(sql_file.text, [field_name])
                direct_evidence.append({"file": sql_file.rel, "line": line or 1, "object": sql_file.primary_object})
            elif any(term_count(sql_file.text, alias) for alias in aliases):
                line = first_line_for_any(sql_file.text, aliases)
                alias_evidence.append({"file": sql_file.rel, "line": line or 1, "object": sql_file.primary_object})
        evidence = direct_evidence or alias_evidence
        if direct_evidence:
            status = "Direct SQL token"
        elif alias_evidence:
            status = "Semantic alias"
        elif doc_present:
            status = "Document only"
        else:
            status = "Not found"
        rows.append(
            {
                "code": code,
                "field": field_name,
                "status": status,
                "pdf_refs": find_pdf_refs(pdfs, [code, field_name], limit=4),
                "evidence": evidence[:6],
                "evidence_count": len(evidence),
            }
        )
    return rows


def build_semantic_map(files: list[SqlFile], pdfs: list[dict]) -> list[dict]:
    all_docs_text = "\n".join(pdf["text"] for pdf in pdfs)
    rows = []
    for item in SEMANTIC_DOC_MAP:
        evidence = []
        for sql_file in files:
            if any(term_count(sql_file.text, term) for term in item["sql_terms"]):
                line = first_line_for_any(sql_file.text, item["sql_terms"])
                evidence.append({"file": sql_file.rel, "line": line or 1, "object": sql_file.primary_object})
        rows.append(
            {
                **item,
                "doc_hits": sum(term_count(all_docs_text, term) for term in item["doc_terms"]),
                "pdf_refs": find_pdf_refs(pdfs, item["doc_terms"]),
                "evidence": evidence[:8],
                "evidence_count": len(evidence),
            }
        )
    return rows


def read_csharp_files() -> list[dict]:
    if not CSHARP_BACKEND_ROOT.exists():
        return []
    result = []
    for path in sorted(CSHARP_BACKEND_ROOT.rglob("*.cs")):
        text = read_text(path)
        result.append({"path": path, "rel": rel(path), "text": text})
    return result


def read_legacy_code_files() -> list[dict]:
    if not LEGACY_CODE_ROOT.exists():
        return []
    result = []
    for path in sorted(LEGACY_CODE_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in LEGACY_CODE_SUFFIXES:
            text = read_text(path)
            result.append({"path": path, "rel": rel(path), "text": text})
    return result


def legacy_code_matchable_sql_objects(files: list[SqlFile]) -> list[dict]:
    objects = []
    for sql_file in files:
        obj = sql_file.primary_object
        if not obj or obj in {"app", "dbo", "ref"}:  # EXAMPLE schema set — adjust per project
            continue
        if sql_file.primary_kind in {"SECURITY", "USER", "ROLE", "ALTER ROLE", "GRANT"}:
            continue
        schema, _, name = obj.partition(".")
        if not schema or not name:
            continue
        objects.append({"object": obj, "schema": schema, "name": name, "kind": sql_file.primary_kind, "file": sql_file.rel})
    return objects


def legacy_code_object_regex(obj: dict) -> re.Pattern:
    schema = obj["schema"]
    name = obj["name"]
    patterns = [
        re.escape(obj["object"]),
        re.escape(f"{schema}.{schema}.{name}"),
        re.escape(f"[{schema}].[{name}]"),
        re.escape(f"[{schema}].[{schema}].[{name}]"),
        rf"(?<![\w.]){re.escape(name)}(?![\w])",
    ]
    return re.compile("|".join(patterns), re.I)


def legacy_code_stored_proc_calls(legacy_code_files: list[dict], objects: list[dict]) -> list[dict]:
    known_by_object = {obj["object"].lower(): obj for obj in objects}
    known_by_name = {obj["name"].lower(): obj for obj in objects}
    call_rx = re.compile(r"<cfstoredproc\b[^>]*\bprocedure\s*=\s*[\"']([^\"']+)", re.I)
    calls = []
    for cf_file in legacy_code_files:
        for match in call_rx.finditer(cf_file["text"]):
            procedure = match.group(1)
            line = line_number(cf_file["text"], match.start())
            normalized = procedure.replace("[", "").replace("]", "")
            parts = normalized.split(".")
            candidates = [normalized.lower(), ".".join(parts[-2:]).lower(), parts[-1].lower()]
            matched = None
            for candidate in candidates:
                matched = known_by_object.get(candidate) or known_by_name.get(candidate)
                if matched:
                    break
            calls.append(
                {
                    "file": cf_file["rel"],
                    "line": line,
                    "procedure": procedure,
                    "matched_object": matched["object"] if matched else "",
                    "sql_file": matched["file"] if matched else "",
                    "matched": bool(matched),
                }
            )
    return calls


def build_legacy_code_callsite_analysis(files: list[SqlFile]) -> dict:
    legacy_code_files = read_legacy_code_files()
    objects = legacy_code_matchable_sql_objects(files)
    sql_by_object = {sql_file.primary_object.lower(): sql_file for sql_file in files}
    object_hits: dict[str, dict] = {}
    file_hits: dict[str, set[str]] = defaultdict(set)
    for obj in objects:
        rx = legacy_code_object_regex(obj)
        for cf_file in legacy_code_files:
            for line_no, line in enumerate(cf_file["text"].splitlines(), start=1):
                if not rx.search(line):
                    continue
                entry = object_hits.setdefault(
                    obj["object"],
                    {
                        "object": obj["object"],
                        "kind": obj["kind"],
                        "sql_file": obj["file"],
                        "hits": 0,
                        "qualified_hits": 0,
                        "refs": [],
                    },
                )
                qualified_rx = re.compile(
                    rf"(\b{re.escape(obj['schema'])}\.|\[{re.escape(obj['schema'])}\])",
                    re.I,
                )
                entry["hits"] += 1
                if qualified_rx.search(line):
                    entry["qualified_hits"] += 1
                if len(entry["refs"]) < 5:
                    entry["refs"].append({"file": cf_file["rel"], "line": line_no, "snippet": compact(line.strip(), 220)})
                file_hits[cf_file["rel"]].add(obj["object"])

    stored_proc_calls = legacy_code_stored_proc_calls(legacy_code_files, objects)
    procedure_flow_map: dict[str, dict] = {}
    for call in stored_proc_calls:
        procedure = call["procedure"]
        flow = procedure_flow_map.setdefault(
            procedure,
            {
                "procedure": procedure,
                "matched_object": call.get("matched_object", ""),
                "sql_file": call.get("sql_file", ""),
                "matched": call.get("matched", False),
                "cf_refs": [],
                "sql_dependencies": [],
                "external_refs": [],
            },
        )
        if len(flow["cf_refs"]) < 8:
            flow["cf_refs"].append({"file": call["file"], "line": call["line"]})
        matched_sql = sql_by_object.get(str(call.get("matched_object", "")).lower())
        if matched_sql:
            dependencies = sorted(
                dep
                for dep in matched_sql.dependencies
                if dep != matched_sql.primary_object and dep.startswith(("app.T", "dbo.T", "ref."))
            )
            flow["sql_dependencies"] = dependencies[:10]
            flow["external_refs"] = sorted(matched_sql.external_refs)[:6]
    procedure_flows = sorted(
        procedure_flow_map.values(),
        key=lambda row: (not row.get("matched"), row["procedure"].lower()),
    )

    domain_definitions = [
        {
            "name": "Order capture, edit, and cancellation",
            "files": ["insert.cfm", "change.cfm", "storno_submit.cfm", "haf/"],
            "objects": ["app.P_STORE_ORDER_XML", "app.P_SHOW_ORDER_XML", "app.TOrderHead", "app.TDestination", "app.TOrderDetail", "app.TBilling", "dbo.TLog"],
            "note": "Main form screens and HAF variants read/write order XML and core order tables.",
        },
        {
            "name": "Postbox administration",
            "files": ["postfach", "_PF_Select.cfm", "pf_"],
            "objects": ["app.TBoxMasterData", "app.TBoxLocation", "app.TBoxStatus", "ref.RLocation", "app.FilterByLocation"],
            "note": "Postbox screens manage master data, free/occupied state, locations, and branch filtering.",
        },
        {
            "name": "Billing and open collection cases",
            "files": ["verrechnung", "result.cfm"],
            "objects": ["app.TBilling", "app.TBillingStatus", "app.TBilling_History", "dbo.TLog", "dbo.sp_GetAutoNummer"],
            "note": "Billing components insert/update Verrechnung rows and record audit log entries.",
        },
        {
            "name": "Bulk import and BatchOrder",
            "files": ["BatchOrderLogic.cfc", "massen_verlaengerung", "asg_importscript", "pf_importscript"],
            "objects": ["app.TBatchOrder", "app.P_STORE_ORDER_XML", "app.TOrderHead", "app.TDestination", "app.TOrderType"],
            "note": "Bulk-import code stages rows, checks duplicates, then creates regular legacy orders through the XML save path.",
        },
        {
            "name": "Search, person, and address lookup",
            "files": ["result.cfm", "functions.cfc", "ver_check", "newreg_adr_check"],
            "objects": ["app.OrderSearch", "app.GetAddress", "app.fn_clr_extperson_search", "app.clr_extperson_getPerson", "app.TOrderHead", "app.TOrderDetail"],
            "note": "Search and validation screens combine legacy rows with external search API/person and address-provider wrappers.",
        },
    ]
    domain_flows = []
    for definition in domain_definitions:
        cf_refs = [
            {"file": file, "object_count": len(objects)}
            for file, objects in sorted(file_hits.items(), key=lambda item: (-len(item[1]), item[0]))
            if any(term.lower() in file.lower() for term in definition["files"])
        ][:8]
        object_rows = []
        for object_name in definition["objects"]:
            hit = object_hits.get(object_name)
            if hit:
                object_rows.append(
                    {
                        "object": object_name,
                        "hits": hit["hits"],
                        "kind": hit["kind"],
                        "sql_file": hit["sql_file"],
                        "refs": hit["refs"][:3],
                    }
                )
        domain_flows.append({**definition, "cf_refs": cf_refs, "sql_objects": object_rows})

    top_objects = sorted(object_hits.values(), key=lambda row: (-row["hits"], row["object"]))[:35]
    top_files = [
        {"file": file, "object_count": len(objects), "objects": sorted(objects)[:12]}
        for file, objects in sorted(file_hits.items(), key=lambda item: (-len(item[1]), item[0]))[:30]
    ]

    datasource_refs = []
    app_file = LEGACY_CODE_ROOT / "Application.cfc"
    if app_file.exists():
        text = read_text(app_file)
        for term in ["this.datasource", "Application.DSN"]:
            line = first_line_for_any(text, [term])
            if line:
                datasource_refs.append({"file": rel(app_file), "line": line})
    datasource_match = re.search(r"this\.datasource\s*=\s*['\"]([^'\"]+)['\"]", read_text(app_file), re.I) if app_file.exists() else None

    return {
        "root": rel(LEGACY_CODE_ROOT),
        "exists": LEGACY_CODE_ROOT.exists(),
        "datasource": datasource_match.group(1) if datasource_match else "",
        "datasource_refs": datasource_refs,
        "files_scanned": len(legacy_code_files),
        "files_with_sql_hits": len(file_hits),
        "distinct_sql_objects_hit": len(object_hits),
        "stored_proc_calls": stored_proc_calls,
        "matched_stored_proc_calls": sum(1 for call in stored_proc_calls if call["matched"]),
        "unmatched_stored_proc_calls": sum(1 for call in stored_proc_calls if not call["matched"]),
        "procedure_flows": procedure_flows,
        "domain_flows": domain_flows,
        "top_objects": top_objects,
        "top_files": top_files,
    }


def build_csharp_backend_comparison(csharp_files: list[dict], pdfs: list[dict]) -> list[dict]:
    rows = []
    for topic in CSHARP_COMPARISON_TOPICS:
        refs = csharp_line_refs(csharp_files, topic["terms"], limit=10)
        if refs:
            status = "Evidence found in C# backend"
        else:
            status = "No direct C# backend evidence found by term scan"
        rows.append(
            {
                "capability": topic["capability"],
                "expected": topic["expected"],
                "terms": topic["terms"],
                "status": status,
                "pdf_refs": find_pdf_refs(pdfs, topic["terms"], limit=4),
                "evidence": refs,
                "evidence_count": len(refs),
            }
        )
    return rows


def find_spec_pdf_refs(pdfs: list[dict], terms: Iterable[str], limit: int = 4) -> list[dict]:
    spec_pdfs = [pdf for pdf in pdfs if pdf.get("name") == PDF_SOURCES[0].name]
    return find_pdf_refs(spec_pdfs, terms, limit=limit)


def sql_evidence_for_terms(files: list[SqlFile], terms: Iterable[str], limit: int = 8) -> list[dict]:
    scored = []
    for sql_file in files:
        score = score_file(sql_file.text, terms)
        if score:
            scored.append((score, sql_file))
    scored.sort(key=lambda item: (-item[0], item[1].rel))
    return [
        {
            "object": sql_file.primary_object,
            "file": sql_file.rel,
            "line": first_line_for_any(sql_file.text, terms) or 1,
            "category": sql_file.category,
        }
        for _, sql_file in scored[:limit]
    ]


def csharp_evidence_for_terms(csharp_files: list[dict], terms: Iterable[str], limit: int = 8) -> list[dict]:
    scored = []
    for item in csharp_files:
        score = score_file(item["text"], terms)
        if not score:
            continue
        domain_bonus = 0
        rel_path = item["rel"]
        if "/{BACKEND-DOMAIN-PROJECT}/" in rel_path:
            domain_bonus += 20
        if "/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/" in rel_path:
            domain_bonus += 16
        if "/Data/Configuration/" in rel_path:
            domain_bonus += 12
        if "/Migrations/" in rel_path and not rel_path.endswith(".Designer.cs"):
            domain_bonus += 4
        if "/Data/TestData/" in rel_path or "/Data/FakeData/" in rel_path:
            domain_bonus -= 80
        if rel_path.endswith(".Designer.cs") or rel_path.endswith("ModelSnapshot.cs"):
            domain_bonus -= 30
        scored.append((score + domain_bonus, item))
    scored.sort(key=lambda item: (-item[0], item[1]["rel"]))
    return [
        {"file": item["rel"], "line": first_line_for_any(item["text"], terms) or 1}
        for _, item in scored[:limit]
    ]


def extract_frontmatter(text: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    return match.group(1) if match else ""


def frontmatter_value(frontmatter: str, field_name: str) -> str:
    match = re.search(rf"^{re.escape(field_name)}:\s*(.+?)\s*$", frontmatter, re.M)
    if not match:
        return ""
    return match.group(1).strip().strip("'\"")


def frontmatter_products(frontmatter: str) -> set[str]:
    match = re.search(r"(?im)^(?:product|Product):\s*\n((?:\s+-\s+PRODUCT-\d{3}\s*\n)+)", frontmatter)
    return set(re.findall(r"PRODUCT-\d{3}", match.group(1))) if match else set()


def read_requirement_pages() -> list[dict]:
    features: dict[str, str] = {}
    feature_paths = sorted(FEATURES_ROOT.glob("FEAT-*.md")) if FEATURES_ROOT.exists() else []
    for path in feature_paths:
        text = read_text(path)
        frontmatter = extract_frontmatter(text)
        feature_id = frontmatter_value(frontmatter, "id")
        if feature_id:
            features[feature_id] = text

    requirements = []
    requirement_paths = sorted(REQUIREMENTS_ROOT.glob("REQ-*.md")) if REQUIREMENTS_ROOT.exists() else []
    for path in requirement_paths:
        text = read_text(path)
        frontmatter = extract_frontmatter(text)
        requirement_id = frontmatter_value(frontmatter, "id") or path.stem
        feature_id = frontmatter_value(frontmatter, "feature")
        title = frontmatter_value(frontmatter, "title") or requirement_id
        feature_text = features.get(feature_id, "")
        requirements.append(
            {
                "id": requirement_id,
                "title": title,
                "path": rel(path),
                "href": f"requirements/{path.name}",
                "products": sorted(frontmatter_products(frontmatter) | frontmatter_products(extract_frontmatter(feature_text))),
                "text": text,
                "own_corpus": normalize(text),
                "feature_corpus": normalize(feature_text),
                "corpus": normalize(f"{text}\n{feature_text}"),
            }
        )
    return requirements


def product_ids_for_label(label: str) -> set[str]:
    product_ids: set[str] = set()
    normalized_label = normalize(label)
    for code, ids in PRODUCT_CODE_TO_IDS.items():
        if re.search(rf"\b{re.escape(normalize(code))}\b", normalized_label):
            product_ids.update(ids)
    return product_ids


def requirement_refs_for_coverage_row(row: dict, requirements: list[dict]) -> list[dict]:
    rules = SPEC_COVERAGE_REQUIREMENT_RULES.get(row.get("area", ""), {})
    row_product_ids = product_ids_for_label(f"{row.get('product', '')} {row.get('area', '')}")
    terms = rules.get("terms", [])
    sql_objects = [ref.get("object", "") for ref in row.get("legacy_sql_evidence", [])]
    sql_files = [Path(ref.get("file", "")).name for ref in row.get("legacy_sql_evidence", [])]

    refs = []
    for requirement in requirements:
        own_corpus = requirement["own_corpus"]
        title_corpus = normalize(requirement["title"])
        semantic_score = 0
        sql_score = 0
        reasons: list[str] = []

        if requirement["id"] in set(rules.get("ids", [])):
            semantic_score += 20
            reasons.append("explizite Zuordnung")
        if any(requirement["id"].startswith(prefix) for prefix in rules.get("prefixes", [])):
            semantic_score += 12
            reasons.append("REQ-Gruppe")

        matched_sql = []
        for sql_object in sql_objects:
            sql_object_norm = normalize(sql_object)
            if sql_object and sql_object_norm in own_corpus:
                sql_score += 5
                matched_sql.append(sql_object)
        for sql_file in sql_files:
            sql_file_norm = normalize(sql_file)
            if sql_file and sql_file_norm in own_corpus:
                sql_score += 4
                matched_sql.append(sql_file)
        if matched_sql:
            reasons.append("SQL")

        matched_terms = []
        for term in terms:
            term_norm = normalize(term)
            if len(term_norm) >= 3 and term_norm in title_corpus:
                semantic_score += 8
                matched_terms.append(term)

        if matched_terms:
            reasons.append("Begriff")

        product_overlap = row_product_ids & set(requirement.get("products", []))
        if product_overlap and semantic_score > 0:
            semantic_score += 1
            reasons.append("Produkt")

        score = semantic_score + (sql_score if semantic_score > 0 else 0)
        if score >= 8:
            refs.append(
                {
                    "id": requirement["id"],
                    "title": requirement["title"],
                    "path": requirement["path"],
                    "href": requirement["href"],
                    "score": score,
                    "reason": ", ".join(dict.fromkeys(reasons)) or "Begriffsabgleich",
                }
            )

    refs.sort(key=lambda ref: (-ref["score"], ref["id"]))
    return refs


def status_is_full_coverage(status: str) -> bool:
    normalized_status = normalize(str(status))
    return normalized_status.startswith("yes") or normalized_status.startswith("exact") or normalized_status.startswith("vollstandig")


def db_table_recommendation_rule(legacy_table: str) -> dict:
    rule = DB_TABLE_RECOMMENDATION_RULES.get(legacy_table)
    if rule:
        return rule
    bare_table = legacy_table.split(".")[-1]
    for table_name, candidate in DB_TABLE_RECOMMENDATION_RULES.items():
        if table_name.split(".")[-1] == bare_table:
            return candidate
    return DEFAULT_DB_TABLE_RECOMMENDATION_RULE


def requirement_refs_for_legacy_table(row: dict, requirements: list[dict], rule: dict) -> list[dict]:
    legacy_table = row.get("legacy_table", "")
    legacy_path = row.get("legacy_path", "")
    legacy_file = Path(legacy_path).name
    legacy_bare = legacy_table.split(".")[-1]
    direct_needles = [legacy_table, legacy_path, legacy_file, legacy_bare]
    semantic_terms = [
        *rule.get("requirement_terms", []),
        *row.get("concepts", []),
    ]
    prefixes = tuple(rule.get("requirement_prefixes", []))
    explicit_ids = set(rule.get("requirement_ids", []))

    refs = []
    for requirement in requirements:
        own_corpus = requirement["own_corpus"]
        title_corpus = normalize(requirement["title"])
        direct_score = 0
        semantic_score = 0
        has_rule_ref = False
        reasons: list[str] = []
        matched_terms: list[str] = []

        for needle in direct_needles:
            needle_norm = normalize(str(needle))
            if needle_norm and needle_norm in own_corpus:
                direct_score += 16 if needle in {legacy_table, legacy_path, legacy_file} else 10
                matched_terms.append(str(needle))
        if direct_score:
            reasons.append("direkte SQL-Quelle")

        if requirement["id"] in explicit_ids:
            semantic_score += 14
            has_rule_ref = True
            reasons.append("explizite REQ-Regel")
        if prefixes and requirement["id"].startswith(prefixes):
            semantic_score += 10
            has_rule_ref = True
            reasons.append("REQ-Gruppe")

        for term in semantic_terms:
            term_norm = normalize(str(term))
            if len(term_norm) < 4:
                continue
            if term_norm in title_corpus:
                semantic_score += 5
                matched_terms.append(str(term))
            elif term_norm in own_corpus:
                semantic_score += 2
                matched_terms.append(str(term))
        if semantic_score and "REQ-Gruppe" not in reasons and "explizite REQ-Regel" not in reasons:
            reasons.append("Fachbegriff")

        score = direct_score + semantic_score
        if direct_score or has_rule_ref:
            refs.append(
                {
                    "id": requirement["id"],
                    "title": requirement["title"],
                    "path": requirement["path"],
                    "href": requirement["href"],
                    "score": score,
                    "reason": ", ".join(dict.fromkeys(reasons)) or "Tabellen-/Begriffsabgleich",
                    "matched_terms": sorted(dict.fromkeys(matched_terms))[:8],
                }
            )

    refs.sort(key=lambda ref: (-ref["score"], ref["id"]))
    return refs[:12]


def build_db_table_recommendations(csharp_sql_model: dict, requirements: list[dict]) -> dict:
    rows = []
    for coverage_row in csharp_sql_model.get("legacy_table_coverage", []):
        if status_is_full_coverage(coverage_row.get("status", "")):
            continue
        legacy_table = coverage_row.get("legacy_table", "")
        rule = db_table_recommendation_rule(legacy_table)
        row = {
            "legacy_table": legacy_table,
            "legacy_path": coverage_row.get("legacy_path", ""),
            "coverage_status": coverage_row.get("status", "Unknown"),
            "confidence": coverage_row.get("confidence", "unknown"),
            "priority": rule.get("priority", "mittel"),
            "decision": rule.get("decision", DEFAULT_DB_TABLE_RECOMMENDATION_RULE["decision"]),
            "target_model": rule.get("target_model", DEFAULT_DB_TABLE_RECOMMENDATION_RULE["target_model"]),
            "target_model_label": rule.get(
                "target_model_label",
                rule.get("target_model", DEFAULT_DB_TABLE_RECOMMENDATION_RULE["target_model"]),
            ),
            "recommendation": rule.get("recommendation", DEFAULT_DB_TABLE_RECOMMENDATION_RULE["recommendation"]),
            "rationale": rule.get("rationale", coverage_row.get("rationale", "")),
            "coverage_rationale": coverage_row.get("rationale", ""),
            "current_csharp_surface": coverage_row.get("csharp_tables", []),
            "concepts": coverage_row.get("concepts", []),
            "legacy_columns": coverage_row.get("legacy_columns", []),
            "target_fields": [
                {"name": name, "type": field_type, "reason": reason}
                for name, field_type, reason in DB_TABLE_TARGET_FIELDS.get(legacy_table, [])
            ],
            "legacy_evidence": coverage_row.get("legacy_evidence", []),
            "csharp_evidence": coverage_row.get("csharp_evidence", []),
        }
        row["requirement_refs"] = requirement_refs_for_legacy_table(coverage_row, requirements, rule)
        rows.append(row)

    status_counts = Counter(row["coverage_status"] for row in rows)
    priority_counts = Counter(row["priority"] for row in rows)
    return {
        "scope": "Legacy SQL tables whose current C# coverage has status Partial or status No direct table.",
        "source": "reports/evaluations/legacy-sql/legacy-sql-analysis-data.json#csharp_sql_model.legacy_table_coverage",
        "counts": {
            "total": len(rows),
            "by_coverage": dict(status_counts),
            "by_priority": dict(priority_counts),
        },
        "rows": rows,
    }


def csharp_active_tables(csharp_sql_model: dict) -> list[str]:
    tables = []
    for schema_row in csharp_sql_model.get("schemas", []):
        schema = schema_row.get("schema")
        for table_name in schema_row.get("tables", []):
            tables.append(table_name if schema == "dbo/default" else f"{schema}.{table_name}")
    return sorted(dict.fromkeys(tables))


def recommendation_visual_kind(row: dict) -> str:
    text = normalize(" ".join([row.get("decision", ""), row.get("recommendation", ""), row.get("target_model", "")]))
    if (
        "nicht portieren" in text
        or "keine tabelle" in text
        or "keine neue tabelle" in text
        or "keine dedizierte" in text
        or "vorlaufig keine" in text
        or "nocsharpdomaintable" in text
    ):
        return "not_recommended"
    return "recommended"


def recommendation_anchor_tables(row: dict, current_tables: set[str]) -> list[str]:
    if recommendation_visual_kind(row) == "not_recommended" and normalize(row.get("target_model", "")) == "nocsharpdomaintable":
        return []
    anchors = [table for table in row.get("current_csharp_surface", []) if table in current_tables]
    if anchors:
        return anchors[:4]
    legacy_table = row.get("legacy_table", "")
    target_model = row.get("target_model", "")
    text = normalize(f"{legacy_table} {target_model} {row.get('decision', '')}")
    inferred: list[str] = []
    if any(term in text for term in ["verrechnung", "billing", "payment", "inkasso", "autonummer", "print", "etikett", "log", "audit", "aenderung", "storno"]):
        inferred.append("Orders")
    if any(term in text for term in ["postfach", "standort", "providerlocation", "branchlocation"]):
        inferred.extend(["OrderRoutingPostOfficeBoxes", "Addresses"])
    if any(term in text for term in ["sso", "registrierung", "customeridentification"]):
        inferred.extend(["CustomerIdentifications", "Orders"])
    if any(term in text for term in ["sammel", "batchimport", "import"]):
        inferred.extend(["Orders", "Directives"])
    if any(term in text for term in ["sendung", "shipment"]):
        inferred.extend(["ShipmentTypes", "Orders"])
    if any(term in text for term in ["serviceinformation", "lookup", "titel", "title"]):
        inferred.append("Lookups")
    if any(term in text for term in ["berechtigung", "permission", "role"]):
        inferred.extend(["auth.Roles", "auth.Permissions"])
    if any(term in text for term in ["adresse", "routing", "destination", "pac", "plz"]):
        inferred.extend(["Addresses", "OrderRoutingAddresses"])
    inferred = [table for table in dict.fromkeys(inferred) if table in current_tables]
    return inferred[:4] or (["Orders"] if "Orders" in current_tables else [])


def domain_group_for_current_table(table_name: str, csharp_sql_model: dict) -> str:
    for row in csharp_sql_model.get("domain_model", []):
        if table_name in row.get("mapped_tables", []):
            return row.get("model", "Current C#")
    if table_name.startswith("auth."):
        return "Role aggregate"
    if table_name.startswith("work."):
        return "Queue/work infrastructure model"
    return "Current C# persistence"


def current_domain_group_label(group_name: str) -> str:
    return {
        "DirectiveOrder aggregate": "Existing C# Model: Orders",
        "Directive aggregate": "Existing C# Model: Product Catalog",
        "Address aggregate": "Existing C# Model: Addresses",
        "Lookup aggregate": "Existing C# Model: Lookups",
        "Role aggregate": "Existing C# Model: Roles and Permissions",
        "Queue/work infrastructure model": "Existing C# Model: Technical Queue",
        "Current C# persistence": "Existing C# Model",
    }.get(group_name, group_name)


def domain_group_for_recommendation(row: dict) -> str:
    text = normalize(f"{row.get('legacy_table', '')} {row.get('target_model', '')} {row.get('decision', '')}")
    if recommendation_visual_kind(row) == "not_recommended":
        return "Not recommended for C# domain persistence"
    if "postfach" in text or "standort" in text or "provider" in text:
        return "Recommended DB Extensions: Mailbox, Address and Location"
    if "verrechnung" in text or "billing" in text or "payment" in text or "inkasso" in text:
        return "Recommended DB Extensions: Billing and Payment"
    if "sso" in text or "registrierung" in text or "berechtigung" in text or "audit" in text or "log" in text:
        return "Recommended DB Extensions: Identity, Permissions and Audit"
    if "import" in text or "sammel" in text or "druck" in text or "etikett" in text or "print" in text:
        return "Recommended DB Extensions: Import and Print"
    return "Recommended DB Extensions: Orders, Lookups and Rules"


def recommendation_target_label(row: dict) -> str:
    target_model = row.get("target_model", "")
    target_display = row.get("target_model_label") or target_model
    visual_kind = recommendation_visual_kind(row)
    normalized_target = normalize(target_model)
    if visual_kind == "not_recommended":
        return f"No new domain model: {target_display}"
    if any(term in normalized_target for term in ["orders", "addresses", "lookups", "directives", "auth", "customeridentifications"]):
        return f"C# Target: extend existing model ({target_display})"
    return f"C# Target: {target_display}"


def recommendation_node_label(node: dict) -> str:
    prefix = "Recommended" if node["visual_kind"] == "recommended" else "Do not port directly"
    decision = node.get("decision", "")
    target = node.get("target_label", node.get("target_model", ""))
    legacy = node.get("legacy_table", "")
    priority = node.get("priority", "")
    return (
        f"{prefix}: {decision}<br/>"
        f"{target}<br/>"
        f"Legacy evidence: {legacy}<br/>"
        f"Priority: {priority}"
    )


def build_domain_model_recommendation_er(csharp_sql_model: dict, db_recommendations: dict) -> dict:
    current_tables = csharp_active_tables(csharp_sql_model)
    current_table_set = set(current_tables)
    used_ids: set[str] = set()
    node_ids = {table_name: mermaid_identifier(f"C_{table_name}", used_ids) for table_name in current_tables}

    current_groups: dict[str, list[str]] = defaultdict(list)
    for table_name in current_tables:
        current_groups[domain_group_for_current_table(table_name, csharp_sql_model)].append(table_name)

    recommendation_nodes = []
    recommendation_edges = []
    for row in db_recommendations.get("rows", []):
        legacy_table = row.get("legacy_table", "")
        rec_id = mermaid_identifier(f"R_{legacy_table}", used_ids)
        visual_kind = recommendation_visual_kind(row)
        anchors = recommendation_anchor_tables(row, current_table_set)
        recommendation_nodes.append(
            {
                "id": rec_id,
                "legacy_table": legacy_table,
                "coverage_status": row.get("coverage_status", ""),
                "priority": row.get("priority", ""),
                "decision": row.get("decision", ""),
                "target_model": row.get("target_model", ""),
                "target_label": recommendation_target_label(row),
                "visual_kind": visual_kind,
                "group": domain_group_for_recommendation(row),
                "anchors": anchors,
            }
        )
        for anchor in anchors:
            recommendation_edges.append(
                {
                    "source": anchor,
                    "target": legacy_table,
                    "label": "extends" if visual_kind == "recommended" else "decision",
                }
            )

    recommendation_groups: dict[str, list[dict]] = defaultdict(list)
    for node in recommendation_nodes:
        recommendation_groups[node["group"]].append(node)

    current_relationships = []
    seen_relationships = set()
    for diagram in csharp_sql_model.get("er_diagrams", []):
        for relationship in diagram.get("relationships", []):
            source = relationship.get("source")
            target = relationship.get("target")
            if source not in current_table_set or target not in current_table_set:
                continue
            key = (source, target, relationship.get("column", ""), relationship.get("kind", ""))
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            current_relationships.append(relationship)

    lines = [
        '%%{init: {"flowchart": {"htmlLabels": true, "curve": "basis", "nodeSpacing": 42, "rankSpacing": 72}}}%%',
        "flowchart LR",
        '  LegendCurrent["Existing C# Table<br/>blue border"]:::current',
        '  LegendRecommended["Recommended DB Extension<br/>orange border"]:::recommended',
        '  LegendDecision["Do not port directly<br/>grey dashed"]:::notRecommended',
        "",
        '  subgraph Current["Current C# EF/Domain Model"]',
        "    direction TB",
    ]
    for group_name, tables in current_groups.items():
        group_id = mermaid_identifier(f"G_Current_{group_name}", used_ids)
        lines.append(f'    subgraph {group_id}["{mermaid_node_label(current_domain_group_label(group_name), 80)}"]')
        lines.append("      direction TB")
        for table_name in tables:
            label = f"C# Table<br/>{table_name}"
            lines.append(f'      {node_ids[table_name]}["{mermaid_node_label(label, 90)}"]:::current')
        lines.append("    end")
    lines.append("  end")
    lines.extend(
        [
            "",
            '  subgraph Recommended["DB Recommendations From Legacy Tables With Gaps"]',
            "    direction TB",
        ]
    )
    for group_name, nodes in recommendation_groups.items():
        group_id = mermaid_identifier(f"G_Recommended_{group_name}", used_ids)
        lines.append(f'    subgraph {group_id}["{mermaid_node_label(group_name, 88)}"]')
        lines.append("      direction TB")
        for node in nodes:
            css_class = "notRecommended" if node["visual_kind"] != "recommended" else "recommended"
            label = mermaid_node_label(recommendation_node_label(node), 220)
            lines.append(f'      {node["id"]}["{label}"]:::{css_class}')
        lines.append("    end")
    lines.append("  end")
    lines.append("")

    for relationship in current_relationships:
        parent = node_ids[relationship["target"]]
        child = node_ids[relationship["source"]]
        label = mermaid_token(relationship.get("column", "fk"), "fk")
        connector = "-->" if relationship.get("kind") == "declared" else "-.->"
        lines.append(f"  {parent} {connector}|{label}| {child}")

    rec_id_by_legacy_table = {node["legacy_table"]: node["id"] for node in recommendation_nodes}
    for edge in recommendation_edges:
        source_id = node_ids.get(edge["source"])
        target_id = rec_id_by_legacy_table.get(edge["target"])
        if source_id and target_id:
            lines.append(f'  {source_id} -.->|{edge["label"]}| {target_id}')

    lines.extend(
        [
            "",
            "  classDef current fill:#eff6ff,stroke:#2563eb,stroke-width:3px,color:#111827;",
            "  classDef recommended fill:#fff7ed,stroke:#ea580c,stroke-width:3px,color:#111827;",
            "  classDef notRecommended fill:#f3f4f6,stroke:#6b7280,stroke-width:3px,stroke-dasharray: 6 4,color:#374151;",
        ]
    )

    return {
        "title": "Domain Model Overlay - Current C# Plus DB Recommendations",
        "description": (
            "Mermaid overlay of the active C# EF/domain model and the recommended DB extensions "
            "from legacy tables with incomplete C# coverage."
        ),
        "current_tables": current_tables,
        "recommendation_nodes": recommendation_nodes,
        "current_relationships": current_relationships,
        "recommendation_edges": recommendation_edges,
        "current_table_count": len(current_tables),
        "recommendation_count": len(recommendation_nodes),
        "current_relationship_count": len(current_relationships),
        "recommendation_edge_count": len(recommendation_edges),
        "mermaid": "\n".join(lines),
    }


def acid_relationships_for_tables(table_names: list[str]) -> list[dict]:
    table_set = set(table_names)
    return [
        {
            "source": source,
            "target": target,
            "column": column,
            "kind": kind,
            "note": note,
        }
        for source, target, column, kind, note in ACID_RECOMMENDED_RELATIONSHIPS
        if source in table_set and target in table_set
    ]


def acid_mermaid_column_line(column: tuple[str, str, str]) -> str:
    column_type, name, key = column
    if key in {"PK", "FK", "UK"}:
        key_text = f" {key}"
    elif key:
        # Mermaid erDiagram only accepts PK/FK/UK as attribute keys; render
        # other markers (e.g. NEU) as a quoted attribute comment instead.
        key_text = f' "{key}"'
    else:
        key_text = ""
    return f"    {mermaid_type(column_type)} {mermaid_token(name, 'column')}{key_text}"


ACID_TABLE_STATUS_LABELS = {
    "exists": "Exists in C#",
    "extend": "Extend existing C# table",
    "implement": "Implement new table",
}


def acid_table_status(table: dict) -> str:
    kind = normalize(table.get("kind", ""))
    if "new" in kind or "neu" in kind:
        return "implement"
    if "extend" in kind or "erweitern" in kind:
        return "extend"
    return "exists"


def acid_entity_ids_for_table_names(table_names: list[str]) -> dict[str, str]:
    used: set[str] = set()
    return {name: mermaid_identifier(name, used) for name in table_names}


def acid_table_payload(name: str, table: dict, entity_id: str) -> dict:
    status = acid_table_status(table)
    return {
        "name": name,
        "entity_id": entity_id,
        "kind": table["kind"],
        "implementation_status": status,
        "implementation_label": ACID_TABLE_STATUS_LABELS[status],
        "source": table["source"],
        "legacy_tables": table.get("legacy_tables", []),
        "columns": [
            {"type": column_type, "name": column_name, "key": key}
            for column_type, column_name, key in table.get("columns", [])
        ],
        "note": table.get("note", ""),
    }


def acid_mermaid_er_source(table_names: list[str], relationships: list[dict]) -> str:
    entity_ids = acid_entity_ids_for_table_names(table_names)
    lines = ["erDiagram"]
    lines.append("  %% Recommended ACID target model. PK/FK/UK mark primary, foreign, and unique keys.")
    lines.append("  %% Colors are applied after Mermaid rendering so erDiagram stays valid for Mermaid 10.9.6.")
    for name in table_names:
        table = ACID_RECOMMENDED_TABLES[name]
        entity_id = entity_ids[name]
        lines.append(f"  %% {entity_id} = {name} | {table['kind']} | Legacy: {', '.join(table.get('legacy_tables', [])) or table['source']}")
        lines.append(f"  {entity_id} {{")
        for column in table.get("columns", []):
            lines.append(acid_mermaid_column_line(column))
        lines.append("  }")
    lines.append("  %% Relationships are target proposals for FK constraints in the ACID model.")
    for relationship in relationships:
        parent = entity_ids[relationship["target"]]
        child = entity_ids[relationship["source"]]
        label = mermaid_token(f'{relationship["column"]}_{relationship["kind"]}', "relates")
        lines.append(f"  {parent} ||--o{{ {child} : {label}")
    return "\n".join(lines)


def build_recommended_acid_er_diagrams(db_recommendations: dict) -> dict:
    recommended_target_models = {
        row.get("target_model")
        for row in db_recommendations.get("rows", [])
        if row.get("target_model") and row.get("target_model") != "NoCSharpDomainTable"
    }
    mapped_legacy_tables = {
        legacy_table
        for table in ACID_RECOMMENDED_TABLES.values()
        for legacy_table in table.get("legacy_tables", [])
    }
    diagrams = []
    all_relationships = []
    all_tables = {}

    complete_table_names = complete_acid_er_table_names()
    complete_entity_ids = acid_entity_ids_for_table_names(complete_table_names)
    complete_relationships = acid_relationships_for_tables(complete_table_names)
    complete_table_payloads = [
        acid_table_payload(name, ACID_RECOMMENDED_TABLES[name], complete_entity_ids[name])
        for name in complete_table_names
    ]
    diagrams.append(
        {
            "id": COMPLETE_ACID_ER_DIAGRAM_ID,
            "title": "Complete ACID Target Model",
            "description": (
                "Single complete ER diagram with every current C# and recommended target table exactly once. "
                "The focused diagrams below intentionally repeat shared anchor tables such as Orders, Lookups, "
                "and AuditLog to keep each topic readable."
            ),
            "is_complete": True,
            "tables": complete_table_payloads,
            "relationships": complete_relationships,
            "mermaid": acid_mermaid_er_source(complete_table_names, complete_relationships),
        }
    )
    for table in complete_table_payloads:
        all_tables[table["name"]] = table
    all_relationships.extend(complete_relationships)

    for spec in ACID_ER_DIAGRAM_SPECS:
        table_names = [name for name in spec["tables"] if name in ACID_RECOMMENDED_TABLES]
        entity_ids = acid_entity_ids_for_table_names(table_names)
        relationships = acid_relationships_for_tables(table_names)
        table_payloads = [
            acid_table_payload(name, ACID_RECOMMENDED_TABLES[name], entity_ids[name])
            for name in table_names
        ]
        diagrams.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "description": spec["description"],
                "is_complete": False,
                "tables": table_payloads,
                "relationships": relationships,
                "mermaid": acid_mermaid_er_source(table_names, relationships),
            }
        )
        for table in table_payloads:
            all_tables[table["name"]] = table
        all_relationships.extend(relationships)

    no_domain_tables = [
        row.get("legacy_table")
        for row in db_recommendations.get("rows", [])
        if row.get("target_model") == "NoCSharpDomainTable"
    ]
    relationship_keys = set()
    unique_relationships = []
    for row in all_relationships:
        key = (row["source"], row["target"], row["column"])
        if key in relationship_keys:
            continue
        relationship_keys.add(key)
        unique_relationships.append(row)
    return {
        "title": "Recommended ACID target model for legacy gaps",
        "description": (
            "Physical SQL table recommendations with columns, PK/FK/UK markers, and relationships. "
            "The diagrams are target-model proposals, not automatically generated EF migrations."
        ),
        "source": "db_table_recommendations.rows",
        "recommended_target_models": sorted(recommended_target_models),
        "mapped_legacy_tables": sorted(mapped_legacy_tables),
        "no_domain_tables": no_domain_tables,
        "diagrams": diagrams,
        "tables": sorted(all_tables.values(), key=lambda row: row["name"]),
        "relationships": unique_relationships,
        "counts": {
            "diagrams": len(diagrams),
            "tables": len(all_tables),
            "relationships": len(relationship_keys),
            "no_domain_tables": len(no_domain_tables),
        },
        "counts_by_implementation_status": dict(
            Counter(row["implementation_status"] for row in all_tables.values())
        ),
    }


def build_spec_coverage_overview(
    files: list[SqlFile], pdfs: list[dict], csharp_files: list[dict], requirements: list[dict]
) -> dict:
    rows = []
    for concept in SPEC_COVERAGE_OVERVIEW_CONCEPTS:
        row = {
            **concept,
            "pdf_source": rel(PDF_SOURCES[0]),
            "pdf_refs": find_spec_pdf_refs(pdfs, concept["spec_terms"], limit=4),
            "legacy_sql_evidence": sql_evidence_for_terms(files, concept["legacy_terms"], limit=8),
            "csharp_evidence": csharp_evidence_for_terms(csharp_files, concept["csharp_terms"], limit=8),
        }
        row["requirement_refs"] = requirement_refs_for_coverage_row(row, requirements)
        rows.append(
            row
        )
    counts = Counter(row["coverage"] for row in rows)
    return {
        "source_pdf": rel(PDF_SOURCES[0]),
        "coverage_definitions": {
            "Complete": "A clear C# domain, persistence, or API surface exists for this concept. This is not a full behavioral parity proof.",
            "Partial": "C# implements parts of the spec/legacy concept; fields, workflow steps, reports, integrations, or historical behavior remain open.",
            "Not found": "The static scan found no reliable C# implementation evidence.",
        },
        "counts": {key: counts.get(key, 0) for key in ["Complete", "Partial", "Not found"]},
        "rows": rows,
    }


def repo_refs(refs: list[tuple[str, Iterable[str], int]]) -> list[dict]:
    return [repo_file_ref(path, terms, fallback_line=fallback_line) for path, terms, fallback_line in refs]


def parse_csharp_table_constants() -> dict[str, str]:
    path = CSHARP_DATA_ROOT / "TableNames.cs"
    if not path.exists():
        return {}
    text = read_text(path)
    values = {}
    for match in re.finditer(r"const\s+string\s+(\w+)\s*=\s*nameof\((\w+)\)", text):
        values[match.group(1)] = match.group(2)
    return values


def parse_csharp_schema_constants() -> dict[str, str]:
    path = CSHARP_DATA_ROOT / "SchemaNames.cs"
    if not path.exists():
        return {}
    text = read_text(path)
    values = {}
    for match in re.finditer(r"const\s+string\s+(\w+)\s*=\s*\"([^\"]+)\"", text):
        values[match.group(1)] = match.group(2)
    return values


def parse_csharp_migration_tables() -> dict[str, set[str]]:
    schemas: dict[str, set[str]] = defaultdict(set)
    if not CSHARP_MIGRATIONS_ROOT.exists():
        return schemas
    for path in sorted(CSHARP_MIGRATIONS_ROOT.rglob("*.cs")):
        if path.name.endswith(".Designer.cs") or path.name.endswith("ModelSnapshot.cs"):
            continue
        text = read_text(path)
        for match in re.finditer(
            r"migrationBuilder\.CreateTable\(\s*name:\s*\"([^\"]+)\"(?:,\s*schema:\s*\"([^\"]+)\")?",
            text,
            re.S,
        ):
            table = match.group(1)
            schema = match.group(2) or "dbo/default"
            schemas[schema].add(table)
    if schemas:
        schemas["dbo/default"].add("__EFMigrationsHistory")
    return schemas


def parse_csharp_configuration_rows(table_constants: dict[str, str], schema_constants: dict[str, str]) -> list[dict]:
    rows = []
    if not CSHARP_CONFIGURATION_ROOT.exists():
        return rows
    for path in sorted(CSHARP_CONFIGURATION_ROOT.glob("*.cs")):
        text = read_text(path)
        entity_match = re.search(r"IEntityTypeConfiguration<([^>]+)>", text)
        class_match = re.search(r"class\s+(\w+)", text)
        table_matches = re.findall(r"\.ToTable\(TableNames\.(\w+)(?:,\s*SchemaNames\.(\w+))?", text)
        table_names = []
        for table_key, schema_key in table_matches:
            table_name = table_constants.get(table_key, table_key)
            schema_name = schema_constants.get(schema_key, "dbo/default") if schema_key else "dbo/default"
            table_names.append(f"{schema_name}.{table_name}" if schema_name != "dbo/default" else table_name)
        patterns = []
        for label, rx in (
            ("key mapping", r"\.HasKey\("),
            ("relationships", r"\.Has(?:One|Many)\("),
            ("owned values", r"\.Owns(?:One|Many)\("),
            ("value conversions", r"\.HasConversion\("),
            ("JSON columns", r"\.HasJsonConversion\("),
        ):
            if re.search(rx, text):
                patterns.append(label)
        entity_name = entity_match.group(1) if entity_match else (class_match.group(1).removesuffix("Configuration") if class_match else path.stem)
        rows.append(
            {
                "entity": entity_name,
                "configuration": path.stem,
                "tables": table_names,
                "patterns": patterns,
                "evidence": [{"file": rel(path), "line": first_line_for_any(text, ["ToTable", "HasKey", "IEntityTypeConfiguration"]) or 1}],
            }
        )
    return rows


def csharp_migration_count(context_folder: str) -> int:
    folder = CSHARP_MIGRATIONS_ROOT / context_folder
    if not folder.exists():
        return 0
    return sum(
        1
        for path in folder.glob("*.cs")
        if not path.name.endswith(".Designer.cs") and not path.name.endswith("ModelSnapshot.cs")
    )


def csharp_table_key(table: str, schema: str | None = None) -> str:
    return f"{schema}.{table}" if schema else table


def extract_csharp_method_body(text: str, method_name: str) -> str:
    match = re.search(rf"\b{re.escape(method_name)}\s*\([^)]*\)\s*\{{", text)
    if not match:
        return ""
    start = match.end() - 1
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            escaped = char == "\\" and not escaped
            if char == '"' and not escaped:
                in_string = False
            elif char != "\\":
                escaped = False
            continue
        if char == '"':
            in_string = True
            escaped = False
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return ""


def extract_csharp_calls(text: str, marker: str) -> list[str]:
    blocks = []
    for match in re.finditer(re.escape(marker) + r"\(", text):
        start = match.start()
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                escaped = char == "\\" and not escaped
                if char == '"' and not escaped:
                    in_string = False
                elif char != "\\":
                    escaped = False
                continue
            if char == '"':
                in_string = True
                escaped = False
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    if end < len(text) and text[end] == ";":
                        end += 1
                    blocks.append(text[start:end])
                    break
    return blocks


def parse_csharp_pk_columns(block: str) -> set[str]:
    match = re.search(r"table\.PrimaryKey\([^;]+?x\s*=>\s*new\s*\{([^}]+)\}", block, re.S)
    if match:
        return set(re.findall(r"x\.(\w+)", match.group(1)))
    match = re.search(r"table\.PrimaryKey\([^;]+?x\s*=>\s*x\.(\w+)", block, re.S)
    if match:
        return {match.group(1)}
    return set()


def parse_csharp_foreign_key(block: str, source_table: str, source_schema: str | None, file: str, line: int) -> dict | None:
    name_match = re.search(r'name:\s*"([^"]+)"', block)
    table_match = re.search(r'principalTable:\s*"([^"]+)"', block)
    if not table_match:
        return None
    schema_match = re.search(r'principalSchema:\s*"([^"]+)"', block)
    columns_match = re.search(r"columns:\s*x\s*=>\s*new\s*\{([^}]+)\}", block, re.S)
    if columns_match:
        columns = re.findall(r"x\.(\w+)", columns_match.group(1))
    else:
        column_match = re.search(r"column:\s*x\s*=>\s*x\.(\w+)", block)
        columns = [column_match.group(1)] if column_match else []
    if not columns:
        return None
    return {
        "source": csharp_table_key(source_table, source_schema),
        "target": csharp_table_key(table_match.group(1), schema_match.group(1) if schema_match else None),
        "column": "_".join(columns),
        "kind": "declared",
        "note": name_match.group(1) if name_match else "Migration foreign key",
        "evidence": [{"file": file, "line": line}],
    }


def parse_csharp_create_table(block: str, file: str, text: str) -> tuple[str, dict, list[dict]] | None:
    name_match = re.search(r'name:\s*"([^"]+)"', block)
    if not name_match:
        return None
    schema_match = re.search(r'schema:\s*"([^"]+)"', block)
    table = name_match.group(1)
    schema = schema_match.group(1) if schema_match else None
    table_key = csharp_table_key(table, schema)
    pk_columns = parse_csharp_pk_columns(block)
    columns: list[dict] = []
    column_block_match = re.search(r"columns:\s*table\s*=>\s*new\s*\{(.*?)\}\s*,\s*constraints:", block, re.S)
    if column_block_match:
        for column_match in re.finditer(
            r"^\s*(\w+)\s*=\s*table\.Column<([^>]+)>\(\s*type:\s*\"([^\"]+)\"",
            column_block_match.group(1),
            re.M,
        ):
            column_name = column_match.group(1)
            columns.append(
                {
                    "name": column_name,
                    "type": column_match.group(3),
                    "clr_type": column_match.group(2),
                    "is_primary_key": column_name in pk_columns,
                }
            )
    relationships = []
    for fk_block in extract_csharp_calls(block, "table.ForeignKey"):
        fk_line = line_number(text, text.find(fk_block)) if fk_block in text else line_number(text, text.find(block))
        relationship = parse_csharp_foreign_key(fk_block, table, schema, file, fk_line)
        if relationship:
            relationships.append(relationship)
    return (
        table_key,
        {
            "name": table_key,
            "table": table,
            "schema": schema or "dbo/default",
            "columns": columns,
            "evidence": [{"file": file, "line": line_number(text, text.find(block))}],
        },
        relationships,
    )


def parse_csharp_migration_model() -> dict:
    tables: dict[str, dict] = {}
    relationships: list[dict] = []
    if not CSHARP_MIGRATIONS_ROOT.exists():
        return {"tables": tables, "relationships": relationships}

    for path in sorted(CSHARP_MIGRATIONS_ROOT.rglob("*.cs")):
        if path.name.endswith(".Designer.cs") or path.name.endswith("ModelSnapshot.cs"):
            continue
        text = read_text(path)
        up_body = extract_csharp_method_body(text, "Up")
        file = rel(path)
        for block in extract_csharp_calls(up_body, "migrationBuilder.CreateTable"):
            parsed = parse_csharp_create_table(block, file, text)
            if not parsed:
                continue
            table_key, table, table_relationships = parsed
            tables[table_key] = table
            relationships.extend(table_relationships)

        for block in extract_csharp_calls(up_body, "migrationBuilder.AddColumn"):
            table_match = re.search(r'table:\s*"([^"]+)"', block)
            name_match = re.search(r'name:\s*"([^"]+)"', block)
            type_match = re.search(r'type:\s*"([^"]+)"', block)
            if not table_match or not name_match:
                continue
            table_key = table_match.group(1)
            if table_key not in tables:
                continue
            column_name = name_match.group(1)
            if any(column["name"] == column_name for column in tables[table_key]["columns"]):
                continue
            tables[table_key]["columns"].append(
                {
                    "name": column_name,
                    "type": type_match.group(1) if type_match else "nvarchar(max)",
                    "clr_type": "",
                    "is_primary_key": False,
                }
            )

        for block in extract_csharp_calls(up_body, "migrationBuilder.DropColumn"):
            table_match = re.search(r'table:\s*"([^"]+)"', block)
            name_match = re.search(r'name:\s*"([^"]+)"', block)
            if not table_match or not name_match:
                continue
            table_key = table_match.group(1)
            if table_key in tables:
                tables[table_key]["columns"] = [
                    column for column in tables[table_key]["columns"] if column["name"] != name_match.group(1)
                ]

        for block in extract_csharp_calls(up_body, "migrationBuilder.DropForeignKey"):
            name_match = re.search(r'name:\s*"([^"]+)"', block)
            if not name_match:
                continue
            fk_name = name_match.group(1)
            relationships = [relationship for relationship in relationships if relationship.get("note") != fk_name]

    if tables:
        tables["__EFMigrationsHistory"] = {
            "name": "__EFMigrationsHistory",
            "table": "__EFMigrationsHistory",
            "schema": "dbo/default",
            "columns": [
                {
                    "name": "MigrationId",
                    "type": "nvarchar(150)",
                    "clr_type": "string",
                    "is_primary_key": True,
                },
                {
                    "name": "ProductVersion",
                    "type": "nvarchar(32)",
                    "clr_type": "string",
                    "is_primary_key": False,
                },
            ],
            "evidence": [
                {
                    "file": "csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250725062156_InitialDbCreation.cs",
                    "line": 1,
                }
            ],
        }

    return {"tables": tables, "relationships": relationships}


def csharp_inferred_relationships() -> list[dict]:
    inferred_specs = [
        ("Orders", "OrderOwnerPersons", "OwnerId", "Domain/EF relationship from DirectiveOrder.Owner to person owner; no declared FK in migrations."),
        ("Orders", "OrderOwnerCompanies", "OwnerId", "Domain/EF relationship from DirectiveOrder.Owner to company owner; no declared FK in migrations."),
        ("Orders", "OrderRoutingAddresses", "OriginId", "Domain/EF relationship from DirectiveOrder.Origin to address routing; no declared FK in migrations."),
        ("Orders", "OrderRoutingPostOfficeBoxes", "OriginId", "Domain/EF relationship from DirectiveOrder.Origin to postbox routing; no declared FK in migrations."),
        ("Orders", "OrderRoutingAddresses", "DestinationId", "Domain/EF relationship from DirectiveOrder.Destination to address routing; no declared FK in migrations."),
        ("Orders", "OrderRoutingPostOfficeBoxes", "DestinationId", "Domain/EF relationship from DirectiveOrder.Destination to postbox routing; no declared FK in migrations."),
        ("OrderRoutingAddresses", "Addresses", "AddressId", "AddressId remains on the routing entity after the FK was dropped; review before treating it as enforced."),
    ]
    evidence = repo_refs(
        [
            ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["Owner", "Origin", "Destination"], 42),
            ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/OrderRoutingAddressConfiguration.cs", ["AddressId"], 16),
            ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250801172745_RemovedAddressFromOrderRoutingAddress.cs", ["DropForeignKey", "OrderRoutingAddresses"], 13),
        ]
    )
    return [
        {
            "source": source,
            "target": target,
            "column": column,
            "kind": "inferred",
            "note": note,
            "evidence": evidence,
        }
        for source, target, column, note in inferred_specs
    ]


def csharp_er_visible_columns(table: dict, relationships: list[dict], limit: int = 14) -> list[dict]:
    fk_columns = {relationship["column"] for relationship in relationships if relationship["source"] == table["name"]}
    relationship_columns = {
        relationship["column"]
        for relationship in relationships
        if relationship["source"] == table["name"] or relationship["target"] == table["name"]
    }
    priority = [
        column
        for column in table.get("columns", [])
        if column.get("is_primary_key")
        or column["name"] in relationship_columns
        or column["name"] in fk_columns
        or column["name"].endswith("Id")
    ]
    priority_names = {column["name"] for column in priority}
    return [*priority, *[column for column in table.get("columns", []) if column["name"] not in priority_names]][:limit]


def csharp_mermaid_column_line(column: dict, fk_columns: set[str]) -> str:
    name = mermaid_token(column["name"], "column")
    column_type = mermaid_type(column.get("type") or column.get("clr_type") or "STRING")
    if column.get("is_primary_key"):
        key_text = " PK"
    elif column["name"] in fk_columns or column["name"].endswith("Id"):
        key_text = " FK"
    else:
        key_text = ""
    return f"    {column_type} {name}{key_text}"


def csharp_er_diagram_specs(model: dict) -> list[dict]:
    relationships = [*model["relationships"], *csharp_inferred_relationships()]

    def rels_for(tables: list[str]) -> list[dict]:
        table_set = set(tables)
        return [
            row
            for row in relationships
            if row["source"] in table_set and row["target"] in table_set
        ]

    return [
        {
            "title": "C# Directive Order Domain ER Model",
            "description": "Main {PROJECT-NAME} order persistence around Orders, customer identity, owners, routing, addresses, and order participants. Solid relationships are declared migration FKs; dotted relationships are domain/EF links without declared FK constraints.",
            "tables": [
                "Orders",
                "CustomerIdentifications",
                "Customers",
                "Companies",
                "OrderOwnerPersons",
                "OrderOwnerCompanies",
                "OrderRoutingAddresses",
                "OrderRoutingPostOfficeBoxes",
                "Addresses",
            ],
            "relationships": rels_for(
                [
                    "Orders",
                    "CustomerIdentifications",
                    "Customers",
                    "Companies",
                    "OrderOwnerPersons",
                    "OrderOwnerCompanies",
                    "OrderRoutingAddresses",
                    "OrderRoutingPostOfficeBoxes",
                    "Addresses",
                ]
            ),
        },
        {
            "title": "C# Directive Catalog And Authorization ER Model",
            "description": "Directive/product catalog, subtype/shipment structures, JSON-backed lookups, and auth role/permission tables.",
            "tables": [
                "Directives",
                "ShipmentTypeGroups",
                "ShipmentTypes",
                "Lookups",
                "auth.Roles",
                "auth.Permissions",
                "auth.RolePermissions",
            ],
            "relationships": rels_for(
                [
                    "Directives",
                    "ShipmentTypeGroups",
                    "ShipmentTypes",
                    "Lookups",
                    "auth.Roles",
                    "auth.Permissions",
                    "auth.RolePermissions",
                ]
            ),
        },
        {
            "title": "C# Worker Queue ER Model",
            "description": "Worker-host persistence tables created by QueueDb migrations plus EF schema history. This is operational infrastructure, not a {PROJECT-NAME} business aggregate.",
            "tables": ["work.Lock", "work.Queue", "work.ScheduledTask", "__EFMigrationsHistory"],
            "relationships": rels_for(["work.Lock", "work.Queue", "work.ScheduledTask", "__EFMigrationsHistory"]),
        },
    ]


def csharp_mermaid_er_source(spec: dict, tables: dict[str, dict]) -> str:
    names = [name for name in spec["tables"] if name in tables]
    used: set[str] = set()
    entity_ids = {name: mermaid_identifier(name, used) for name in names}
    relationships = [
        relationship
        for relationship in spec["relationships"]
        if relationship["source"] in entity_ids and relationship["target"] in entity_ids
    ]
    lines = ["erDiagram"]
    lines.append("  %% Generated from C# EF migrations and configuration evidence.")
    for name in names:
        table = tables[name]
        entity_id = entity_ids[name]
        lines.append(f"  %% {entity_id} = {name}")
        lines.append(f"  {entity_id} {{")
        fk_columns = {
            relationship["column"]
            for relationship in relationships
            if relationship["source"] == name
        }
        visible_columns = csharp_er_visible_columns(table, relationships)
        for column in visible_columns:
            lines.append(csharp_mermaid_column_line(column, fk_columns))
        omitted = len(table.get("columns", [])) - len(visible_columns)
        if omitted > 0:
            lines.append(f"    STRING omitted_columns_{omitted}")
        lines.append("  }")
    if relationships:
        lines.append("  %% Solid = declared migration FK; dotted = domain/configuration relationship without declared FK.")
    for relationship in relationships:
        parent = entity_ids[relationship["target"]]
        child = entity_ids[relationship["source"]]
        connector = "||--o{" if relationship["kind"] == "declared" else "||..o{"
        label = mermaid_token(f'{relationship["column"]}_{relationship["kind"]}', "relates")
        lines.append(f"  {parent} {connector} {child} : {label}")
    return "\n".join(lines)


def build_csharp_er_diagrams(model: dict) -> list[dict]:
    tables = model["tables"]
    rows = []
    for spec in csharp_er_diagram_specs(model):
        names = [name for name in spec["tables"] if name in tables]
        relationships = [
            relationship
            for relationship in spec["relationships"]
            if relationship["source"] in names and relationship["target"] in names
        ]
        rows.append(
            {
                **spec,
                "tables": names,
                "table_count": len(names),
                "declared_relationship_count": sum(1 for relationship in relationships if relationship["kind"] == "declared"),
                "inferred_relationship_count": sum(1 for relationship in relationships if relationship["kind"] == "inferred"),
                "relationships": relationships,
                "mermaid": csharp_mermaid_er_source({**spec, "relationships": relationships}, tables),
                "table_inventory": [tables[name] for name in names],
            }
        )
    return rows


def legacy_csharp_table_coverage_specs() -> dict[str, dict]:
    return {
        "app.TDropOffLocation": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Lookups", "Orders"],
            "concepts": ["Abstellort -> asg-drop-off-location lookup", "Drop-off code/text -> Orders.Data JSON"],
            "rationale": "C# has ASG drop-off locations as JSON-backed lookup data configured by LookupConfiguration and stores the selected drop-off code/text inside polymorphic order data. This is the client-confirmed target surface; field-level parity for legacy aktiv, Sortierung, and Freitext_Zusatz still needs confirmation.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250822180238_UpdatedAsgDropOffLocationLookup.cs", ["asg-drop-off-location"], 12),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/ValueObjects/OrderData.cs", ["DropOffLocationCode", "SetDropOffLocation"], 50),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/LookupConfiguration.cs", ["Lookups", "HasJsonConversion"], 13),
                ]
            ),
        },
        "app.TOrderType": {
            "status": "Yes",
            "confidence": "high",
            "csharp_tables": ["Directives"],
            "concepts": ["Code -> Directives.Code", "Bezeichnung -> Directives.Name", "validity/settings -> Directives.Settings JSON", "product type -> DirectiveType"],
            "rationale": "The legacy order-type/catalog table is represented by the C# Directive aggregate and the EF-managed Directives table, including seeded product types and settings.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveAggregate/Directive.cs", ["DirectiveType", "Settings"], 34),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveConfiguration.cs", ["Directives", "Settings"], 14),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/InitialData.cs", ["GetDirectives", "DirectiveType"], 90),
                ]
            ),
        },
        "app.TPermission": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["auth.Roles", "auth.Permissions", "auth.RolePermissions"],
            "concepts": ["legacy flags -> new role/permission model", "Aktion/Typ -> permission names and roles"],
            "rationale": "C# has an authorization schema, but it is a new role/permission model rather than a direct copy of the legacy TPermission flag table.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/RoleConfiguration.cs", ["Roles", "RolePermissions"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/PermissionConfiguration.cs", ["Permissions", "auth"], 13),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/RoleAggregate/Role.cs", ["Role", "Permissions"], 7),
                ]
            ),
        },
        "app.TDestination": {
            "status": "Partial",
            "confidence": "high",
            "csharp_tables": ["OrderRoutingAddresses", "OrderRoutingPostOfficeBoxes", "Addresses", "Orders"],
            "concepts": ["PAC/PLZ/Ort/Strasse/Hnr -> Addresses", "Postfach/postlagernd -> OrderRoutingPostOfficeBoxes", "origin/destination -> Orders.OriginId/DestinationId"],
            "rationale": "C# models order routing with separate routing rows and an address master table. This covers the same origin/destination concept, but it is not a one-table legacy TDestination clone.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/Entities/OrderRouting.cs", ["OrderRoutingAddress", "OrderRoutingPostOfficeBox"], 20),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["Origin", "Destination"], 40),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/AddressConfiguration.cs", ["Pac", "PostalCode"], 20),
                ]
            ),
        },
        "app.TOrderDetail": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Customers", "Companies", "Orders"],
            "concepts": ["person/company participants -> Customers/Companies", "NeuerEmpfaenger/detail semantics -> order participant/data model"],
            "rationale": "C# has participant tables for customers and companies and a JSON order-data field, but there is no direct normalized equivalent of the legacy detail/person row table.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/CustomerConfiguration.cs", ["Customers", "ToTable"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/CompanyConfiguration.cs", ["Companies", "ToTable"], 13),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["Customers", "Companies", "Data"], 45),
                ]
            ),
        },
        "app.TOrderHead": {
            "status": "Yes",
            "confidence": "high",
            "csharp_tables": ["Orders", "CustomerIdentifications", "Customers", "Companies", "OrderOwnerPersons", "OrderOwnerCompanies", "OrderRoutingAddresses", "OrderRoutingPostOfficeBoxes"],
            "concepts": ["Formularnr -> FormulaNumber", "GueltigAb/GueltigBis -> ValidFrom/ValidTo", "FK_AuftragTyp -> Orders.Type", "Auftragtypdaten/contact -> Orders.Data JSON"],
            "rationale": "The C# DirectiveOrder aggregate and Orders table are the active replacement for the legacy order head concept. Related identity, owner, routing, customer, and company data are split into dedicated EF tables.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["FormulaNumber", "ValidityExampleRefod", "Data"], 45),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["Orders", "FormulaNumber"], 14),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250725062156_InitialDbCreation.cs", ["Orders", "FormulaNumber"], 167),
                ]
            ),
        },
        "app.TBoxMasterData": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Directives", "OrderRoutingPostOfficeBoxes", "Orders"],
            "concepts": ["Postfach products -> DirectiveType/PostOfficeBox directives", "postbox routing marker -> OrderRoutingPostOfficeBoxes"],
            "rationale": "C# has PostOfficeBox product types and a routing table for postbox destinations, but it does not currently show a dedicated EF table for legacy postbox master data such as PLZ/PF/size/status.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-SHAREDKERNEL-PROJECT}/Enums/DirectiveType.cs", ["PostOfficeBox"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/InitialData.cs", ["Postfach"], 199),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/OrderRoutingPostOfficeBoxConfiguration.cs", ["OrderRoutingPostOfficeBoxes"], 11),
                ]
            ),
        },
        "app.TBoxLocation": {
            "status": "No direct table",
            "confidence": "medium",
            "csharp_tables": [],
            "concepts": ["legacy postbox location master data"],
            "rationale": "No active C# EF table matching postbox-location master data was found. C# has postbox directive types and routing markers, but not the Standort/PLZ/address/location catalog table.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-SHAREDKERNEL-PROJECT}/Enums/DirectiveType.cs", ["PostOfficeBox"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/OrderRoutingPostOfficeBoxConfiguration.cs", ["OrderRoutingPostOfficeBoxes"], 11),
                ]
            ),
        },
        "app.TRegistrationFeedback": {
            "status": "No direct table",
            "confidence": "medium",
            "csharp_tables": [],
            "concepts": ["legacy registration feedback / customer-number feedback"],
            "rationale": "No EF table or domain aggregate dedicated to registration feedback was found in the C# persistence model.",
            "evidence": [],
        },
        "app.TSsoIdentification": {
            "status": "No direct table",
            "confidence": "medium",
            "csharp_tables": [],
            "concepts": ["SSO customer-number evidence appears in integration models, not as a table"],
            "rationale": "C# contains SSO/ExampleCrm integration fields, but the scanned EF model does not contain a dedicated TSsoIdentification-style persistence table.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Models/ExampleCrm/ExampleCrmContactMapping.cs", ["SSOCustomerNumber"], 25),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/Entities/CustomerIdentification.cs", ["CustomerIdentification"], 5),
                ]
            ),
        },
        "app.TBatchOrder": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Directives", "Orders"],
            "concepts": ["SAM product -> DirectiveType.CollectiveDomainConceptA", "bulk-import row storage -> no dedicated EF table found"],
            "rationale": "C# has the SAM directive type/catalog entry, but no dedicated EF table matching the legacy TBatchOrder import/staging rows was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-SHAREDKERNEL-PROJECT}/Enums/DirectiveType.cs", ["CollectiveDomainConceptA"], 10),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/InitialData.cs", ["Collective Example Domestic Order"], 155),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["Orders", "Data"], 14),
                ]
            ),
        },
        "app.TShipmentType": {
            "status": "Yes",
            "confidence": "high",
            "csharp_tables": ["ShipmentTypes"],
            "concepts": ["Code/name/orderable shipment choices -> ShipmentTypes"],
            "rationale": "C# represents shipment types as owned rows under the Directive aggregate and persists them in ShipmentTypes.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveAggregate/Entities/ShipmentType.cs", ["ShipmentType"], 6),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveConfiguration.cs", ["ShipmentTypes", "HasData"], 56),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/InitialData.cs", ["GetShipmentTypes"], 1),
                ]
            ),
        },
        "app.TShipmentTypeAssignment": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["ShipmentTypeGroups", "ShipmentTypes", "Orders"],
            "concepts": ["shipment selection/grouping -> ShipmentTypeGroups/ShipmentTypes", "order-specific selection -> Orders.Data JSON where used"],
            "rationale": "C# has shipment type catalog/group tables, but no direct normalized per-order join table equivalent to the legacy TShipmentTypeAssignment table was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveConfiguration.cs", ["ShipmentTypeGroups", "ShipmentTypes"], 40),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/ValueObjects/OrderData.cs", ["ShipmentTypeGroups"], 56),
                ]
            ),
        },
        "app.TShipmentOrder": {
            "status": "Yes",
            "confidence": "high",
            "csharp_tables": ["ShipmentTypeGroups", "ShipmentTypes", "Directives"],
            "concepts": ["order-type to shipment-type catalog mapping -> Directive shipment type groups"],
            "rationale": "The C# Directive aggregate owns shipment type groups and shipment types, which represent the catalog-side mapping between directives and allowed shipment choices.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveAggregate/Directive.cs", ["ShipmentTypeGroups"], 42),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveConfiguration.cs", ["ShipmentTypeGroups", "ShipmentTypes"], 40),
                ]
            ),
        },
        "app.TTitle": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["CustomerIdentifications", "Customers", "OrderOwnerPersons"],
            "concepts": ["title lookup values -> title string columns"],
            "rationale": "C# stores title prefixes/suffixes on identity/person rows, but no dedicated title lookup table equivalent to TTitle was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/Entities/CustomerIdentification.cs", ["TitlePrefix", "TitleSuffix"], 15),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/CustomerIdentificationConfiguration.cs", ["TitlePrefix", "TitleSuffix"], 44),
                ]
            ),
        },
        "app.TBilling": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Orders"],
            "concepts": ["payment/billing state -> Orders.PaymentStatus", "billing lifecycle/details -> no dedicated EF table found"],
            "rationale": "C# stores a coarse payment status on Orders, but no table equivalent to the detailed legacy billing/collection table was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["PaymentStatus"], 50),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["PaymentStatus"], 20),
                    ("csharp/src/backend/{BACKEND-SHAREDKERNEL-PROJECT}/Enums/DirectivePaymentStatus.cs", ["Unpaid", "Paid", "Pending"], 3),
                ]
            ),
        },
        "app.TBillingStatus": {
            "status": "Partial",
            "confidence": "medium",
            "csharp_tables": ["Orders"],
            "concepts": ["legacy billing status -> DirectivePaymentStatus enum / Orders.PaymentStatus"],
            "rationale": "C# has a payment-status enum and an Orders.PaymentStatus column, but no dedicated VerrechnungStatus lookup table.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-SHAREDKERNEL-PROJECT}/Enums/DirectivePaymentStatus.cs", ["Unpaid", "Paid", "Pending"], 3),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["PaymentStatus"], 20),
                ]
            ),
        },
        "dbo.TAutoNummer": {
            "status": "No direct table",
            "confidence": "medium",
            "csharp_tables": [],
            "concepts": ["legacy sequence/autonumber table -> formula number generated in code"],
            "rationale": "C# has formula-number generation logic, but no EF table equivalent to the legacy TAutoNummer counter table was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["SetFormulaNumber", "FormulaCodes"], 65),
                ]
            ),
        },
        "ref.RLocation": {
            "status": "No direct table",
            "confidence": "medium",
            "csharp_tables": [],
            "concepts": ["legacy provider Standort/location master data"],
            "rationale": "C# has address master data and ExampleRef/ExampleCrm integration models, but no EF table equivalent to the provider Standort reference table was found.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/AddressConfiguration.cs", ["Addresses", "Pac"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Models/ExampleRef/ExampleRefAddress.cs", ["ExampleRefAddress"], 1),
                ]
            ),
        },
    }


def build_legacy_csharp_table_coverage(files: list[SqlFile], migration_model: dict) -> list[dict]:
    specs = legacy_csharp_table_coverage_specs()
    csharp_tables = migration_model.get("tables", {})
    normalized_csharp_tables = {
        normalize(name): name
        for name in csharp_tables
    }
    normalized_csharp_bare_tables = {
        normalize(name.split(".")[-1]): name
        for name in csharp_tables
    }
    rows = []
    for sql_file in sorted((item for item in files if item.category == "Table" and not item.generated), key=lambda item: item.primary_object):
        legacy_object = sql_file.primary_object
        legacy_bare = legacy_object.split(".")[-1]
        spec = specs.get(legacy_object)
        exact_match = normalized_csharp_tables.get(normalize(legacy_object)) or normalized_csharp_bare_tables.get(normalize(legacy_bare))
        if exact_match and not spec:
            spec = {
                "status": "Exact",
                "confidence": "high",
                "csharp_tables": [exact_match],
                "concepts": ["same table name in active C# EF migrations"],
                "rationale": "The active C# EF migrations contain a table with the same legacy table name.",
                "evidence": csharp_tables[exact_match].get("evidence", []),
            }
        if not spec:
            spec = {
                "status": "No direct table",
                "confidence": "medium",
                "csharp_tables": [],
                "concepts": [],
                "rationale": "No exact table name or curated C# domain-table equivalent was found in the active C# EF migration model.",
                "evidence": [],
            }
        csharp_table_names = [name for name in spec.get("csharp_tables", []) if name in csharp_tables]
        csharp_columns = sorted(
            {
                column["name"]
                for table_name in csharp_table_names
                for column in csharp_tables.get(table_name, {}).get("columns", [])
            }
        )
        rows.append(
            {
                "legacy_table": legacy_object,
                "legacy_path": sql_file.rel,
                "legacy_columns": [column["name"] for column in sql_file.columns],
                "status": spec["status"],
                "confidence": spec["confidence"],
                "csharp_tables": csharp_table_names,
                "concepts": spec.get("concepts", []),
                "rationale": spec["rationale"],
                "csharp_columns": csharp_columns,
                "legacy_evidence": [
                    {
                        "file": sql_file.rel,
                        "line": next((definition["line"] for definition in sql_file.definitions if definition["kind"] == "TABLE"), 1),
                    }
                ],
                "csharp_evidence": spec.get("evidence", []),
            }
        )
    return rows


def build_csharp_sql_model(files: list[SqlFile]) -> dict:
    table_constants = parse_csharp_table_constants()
    schema_constants = parse_csharp_schema_constants()
    migration_schemas = parse_csharp_migration_tables()
    configuration_rows = parse_csharp_configuration_rows(table_constants, schema_constants)
    migration_model = parse_csharp_migration_model()
    csharp_er_diagrams = build_csharp_er_diagrams(migration_model)
    legacy_table_coverage = build_legacy_csharp_table_coverage(files, migration_model)
    raw_sql_files = sorted(rel(path) for path in CSHARP_ROOT.rglob("*.sql")) if CSHARP_ROOT.exists() else []
    ps_sql_scripts = [
        rel(path)
        for path in sorted((CSHARP_ROOT / "azure" / "scripts").glob("*.ps1"))
        if term_count(read_text(path), "SqlConnection") or term_count(read_text(path), "SELECT") or term_count(read_text(path), "DELETE")
    ] if (CSHARP_ROOT / "azure" / "scripts").exists() else []

    summary = [
        {
            "topic": "Active database technology",
            "answer": "The active C# backend uses Entity Framework Core migrations with SQL Server, not imported legacy .sql files as deployable migrations.",
            "evidence": repo_refs(
                [
                    ("csharp/README.md", ["Entity Framework Core Migrations", "SQL Server"], 16),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/DependencyInjection.cs", ["UseSqlServer", "DirectivesDbContext"], 84),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/{BACKEND-INFRASTRUCTURE-PROJECT}.csproj", ["Microsoft.EntityFrameworkCore.SqlServer"], 18),
                ]
            ),
        },
        {
            "topic": "Application DbContext",
            "answer": "DirectivesDbContext is the main application persistence context. It exposes DbSets for DirectiveOrder, Directive, Address, Lookup, and Role, then applies EF configurations from the infrastructure assembly.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/DirectivesDbContext.cs", ["DbSet", "ApplyConfigurationsFromAssembly"], 10),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["ToTable", "Orders"], 16),
                ]
            ),
        },
        {
            "topic": "Database schema",
            "answer": "Yes. The C# code has an EF-managed schema: a default/dbo-style directives schema, an auth schema for roles/permissions, and a work schema for queue/worker infrastructure.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/TableNames.cs", ["Orders", "Directives"], 5),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/SchemaNames.cs", ["auth"], 5),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/QueueDb/20250725062214_InitialDbCreation.cs", ["EnsureSchema", "work"], 13),
                ]
            ),
        },
        {
            "topic": "Domain model",
            "answer": "Yes. The C# backend has a DDD-style domain model with aggregate roots for directive orders, directives, addresses, lookups, and roles, plus value objects and child entities mapped by EF Core.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["AggregateRoot", "DirectiveOrder"], 10),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveAggregate/Directive.cs", ["AggregateRoot", "Directive"], 10),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/AddressAggregate/Address.cs", ["AggregateRoot", "Address"], 9),
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/Common/Models/ValueObject.cs", ["ValueObject"], 3),
                ]
            ),
        },
        {
            "topic": "Repository boundary",
            "answer": "Application-layer repository interfaces are implemented by infrastructure repositories backed by DirectivesDbContext; SQL access is primarily EF LINQ rather than hand-written SQL.",
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-APPLICATION-PROJECT}/Abstractions/Repositories/IDirectiveOrderRepository.cs", ["IDirectiveOrderRepository"], 8),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Repositories/DirectiveOrderRepository.cs", ["DirectivesDbContext", "DirectiveOrderRepository"], 15),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/DependencyInjection.cs", ["AddRepositories", "DirectiveOrderRepository"], 46),
                ]
            ),
        },
        {
            "topic": "Raw SQL in csharp/",
            "answer": (
                f"No standalone .sql files were found under csharp/. The SQL-like code in this area is limited to EF-generated migrations plus PowerShell maintenance/deployment scripts ({len(ps_sql_scripts)} scripts detected)."
            ),
            "evidence": repo_refs(
                [
                    ("csharp/azure/scripts/delete_orders_from_db.ps1", ["DELETE FROM dbo.Orders", "SqlConnection"], 33),
                    ("csharp/azure/scripts/deploy_sql_permissions.ps1", ["sys.database_principals", "SqlConnection"], 144),
                ]
            ),
        },
    ]

    schema_rows = []
    schema_roles = {
        "dbo/default": "Application directive/order persistence tables generated by DirectivesDb migrations.",
        "auth": "Authorization tables for roles, permissions, and role-permission joins.",
        "work": "Worker-host queue, lock, and scheduled-task infrastructure tables.",
    }
    for schema, tables in sorted(migration_schemas.items()):
        schema_rows.append(
            {
                "schema": schema,
                "role": schema_roles.get(schema, "Schema discovered from EF migrations."),
                "tables": sorted(tables),
                "evidence": repo_refs(
                    [
                        (
                            "csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250725062156_InitialDbCreation.cs"
                            if schema != "work"
                            else "csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/QueueDb/20250725062214_InitialDbCreation.cs",
                            [schema if schema != "dbo/default" else next(iter(tables), "CreateTable"), "CreateTable"],
                            13,
                        )
                    ]
                ),
            }
        )

    domain_rows = [
        {
            "model": "DirectiveOrder aggregate",
            "role": "Central order aggregate for captured directive orders, validity, owner/origin/destination/customer identity, formula number, payment status, and product-specific data.",
            "mapped_tables": ["Orders", "CustomerIdentifications", "OrderOwnerPersons", "OrderOwnerCompanies", "OrderRoutingAddresses", "OrderRoutingPostOfficeBoxes", "Customers", "Companies"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveOrderAggregate/DirectiveOrder.cs", ["DirectiveOrder", "AggregateRoot"], 10),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveOrderConfiguration.cs", ["Orders", "HasOne"], 16),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/DirectivesDb/20250725062156_InitialDbCreation.cs", ["Orders", "CustomerIdentificationId"], 167),
                ]
            ),
        },
        {
            "model": "Directive aggregate",
            "role": "Product/catalog model for directive types, settings, subtypes, shipment type groups, and shipment types.",
            "mapped_tables": ["Directives", "ShipmentTypeGroups", "ShipmentTypes"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/DirectiveAggregate/Directive.cs", ["Directive", "AggregateRoot"], 10),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/DirectiveConfiguration.cs", ["ShipmentTypeGroups", "ShipmentTypes"], 40),
                ]
            ),
        },
        {
            "model": "Address aggregate",
            "role": "Persisted address master data used by order routing addresses; includes PAC, postal code, city, street, house number, validity, and row hash data.",
            "mapped_tables": ["Addresses"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/AddressAggregate/Address.cs", ["Address", "AggregateRoot"], 9),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/AddressConfiguration.cs", ["Addresses", "Pac"], 13),
                ]
            ),
        },
        {
            "model": "Lookup aggregate",
            "role": "JSON-backed lookup data used for application lookup lists.",
            "mapped_tables": ["Lookups"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/LookupAggregate/Lookup.cs", ["Lookup", "AggregateRoot"], 6),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/LookupConfiguration.cs", ["Lookups", "HasJsonConversion"], 14),
                ]
            ),
        },
        {
            "model": "Role aggregate",
            "role": "Application authorization model with roles, permissions, and many-to-many role-permission mapping under the auth schema.",
            "mapped_tables": ["auth.Roles", "auth.Permissions", "auth.RolePermissions"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-DOMAIN-PROJECT}/RoleAggregate/Role.cs", ["Role", "AggregateRoot"], 7),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/RoleConfiguration.cs", ["Roles", "RolePermissions"], 13),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Data/Configuration/PermissionConfiguration.cs", ["Permissions", "auth"], 13),
                ]
            ),
        },
        {
            "model": "Queue/work infrastructure model",
            "role": "Operational queue and lock tables supplied by the worker-host EF package; it is infrastructure persistence, not a {PROJECT-NAME} business aggregate.",
            "mapped_tables": ["work.Lock", "work.Queue", "work.ScheduledTask", "__EFMigrationsHistory"],
            "evidence": repo_refs(
                [
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/DependencyInjection.cs", ["UseMessageQueueEFCore", "QueueNames"], 155),
                    ("csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Migrations/QueueDb/20250725062214_InitialDbCreation.cs", ["Queue", "ScheduledTask"], 17),
                ]
            ),
        },
    ]

    repository_rows = []
    for interface_name, implementation_name in (
        ("IDirectiveOrderRepository", "DirectiveOrderRepository"),
        ("IDirectiveRepository", "DirectiveRepository"),
        ("IAddressRepository", "AddressRepository"),
        ("ILookupRepository", "LookupRepository"),
        ("IRoleRepository", "RoleRepository"),
    ):
        repository_rows.append(
            {
                "interface": interface_name,
                "implementation": implementation_name,
                "evidence": repo_refs(
                    [
                        (f"csharp/src/backend/{BACKEND-APPLICATION-PROJECT}/Abstractions/Repositories/{interface_name}.cs", [interface_name], 1),
                        (f"csharp/src/backend/{BACKEND-INFRASTRUCTURE-PROJECT}/Repositories/{implementation_name}.cs", [implementation_name, "DirectivesDbContext"], 1),
                    ]
                ),
            }
        )

    return {
        "summary": summary,
        "raw_sql_files": raw_sql_files,
        "powershell_sql_scripts": ps_sql_scripts,
        "migration_counts": {
            "DirectivesDb": csharp_migration_count("DirectivesDb"),
            "QueueDb": csharp_migration_count("QueueDb"),
        },
        "table_constants": sorted(table_constants.values()),
        "schema_constants": schema_constants,
        "schemas": schema_rows,
        "domain_model": domain_rows,
        "configuration_rows": configuration_rows,
        "repository_rows": repository_rows,
        "er_diagrams": csharp_er_diagrams,
        "legacy_table_coverage": legacy_table_coverage,
    }


def function_basename(sql_file: SqlFile) -> str:
    return normalize(sql_file.primary_object.split(".")[-1])


def extract_sql_comment_summary(text: str) -> str:
    lines = text.splitlines()
    capture = False
    parts = []
    for line in lines[:45]:
        stripped = line.strip()
        if stripped.startswith("-- Description:"):
            capture = True
            parts.append(stripped.removeprefix("-- Description:").strip())
            continue
        if capture:
            if stripped.startswith("-- Applikation") or stripped.startswith("-- Change") or stripped.startswith("-- ====="):
                break
            if stripped.startswith("--"):
                value = stripped.removeprefix("--").strip()
                if value:
                    parts.append(value)
            elif stripped:
                break
    return compact(" ".join(parts), 240)


def function_return_shape(text: str) -> str:
    if re.search(r"\bEXTERNAL\s+NAME\b", text, re.I):
        if re.search(r"\bRETURNS\s+(?:@\w+\s+)?TABLE\b|\bRETURNS\s*\n\s*TABLE\b", text, re.I):
            return "CLR/provider table-valued function"
        return "CLR/provider scalar function"
    if re.search(r"\bRETURNS\s+@\w+\s+TABLE\b", text, re.I):
        return "Multi-statement table-valued function"
    if re.search(r"\bRETURNS\s+TABLE\b", text, re.I):
        return "Inline table-valued function"
    match = re.search(r"\bRETURNS\s+([A-Za-z0-9_\[\]\(\), ]+)", text, re.I)
    if match:
        return f"Scalar function returning {' '.join(match.group(1).split())}"
    return "Function"


def classify_function_group(sql_file: SqlFile) -> dict:
    override = FUNCTION_GROUP_OVERRIDES.get(function_basename(sql_file))
    if override:
        return next(group for group in FUNCTION_BUSINESS_GROUPS if group["name"] == override)
    haystack = normalize(f"{sql_file.primary_object} {sql_file.rel} {extract_sql_comment_summary(sql_file.text)}")
    best_group = FUNCTION_BUSINESS_GROUPS[-1]
    best_score = -1
    for group in FUNCTION_BUSINESS_GROUPS:
        score = sum(1 for pattern in group["patterns"] if normalize(pattern) in haystack or term_count(sql_file.text, pattern))
        if score > best_score:
            best_group = group
            best_score = score
    return best_group


def build_function_business_logic(files: list[SqlFile], pdfs: list[dict]) -> dict:
    function_files = [sql_file for sql_file in files if sql_file.category == "Function"]
    details = []
    grouped: dict[str, list[SqlFile]] = defaultdict(list)
    for sql_file in function_files:
        group = classify_function_group(sql_file)
        grouped[group["name"]].append(sql_file)
        base = function_basename(sql_file)
        role = FUNCTION_ROLE_HINTS.get(base, group["logic"])
        comment = extract_sql_comment_summary(sql_file.text)
        evidence_terms = [sql_file.primary_object.split(".")[-1], "CREATE FUNCTION", *group["patterns"]]
        details.append(
            {
                "object": sql_file.primary_object,
                "file": sql_file.rel,
                "line": next((definition["line"] for definition in sql_file.definitions if definition["kind"] == "FUNCTION"), 1),
                "group": group["name"],
                "return_shape": function_return_shape(sql_file.text),
                "comment": comment,
                "business_logic": role,
                "dependencies": sorted(sql_file.dependencies)[:10],
                "external_refs": sorted(sql_file.external_refs)[:10],
                "risk_flags": sql_file.risk_flags,
                "source_refs": [
                    {
                        "file": sql_file.rel,
                        "line": first_line_for_any(sql_file.text, evidence_terms) or 1,
                    }
                ],
            }
        )

    group_rows = []
    for group in FUNCTION_BUSINESS_GROUPS:
        matched = sorted(grouped.get(group["name"], []), key=lambda item: item.primary_object)
        if not matched:
            continue
        evidence = [
            {
                "file": sql_file.rel,
                "line": first_line_for_any(sql_file.text, [sql_file.primary_object.split(".")[-1], *group["patterns"]]) or 1,
            }
            for sql_file in matched[:10]
        ]
        group_rows.append(
            {
                "name": group["name"],
                "count": len(matched),
                "logic": group["logic"],
                "review": group["review"],
                "functions": [sql_file.primary_object for sql_file in matched],
                "pdf_refs": find_pdf_refs(pdfs, group["pdf_terms"], limit=4),
                "evidence": evidence,
            }
        )

    return {"groups": group_rows, "details": sorted(details, key=lambda item: (item["group"], item["object"]))}


def build_diagram_sources(files: list[SqlFile], pdfs: list[dict], legacy_code: dict) -> list[dict]:
    return [
        {
            "diagram": "Core Persistence Hypothesis",
            "answer": (
                "The persistence shape is inferred from SQL, and Legacy code source now provides static call-site "
                "evidence for P_STORE_ORDER_XML. It still does not prove production runtime frequency, scheduled "
                "execution, or every reachable UI path."
            ),
            "source_basis": "Legacy SQL stored procedures and table definitions, plus static Legacy code call-site evidence.",
            "pdf_refs": find_pdf_refs(pdfs, ["Protokollierung", "Neuerfassung", "Storno", "Formular-/Vorausverfügungstypen"], limit=4),
            "file_refs": [
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["CREATE PROCEDURE", "P_STORE_ORDER_XML"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["EXEC app.SetShipmentType"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["EXEC app.SetDestination"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["EXEC app.clr_extperson_setPerson"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["EXEC app.SetDetail"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/P_STORE_ORDER_XML.sql", ["EXEC app.WriteLog"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Tables/TOrderHead.sql", ["CREATE TABLE"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Tables/TOrderDetail.sql", ["CREATE TABLE"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Tables/TDestination.sql", ["CREATE TABLE"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Tables/TBilling.sql", ["CREATE TABLE"]),
                *[
                    {"file": call["file"], "line": call["line"]}
                    for call in legacy_code.get("stored_proc_calls", [])
                    if call.get("matched_object") == "app.P_STORE_ORDER_XML"
                ][:6],
            ],
        },
        {
            "diagram": "Print Datafile Flow",
            "answer": (
                "This diagram has two source types: the datafile contract and record families come from the Print Spec Document; "
                "the concrete legacy implementation flow comes from SQL procedure/function files such as LabelPrint "
                "and FilterByOrderLabels."
            ),
            "source_basis": "Print Spec Document for K/N/D/E contract; legacy SQL for implementation and batching/person lookup.",
            "pdf_refs": find_pdf_refs(
                pdfs,
                ["Datenübermittlung an Druckdienstleister", "Dateibeschreibung", "K-Satz", "N-Satz", "D-Satz", "E-Satz"],
                limit=6,
                min_page=4,
            ),
            "file_refs": [
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/LabelPrint.sql", ["CREATE PROCEDURE", "LabelPrint"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/LabelPrint.sql", ["app.FilterByOrderLabels"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/LabelPrint.sql", ["clr_extperson_getPerson_tran"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Stored Procedures/LabelPrint.sql", ["TEnvelope_BAA"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/FilterByOrderLabels.sql", ["CREATE FUNCTION", "FilterByOrderLabels"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/FilterByOrderLabels.sql", ["WHEN 'K'"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/FilterByOrderLabels.sql", ["WHEN 'N'"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/FilterByOrderLabels.sql", ["GetLabelCount"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/GetPrintDate.sql", ["CREATE FUNCTION", "GetPrintDate"]),
                repo_file_ref("legacy-sql/{LEGACY-DB-NAME}/app/Functions/GetItemsPerEnvelope.sql", ["CREATE FUNCTION", "GetItemsPerEnvelope"]),
            ],
        },
    ]


def build_product_sql_mapping(files: list[SqlFile], pdfs: list[dict]) -> list[dict]:
    core_terms = ["TOrderHead", "TOrderDetail", "TDestination", "TOrderType", "TShipmentType", "P_STORE_ORDER_XML"]
    rows = []
    for product in PRODUCTS:
        scored = []
        terms = [*product["terms"], product["code"], product["name"]]
        for sql_file in files:
            score = score_file(sql_file.text, terms)
            core_score = score_file(sql_file.text, core_terms)
            if score:
                scored.append((score * 3 + core_score, sql_file))
        scored.sort(key=lambda item: (-item[0], item[1].rel))
        evidence = [
            {
                "object": sql_file.primary_object,
                "file": sql_file.rel,
                "line": first_line_for_any(sql_file.text, terms) or 1,
                "category": sql_file.category,
            }
            for _, sql_file in scored[:10]
        ]
        rows.append(
            {
                **product,
                "pdf_refs": find_pdf_refs(pdfs, [product["code"], product["name"], *product["terms"]], limit=8),
                "evidence": evidence,
                "evidence_count": len(scored),
            }
        )
    return rows


def dependency_rank(files: list[SqlFile]) -> list[dict]:
    inbound = Counter()
    outbound = Counter()
    for sql_file in files:
        outbound[sql_file.primary_object] = len(sql_file.dependencies)
        for dep in sql_file.dependencies:
            inbound[dep] += 1
    rows = []
    objects = set(inbound) | set(outbound)
    for obj in objects:
        rows.append({"object": obj, "inbound": inbound[obj], "outbound": outbound[obj], "score": inbound[obj] * 3 + outbound[obj]})
    return sorted(rows, key=lambda row: (-row["score"], row["object"]))[:30]


def count_by_category(files: list[SqlFile]) -> Counter:
    return Counter(sql_file.category for sql_file in files)


def count_by_schema(files: list[SqlFile]) -> Counter:
    counts = Counter()
    for sql_file in files:
        for definition in sql_file.definitions:
            name = definition["name"]
            schema = name.split(".")[0] if "." in name else "(none)"
            counts[schema] += 1
    return counts


def svg_bar_chart(counts: Counter, title: str, width: int = 780) -> str:
    rows = counts.most_common()
    if not rows:
        return ""
    bar_area = 520
    row_h = 32
    height = 54 + row_h * len(rows)
    max_count = max(count for _, count in rows) or 1
    parts = [
        f'<svg class="diagram" viewBox="0 0 {width} {height}" role="img" aria-label="{html_escape(title)}">',
        f'<text x="24" y="30" class="svg-title">{html_escape(title)}</text>',
    ]
    y = 54
    for label, count in rows:
        bar_w = int(bar_area * count / max_count)
        parts.append(f'<text x="24" y="{y + 18}" class="svg-label">{html_escape(label)}</text>')
        parts.append(f'<rect x="230" y="{y}" width="{bar_w}" height="22" rx="4" class="svg-bar"></rect>')
        parts.append(f'<text x="{240 + bar_w}" y="{y + 17}" class="svg-count">{count}</text>')
        y += row_h
    parts.append("</svg>")
    return "\n".join(parts)


def svg_core_flow() -> str:
    boxes = [
        (35, 24, 180, 58, "XML input", "exampleforwardingauftrag"),
        (280, 24, 220, 58, "P_STORE_ORDER_XML", "save/import orchestrator"),
        (585, 0, 150, 52, "TOrderHead", "order head"),
        (585, 64, 150, 52, "TOrderDetail", "persons/details"),
        (585, 128, 150, 52, "TDestination", "from/to address"),
        (585, 192, 150, 52, "TBilling", "billing"),
        (280, 142, 220, 58, "External API/CLR wrappers", "person persistence/search"),
        (35, 142, 180, 58, "WriteLog / TLog", "audit trail"),
    ]
    arrows = [
        (215, 53, 280, 53),
        (500, 53, 585, 26),
        (500, 53, 585, 90),
        (500, 53, 585, 154),
        (500, 53, 585, 218),
        (390, 82, 390, 142),
        (280, 171, 215, 171),
    ]
    parts = ['<svg class="diagram wide" viewBox="0 0 780 270" role="img" aria-label="Core SQL save workflow">']
    parts.append('<defs><marker id="arrow2" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" class="svg-arrowhead"/></marker></defs>')
    for x1, y1, x2, y2 in arrows:
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="svg-arrow" marker-end="url(#arrow2)"></line>')
    for x, y, w, h, title, subtitle in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="svg-box"></rect>')
        parts.append(f'<text x="{x + 12}" y="{y + 24}" class="svg-box-title">{html_escape(title)}</text>')
        parts.append(f'<text x="{x + 12}" y="{y + 44}" class="svg-label">{html_escape(subtitle)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def svg_print_flow() -> str:
    boxes = [
        (30, 28, 160, 58, "LabelPrint", "procedure"),
        (250, 28, 200, 58, "FilterByOrderLabels", "K/N data rows"),
        (510, 28, 170, 58, "External API person data", "D/E rows"),
        (250, 134, 200, 58, "Pipe-delimited output", "K, N, D, E records"),
        (510, 134, 170, 58, "Print provider", "official contract"),
        (30, 134, 160, 58, "TEnvelope_BAA", "tracking insert"),
    ]
    arrows = [(190, 57, 250, 57), (450, 57, 510, 57), (350, 86, 350, 134), (450, 163, 510, 163), (110, 86, 110, 134)]
    parts = ['<svg class="diagram wide" viewBox="0 0 720 225" role="img" aria-label="Print datafile flow">']
    parts.append('<defs><marker id="arrow3" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" class="svg-arrowhead"/></marker></defs>')
    for x1, y1, x2, y2 in arrows:
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="svg-arrow" marker-end="url(#arrow3)"></line>')
    for x, y, w, h, title, subtitle in boxes:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="svg-box"></rect>')
        parts.append(f'<text x="{x + 12}" y="{y + 24}" class="svg-box-title">{html_escape(title)}</text>')
        parts.append(f'<text x="{x + 12}" y="{y + 44}" class="svg-label">{html_escape(subtitle)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def table_lookup(files: list[SqlFile]) -> dict[str, SqlFile]:
    return {sql_file.primary_object: sql_file for sql_file in files if sql_file.category == "Table"}


def display_columns(sql_file: SqlFile, limit: int = 7) -> list[str]:
    columns = [column["name"] for column in sql_file.columns[:limit]]
    if len(sql_file.columns) > limit:
        columns.append(f"+{len(sql_file.columns) - limit} more")
    return columns


def inferred_relationships(table_files: list[SqlFile]) -> list[dict]:
    declared = {
        (sql_file.primary_object, fk["column"], fk["target"])
        for sql_file in table_files
        for fk in sql_file.fks
    }
    rules = {
        "FK_OrderHead": "app.TOrderHead",
        "FK_OrderHeadID": "app.TOrderHead",
        "FK_OrderheadID": "app.TOrderHead",
        "Datensatz_ID": "app.TOrderHead",
        "FK_AuftragTyp": "app.TOrderType",
        "FK_Status": {
            "app.TBilling": "app.TBillingStatus",
            "app.TBoxMasterData": "app.TBoxStatus",
        },
        "FK_LogTyp": "app.TOrderChangeReason",
        "Verantwortliche_Dienststelle": "ref.RLocation",
        "Dienststelle_Postlagernd": "ref.RLocation",
        "FK_Person": "ExtPersonDb.Person",
    }
    rows = []
    table_names = {sql_file.primary_object for sql_file in table_files}
    for sql_file in table_files:
        for column in sql_file.columns:
            target_rule = rules.get(column["name"])
            if not target_rule:
                continue
            target = target_rule.get(sql_file.primary_object) if isinstance(target_rule, dict) else target_rule
            if not target:
                continue
            if (sql_file.primary_object, column["name"], target) in declared:
                continue
            if target not in table_names and not target.startswith("ExtPersonDb"):
                continue
            rows.append(
                {
                    "source": sql_file.primary_object,
                    "target": target,
                    "column": column["name"],
                    "kind": "inferred",
                    "note": "Inferred from column name; no FK constraint was extracted from the SQL file.",
                }
            )
    return rows


def all_relationships(table_files: list[SqlFile]) -> list[dict]:
    rows = []
    for sql_file in table_files:
        for fk in sql_file.fks:
            rows.append(
                {
                    "source": sql_file.primary_object,
                    "target": fk["target"],
                    "column": fk["column"],
                    "kind": "declared",
                    "note": fk["name"],
                }
            )
    rows.extend(inferred_relationships(table_files))
    return rows


def er_diagram_specs(table_files: list[SqlFile]) -> list[dict]:
    relationships = all_relationships(table_files)

    def rels_for(tables: list[str]) -> list[dict]:
        table_set = set(tables)
        return [
            row
            for row in relationships
            if row["source"] in table_set and (row["target"] in table_set or row["target"].startswith("ExtPersonDb"))
        ]

    return [
        {
            "title": "Core Order ER Model",
            "description": "Head, detail, address, type, delivery-type, log, and branch/location tables around the central legacy order.",
            "tables": [
                "app.TOrderHead",
                "app.TOrderType",
                "app.TOrderDetail",
                "app.TDestination",
                "app.TShipmentTypeAssignment",
                "app.TShipmentType",
                "app.TShipmentOrder",
                "ref.RLocation",
                "dbo.TLog",
                "app.TOrderChangeReason",
            ],
            "relationships": rels_for(
                [
                    "app.TOrderHead",
                    "app.TOrderType",
                    "app.TOrderDetail",
                    "app.TDestination",
                    "app.TShipmentTypeAssignment",
                    "app.TShipmentType",
                    "app.TShipmentOrder",
                    "ref.RLocation",
                    "dbo.TLog",
                    "app.TOrderChangeReason",
                ]
            ),
        },
        {
            "title": "Billing, Postbox, SSO, And Bulk Import ER Model",
            "description": "Tables that extend orders with billing/open collection, postbox, SSO identity/deletion, and BatchOrder import data.",
            "tables": [
                "app.TOrderHead",
                "app.TBilling",
                "app.TBillingStatus",
                "app.TBoxMasterData",
                "app.TBoxStatus",
                "app.TBoxLocation",
                "app.TBatchOrder",
                "app.TSsoIdentification",
                "app.TSsoDeletion",
            ],
            "relationships": rels_for(
                [
                    "app.TOrderHead",
                    "app.TBilling",
                    "app.TBillingStatus",
                    "app.TBoxMasterData",
                    "app.TBoxStatus",
                    "app.TBoxLocation",
                    "app.TBatchOrder",
                    "app.TSsoIdentification",
                    "app.TSsoDeletion",
                ]
            ),
        },
        {
            "title": "Operations And Reference Tables",
            "description": "Security, counters, service information, schema-change logging, and reference/master-data tables used around the core model.",
            "tables": [
                "app.TPermission",
                "dbo.TAutoNummer",
                "dbo.TLog",
                "dbo._DBSchema_Log",
                "app.TServiceInfo",
                "app.TDropOffLocation",
                "app.TTitle",
                "ref.RLocation",
            ],
            "relationships": rels_for(
                [
                    "app.TPermission",
                    "dbo.TAutoNummer",
                    "dbo.TLog",
                    "dbo._DBSchema_Log",
                    "app.TServiceInfo",
                    "app.TDropOffLocation",
                    "app.TTitle",
                    "ref.RLocation",
                ]
            ),
        },
    ]


def mermaid_identifier(value: str, used: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_")
    base = re.sub(r"_+", "_", base) or "entity"
    if base[0].isdigit():
        base = f"entity_{base}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def mermaid_token(value: str, default: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_")
    token = re.sub(r"_+", "_", token)
    if not token:
        return default
    if token[0].isdigit():
        token = f"{default}_{token}"
    return token


def mermaid_type(value: str) -> str:
    value = value.replace("[", "").replace("]", "").upper()
    return mermaid_token(value, "UNKNOWN")


def er_visible_columns(sql_file: SqlFile, relationships: list[dict], limit: int = 14) -> list[dict]:
    fk_columns = {relationship["column"] for relationship in relationships if relationship["source"] == sql_file.primary_object}
    relationship_columns = {
        relationship["column"]
        for relationship in relationships
        if relationship["source"] == sql_file.primary_object or relationship["target"] == sql_file.primary_object
    }
    priority = [
        column
        for column in sql_file.columns
        if column.get("is_primary_key")
        or column["name"] in relationship_columns
        or column["name"] in fk_columns
        or column["name"].lower().startswith("fk_")
    ]
    priority_names = {column["name"] for column in priority}
    return [*priority, *[column for column in sql_file.columns if column["name"] not in priority_names]][:limit]


def mermaid_column_line(column: dict, fk_columns: set[str]) -> str:
    name = mermaid_token(column["name"], "column")
    column_type = mermaid_type(column["type"])
    if column.get("is_primary_key"):
        key_text = " PK"
    elif column["name"] in fk_columns or column["name"].lower().startswith("fk_"):
        key_text = " FK"
    else:
        key_text = ""
    return f"    {column_type} {name}{key_text}"


def er_entities_for_spec(spec: dict, tables: dict[str, SqlFile]) -> list[str]:
    names = [name for name in spec["tables"] if name in tables]
    external_targets = sorted(
        {
            relationship["target"]
            for relationship in spec["relationships"]
            if relationship["source"] in names and relationship["target"] not in tables
        }
    )
    return [*names, *external_targets]


def mermaid_er_source(spec: dict, tables: dict[str, SqlFile]) -> tuple[str, list[str], list[dict]]:
    names = er_entities_for_spec(spec, tables)
    used: set[str] = set()
    entity_ids = {name: mermaid_identifier(name, used) for name in names}
    relationships = [
        relationship
        for relationship in spec["relationships"]
        if relationship["source"] in entity_ids and relationship["target"] in entity_ids
    ]
    lines = ["erDiagram"]
    lines.append("  %% Entity names use schema_table identifiers; see the evidence table for original SQL names.")
    for name in names:
        entity_id = entity_ids[name]
        lines.append(f"  %% {entity_id} = {name}")
        lines.append(f"  {entity_id} {{")
        if name in tables:
            sql_file = tables[name]
            fk_columns = {
                relationship["column"]
                for relationship in relationships
                if relationship["source"] == sql_file.primary_object
            }
            visible_columns = er_visible_columns(sql_file, relationships)
            for column in visible_columns:
                lines.append(mermaid_column_line(column, fk_columns))
            omitted = len(sql_file.columns) - len(visible_columns)
            if omitted > 0:
                lines.append(f"    STRING omitted_columns_{omitted}")
        else:
            lines.append("    STRING external_reference")
        lines.append("  }")
    if relationships:
        lines.append("  %% Declared FK relationships are solid; inferred name-based relationships are dotted.")
    for relationship in relationships:
        parent = entity_ids[relationship["target"]]
        child = entity_ids[relationship["source"]]
        connector = "||--o{" if relationship["kind"] == "declared" else "||..o{"
        label = mermaid_token(f'{relationship["column"]}_{relationship["kind"]}', "relates")
        lines.append(f"  {parent} {connector} {child} : {label}")
    return "\n".join(lines), names, relationships


def relationship_evidence_table(relationships: list[dict]) -> str:
    if not relationships:
        return '<p class="muted">No relationships found inside this diagram scope.</p>'
    rows = []
    for relationship in relationships:
        evidence_class = "declared" if relationship["kind"] == "declared" else "inferred"
        rows.append(
            [
                f'<span class="code-ref">{html_escape(relationship["source"])}</span>',
                html_escape(relationship["column"]),
                f'<span class="code-ref">{html_escape(relationship["target"])}</span>',
                f'<span class="er-rel-kind {evidence_class}">{html_escape(relationship["kind"])}</span>',
                html_escape(relationship["note"]),
            ]
        )
    return table(["Child / FK table", "Column", "Parent / referenced table", "Evidence", "Note"], rows)


def er_table_inventory(spec: dict, tables: dict[str, SqlFile], relationships: list[dict]) -> str:
    rows = []
    for name in spec["tables"]:
        if name not in tables:
            continue
        sql_file = tables[name]
        visible = er_visible_columns(sql_file, relationships, limit=18)
        search = " ".join([sql_file.primary_object, sql_file.rel, *[column["name"] for column in sql_file.columns]])
        pk_columns = [column["name"] for column in sql_file.columns if column.get("is_primary_key")]
        fk_columns = sorted(
            {
                relationship["column"]
                for relationship in relationships
                if relationship["source"] == sql_file.primary_object
            }
        )
        rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(sql_file.primary_object)}</strong><br><span class="muted">{html_escape(sql_file.rel)}</span></div>',
                chip_list(pk_columns, limit=6, empty="No PK extracted"),
                chip_list(fk_columns, limit=8, empty="No FK relationship in this scope"),
                chip_list([column["name"] for column in visible], limit=18, empty="No columns extracted"),
                str(len(sql_file.columns)),
            ]
        )
    return table(["Table", "PK columns", "FK columns", "Columns shown in Mermaid", "Total columns"], rows)


def render_er_diagrams(table_files: list[SqlFile]) -> str:
    tables = table_lookup(table_files)
    blocks = []
    for index, spec in enumerate(er_diagram_specs(table_files), start=1):
        source, names, relationships = mermaid_er_source(spec, tables)
        if not names:
            continue
        declared_count = sum(1 for relationship in relationships if relationship["kind"] == "declared")
        inferred_count = sum(1 for relationship in relationships if relationship["kind"] == "inferred")
        relationship_table = relationship_evidence_table(relationships)
        inventory_table = er_table_inventory(spec, tables, relationships)
        search = " ".join(
            [
                spec["title"],
                spec["description"],
                *names,
                *[
                    f'{relationship["source"]} {relationship["column"]} {relationship["target"]} {relationship["kind"]}'
                    for relationship in relationships
                ],
            ]
        )
        blocks.append(
            f'<div class="card mermaid-er-card search-item" data-search="{html_escape(search)}">'
            f'<h3>{html_escape(spec["title"])}</h3>'
            f'<p class="muted">{html_escape(spec["description"])}</p>'
            f'<div class="er-mermaid-summary">'
            f'<span><strong>{len([name for name in names if name in tables])}</strong> SQL tables</span>'
            f'<span><strong>{declared_count}</strong> declared FK relationships</span>'
            f'<span><strong>{inferred_count}</strong> inferred relationships</span>'
            f'</div>'
            f'<div class="mermaid-diagram-wrap" role="img" aria-label="{html_escape(spec["title"])} Mermaid ER diagram">'
            f'<pre class="mermaid">{html_escape(source)}</pre>'
            f'</div>'
            f'<details class="mermaid-source-details"><summary>Mermaid ER source</summary><pre class="mermaid-source"><code>{html_escape(source)}</code></pre></details>'
            f'<details class="er-relationship-details"><summary>Relationship evidence table</summary>{relationship_table}</details>'
            f'<details class="er-relationship-details"><summary>Table inventory used by this diagram</summary>{inventory_table}</details>'
            f'</div>'
        )
    return "\n".join(blocks)


def chip_list(values: Iterable[str], limit: int = 8, empty: str = "None found") -> str:
    unique = list(dict.fromkeys(str(value) for value in values if value))
    if not unique:
        return f'<span class="muted">{html_escape(empty)}</span>'
    chips = "".join(f'<span class="flow-chip">{html_escape(value)}</span>' for value in unique[:limit])
    if len(unique) > limit:
        chips += f'<span class="muted">+{len(unique) - limit} more</span>'
    return chips


def mermaid_text(value: object, limit: int = 120) -> str:
    text = compact(value, limit)
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("\\", "/")
    return text.replace('"', "'").replace(":", " -")


def mermaid_node_label(value: object, limit: int = 110) -> str:
    text = mermaid_text(value, limit)
    return text.replace("|", "/").replace("[", "(").replace("]", ")")


def render_mermaid_block(source: str, label: str, source_label: str = "Mermaid source") -> str:
    stripped = source.lstrip()
    diagram_body = re.sub(r"^%%\{.*?\}%%\s*", "", stripped, flags=re.S)
    diagram_class = "mermaid-sequence-wrap" if diagram_body.startswith("sequenceDiagram") else "mermaid-flowchart-wrap" if diagram_body.startswith("flowchart") else "mermaid-er-wrap" if diagram_body.startswith("erDiagram") else ""
    return (
        f'<div class="mermaid-diagram-wrap {diagram_class}" role="img" aria-label="{html_escape(label)}">'
        f'<pre class="mermaid">{html_escape(source)}</pre>'
        f'</div>'
        f'<details class="mermaid-source-details"><summary>{html_escape(source_label)}</summary>'
        f'<pre class="mermaid-source"><code>{html_escape(source)}</code></pre></details>'
    )


def render_legacy_code_overview_diagram(legacy_code: dict) -> str:
    source = "\n".join(
        [
            "sequenceDiagram",
            "  autonumber",
            "  participant CF as Legacy code app",
            "  participant Scan as Static source scan",
            "  participant SQL as Imported SQL project",
            "  participant Report as Analysis report",
            "  participant CSharp as CSharp extension",
            f"  CF->>Scan: scan {legacy_code.get('files_scanned', 0)} source files",
            f"  Scan->>Scan: extract datasource {mermaid_text(legacy_code.get('datasource') or 'unknown', 60)} and SQL identifiers",
            "  Scan->>SQL: match references against table/procedure/function/view definitions",
            f"  SQL-->>Scan: {legacy_code.get('distinct_sql_objects_hit', 0)} imported objects referenced from {legacy_code.get('files_with_sql_hits', 0)} files",
            f"  Scan-->>Report: {legacy_code.get('matched_stored_proc_calls', 0)} matched stored-procedure calls, {legacy_code.get('unmatched_stored_proc_calls', 0)} unmatched external calls",
            "  Report-->>CSharp: supporting evidence for migration and parity questions",
            "  Note over CF,CSharp: Static source evidence only; PDFs and approved requirements remain authoritative.",
        ]
    )
    return (
        '<div class="card mermaid-card search-item" data-search="legacy code overview static sql call-site evidence datasource imported sql csharp">'
        '<p class="muted">This sequence shows the evidence chain created by the static scan. It is not a production runtime trace.</p>'
        f'{render_mermaid_block(source, "Legacy code to SQL static evidence sequence")}'
        '</div>'
    )


def render_legacy_code_procedure_diagram(legacy_code: dict) -> str:
    cards = []
    for row in legacy_code.get("procedure_flows", [])[:10]:
        status = "matched" if row.get("matched") else "unmatched"
        sql_target = row.get("matched_object") or "External / not imported"
        deps = row.get("sql_dependencies", [])
        external = row.get("external_refs", [])
        cf_refs = row.get("cf_refs", [])
        cf_ref_text = ", ".join(f'{Path(ref["file"]).name}:{ref["line"]}' for ref in cf_refs[:3]) or "No CF source line captured"
        sql_file_name = Path(row.get("sql_file") or "not-imported").name
        source_lines = [
            "sequenceDiagram",
            "  autonumber",
            "  participant CF as Legacy code source",
            "  participant SQL as Imported SQL object",
            "  participant Surface as SQL surface",
            "  participant Ext as External dependency",
            "  participant Result as Result side effect",
            f"  CF->>SQL: calls {mermaid_text(row.get('procedure', sql_target), 90)}",
            f"  Note right of CF: {mermaid_text(cf_ref_text, 80)}",
        ]
        if row.get("matched"):
            source_lines.append(f"  Note right of SQL: {mermaid_text(sql_file_name, 80)}")
            if deps:
                source_lines.append(f"  SQL->>Surface: touches {mermaid_text(', '.join(deps[:4]), 72)}")
            else:
                source_lines.append("  SQL->>Surface: no table/function dependency extracted")
            if external:
                source_lines.append(f"  SQL->>Ext: references {mermaid_text(', '.join(external[:3]), 72)}")
            source_lines.append("  SQL-->>Result: behavior inferred from imported SQL definition")
        else:
            source_lines.append("  SQL-->>Result: not found in imported SQL snapshot")
            source_lines.append("  Note over SQL,Ext: Treat as external or missing legacy dependency until reviewed.")
        source_lines.append("  Note over CF,Result: Static call-site map only; not runtime frequency or reachability proof.")
        source = "\n".join(source_lines)
        cards.append(
            '<details class="card mermaid-card search-item" data-search="{}" open>'
            '<summary>{} - {}</summary>'
            '<p class="muted">Legacy code evidence: {}. Imported SQL file: <code>{}</code>.</p>'
            '{}'
            '<div class="function-flow-chips"><strong>SQL surface</strong>{}<strong>External</strong>{}</div>'
            '</details>'.format(
                html_escape(" ".join([row.get("procedure", ""), sql_target, status, " ".join(deps), " ".join(external), cf_ref_text])),
                html_escape(row.get("procedure", sql_target)),
                html_escape(status),
                file_ref_links(cf_refs, limit=4, empty="No CF call refs"),
                html_escape(row.get("sql_file") or "Not present in imported SQL snapshot"),
                render_mermaid_block(source, f'Legacy code procedure call sequence for {sql_target}'),
                chip_list(deps, limit=8, empty="No imported SQL dependency listed"),
                chip_list(external, limit=6, empty="No external dependency extracted"),
            )
        )
    return '<div class="mermaid-card-grid">' + "".join(cards) + "</div>"


def render_legacy_code_domain_diagram(legacy_code: dict) -> str:
    domain_flows = legacy_code.get("domain_flows", [])
    if not domain_flows:
        return '<p class="muted">No Legacy code domain flow evidence found.</p>'
    lines = [
        "flowchart LR",
        "  subgraph CF[Legacy code functional areas]",
    ]
    for index, row in enumerate(domain_flows, start=1):
        lines.append(
            f'    D{index}["{mermaid_node_label(row["name"], 80)}<br/>{len(row.get("cf_refs", []))} source refs"]'
        )
    lines.append("  end")
    lines.append("  subgraph SQL[Imported SQL evidence]")
    for index, row in enumerate(domain_flows, start=1):
        objects = [item["object"] for item in row.get("sql_objects", [])[:4]]
        label = "<br/>".join(mermaid_node_label(obj, 50) for obj in objects) or "No SQL object match"
        if len(row.get("sql_objects", [])) > 4:
            label += f"<br/>+{len(row.get('sql_objects', [])) - 4} more"
        lines.append(f'    S{index}["{label}"]')
    lines.append("  end")
    for index, _ in enumerate(domain_flows, start=1):
        lines.append(f"  D{index} -->|static references| S{index}")
    source = "\n".join(lines)
    rows = []
    for row in domain_flows:
        rows.append(
            [
                f'<strong>{html_escape(row["name"])}</strong><br><span class="muted">{html_escape(row["note"])}</span>',
                file_ref_links(row.get("cf_refs", []), limit=6, empty="No direct CF file match"),
                chip_list([item["object"] for item in row.get("sql_objects", [])], limit=10, empty="No imported SQL object match"),
            ]
        )
    return (
        '<div class="card mermaid-card search-item" data-search="legacy code functional area map imported sql evidence">'
        f'{render_mermaid_block(source, "Legacy code functional area to SQL evidence map")}'
        '<details class="er-relationship-details"><summary>Functional area evidence table</summary>'
        f'{table(["Functional area", "Legacy code files", "Imported SQL objects"], rows)}'
        '</details>'
        '</div>'
    )


def render_function_group_flow(function_logic: dict) -> str:
    groups = function_logic.get("groups", [])
    lines = [
        "flowchart LR",
        '  Caller["Caller evidence<br/>Legacy code mapped separately"]',
        '  Functions["SQL function groups"]',
        '  Outputs["Observed outputs<br/>rowsets / scalar values / XML"]',
        "  Caller -->|static invocation evidence, when available| Functions",
        "  Functions -->|read / lookup / format / report| Outputs",
        "  subgraph Groups[Business role groups]",
    ]
    for index, group in enumerate(groups, start=1):
        label = f'{group["name"]}<br/>{group["count"]} functions<br/>{mermaid_node_label(compact(group["logic"], 72), 88)}'
        lines.append(f'    G{index}["{label}"]')
    lines.append("  end")
    for index, _ in enumerate(groups, start=1):
        lines.append(f"  Functions --> G{index}")
        lines.append(f"  G{index} --> Outputs")
    lines.append('  Note["Static SQL analysis<br/>not runtime telemetry"]')
    lines.append("  Outputs -.-> Note")
    source = "\n".join(lines)
    rows = []
    for group in groups:
        rows.append(
            [
                f'<strong>{html_escape(group["name"])}</strong><br><span class="muted">{group["count"]} function files</span>',
                html_escape(group["logic"]),
                chip_list(group.get("functions", [])[:4], limit=4, empty="No function examples"),
            ]
        )
    return (
        '<div class="card mermaid-card search-item" data-search="sql function group flow mermaid business logic">'
        f'{render_mermaid_block(source, "High-level SQL function group flow")}'
        '<details class="er-relationship-details"><summary>Function-group summary</summary>'
        f'{table(["Group", "Business logic", "Examples"], rows)}'
        '</details>'
        '</div>'
    )


def function_dependency_lists(row: dict) -> tuple[list[str], list[str], list[str]]:
    dependencies = [dep for dep in row.get("dependencies", []) if dep != row.get("object")]
    table_refs = [dep for dep in dependencies if dep.startswith(("app.T", "dbo.T", "ref."))]
    function_refs = [dep for dep in dependencies if dep not in table_refs]
    external_refs = list(row.get("external_refs", []))
    return table_refs, function_refs, external_refs


def function_sequence_steps(row: dict) -> list[tuple[str, str]]:
    table_refs, function_refs, external_refs = function_dependency_lists(row)
    group = row["group"]
    object_name = row["object"]
    result = row["return_shape"]
    source = row.get("source_refs", [{}])[0]
    source_text = f'{source.get("file", row.get("file"))}:{source.get("line", row.get("line", 1))}'
    steps = [
        ("Caller evidence", "See the Legacy code call-site section for direct source references; this per-function flow remains SQL-static."),
        ("Function entry", f"{object_name} ({result}) in {source_text}."),
    ]

    if group == "Print and datafile helpers":
        steps.extend(
            [
                ("Select print candidates", "Uses validity, print-date, batching, or label-count inputs visible in SQL."),
                ("Build print values", "Formats envelope/order/person values used by K/N/D/E records or related print settings."),
            ]
        )
    elif group == "Address, PAC, routing, and branch resolution":
        steps.extend(
            [
                ("Resolve address/routing input", "Starts from PAC, PLZ, Standort, destination rows, or order ids."),
                ("Format operational output", "Returns address strings, branch data, delivery district/group-order, or location rows."),
            ]
        )
    elif group == "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup":
        steps.extend(
            [
                ("Apply search/person criteria", "Uses person/order/address parameters or XML to locate matching order/person records."),
                ("Join person and order context", "Combines legacy head/detail rows with external search API/CLR person data or fuzzy-search scoring."),
            ]
        )
    elif group == "Validity, current-order filters, and eligibility":
        steps.extend(
            [
                ("Load order state", "Reads validity dates, cancellation/revocation state, order type, destination, or print eligibility."),
                ("Derive status/filter result", "Returns current/future/expired/cancelled status or a filtered current-order rowset."),
            ]
        )
    elif group == "Reports and exports":
        steps.extend(
            [
                ("Assemble reporting rowset", "Projects order, destination, person, validity, or log data into a report/export shape."),
                ("Apply report-specific filtering", "Filters by person, validity, history chain, product type, or legacy report purpose."),
            ]
        )
    elif group == "Import and transformation":
        steps.extend(
            [
                ("Parse imported detail data", "Splits legacy/imported fields into a structured in-memory result."),
                ("Return XML payload", "Builds XML detail nodes consumed by the legacy save/import path."),
            ]
        )
    else:
        steps.extend(
            [
                ("Call provider/config boundary", "Delegates to SQL CLR or provider-service wrapper visible in the function DDL."),
                ("Return master/config data", "Returns application parameters, branch/location data, country codes, or person-provider rows."),
            ]
        )

    if table_refs:
        steps.append(("SQL table reads", ", ".join(table_refs[:6]) + (" ..." if len(table_refs) > 6 else "")))
    if function_refs:
        steps.append(("SQL function dependencies", ", ".join(function_refs[:6]) + (" ..." if len(function_refs) > 6 else "")))
    if external_refs:
        steps.append(("External boundary", ", ".join(external_refs[:5]) + (" ..." if len(external_refs) > 5 else "")))
    elif "CLR dependency" in row.get("risk_flags", []):
        steps.append(("External boundary", "CLR dependency detected, but no external reference was extracted by name."))
    steps.append(("Return", row["business_logic"]))
    return steps


def function_group_sequence_actions(group: str) -> tuple[str, str]:
    if group == "Print and datafile helpers":
        return (
            "select print candidates, dates, batches, or label counts",
            "format K/N/D/E print or envelope values",
        )
    if group == "Address, PAC, routing, and branch resolution":
        return (
            "resolve PAC, PLZ, Standort, destination, or order input",
            "format address, branch, delivery district, or location output",
        )
    if group == "Search, fuzzy matching, and {EXTERNAL-SEARCH-API} person lookup":
        return (
            "apply person, order, address, fuzzy, or XML criteria",
            "combine legacy rows with external search API/CLR person/search data",
        )
    if group == "Validity, current-order filters, and eligibility":
        return (
            "load validity, cancellation, type, destination, or print state",
            "derive current/future/expired/cancelled or eligible result",
        )
    if group == "Reports and exports":
        return (
            "assemble report/export rowset from order, person, address, or log data",
            "apply report-specific product, history, or validity filtering",
        )
    if group == "Import and transformation":
        return (
            "parse imported or legacy detail fields",
            "build XML detail payload for legacy save/import path",
        )
    return (
        "call configuration, CLR, or provider wrapper boundary",
        "return master data, parameters, or provider rows",
    )


def render_function_sequence_panel(row: dict) -> str:
    table_refs, function_refs, external_refs = function_dependency_lists(row)
    source_ref = row.get("source_refs", [{}])[0]
    source_text = f'{Path(source_ref.get("file", row.get("file"))).name}:{source_ref.get("line", row.get("line", 1))}'
    first_action, second_action = function_group_sequence_actions(row["group"])
    table_label = ", ".join(table_refs[:4]) if table_refs else "No table read extracted by static scan"
    helper_label = ", ".join(function_refs[:4]) if function_refs else "No SQL helper call extracted"
    if external_refs:
        external_label = ", ".join(external_refs[:3])
    elif "CLR dependency" in row.get("risk_flags", []):
        external_label = "CLR dependency detected"
    else:
        external_label = "No external boundary extracted"
    lines = [
        "flowchart LR",
        '  Caller["Caller evidence"]',
        f'  Func["{mermaid_node_label(row["object"], 56)}<br/>{mermaid_node_label(row["return_shape"], 48)}"]',
        f'  Source["Source line<br/>{mermaid_node_label(source_text, 70)}"]',
        f'  Input["Input/action<br/>{mermaid_node_label(first_action, 82)}"]',
        f'  Tables["Tables<br/>{mermaid_node_label(table_label, 82)}"]',
        f'  Helpers["SQL helpers<br/>{mermaid_node_label(helper_label, 82)}"]',
        f'  External["External boundary<br/>{mermaid_node_label(external_label, 82)}"]',
        f'  Output["Output shaping<br/>{mermaid_node_label(second_action, 82)}"]',
        f'  Result["Result<br/>{mermaid_node_label(row["return_shape"], 64)}"]',
        '  Note["Static SQL dependency map<br/>not a proven runtime trace"]',
        '  Caller -->|"invoke"| Func',
        "  Func -.-> Source",
        "  Func --> Input",
        "  Input --> Tables",
        "  Input --> Helpers",
        "  Input --> External",
        "  Tables --> Output",
        "  Helpers --> Output",
        "  External --> Output",
        "  Output --> Result",
        "  Result -.-> Note",
    ]
    source = "\n".join(lines)
    chips = []
    for label, values in (("Tables", table_refs), ("SQL helpers", function_refs), ("External", external_refs)):
        if values:
            chips.append(f'<span class="flow-chip">{html_escape(label)}: {html_escape(", ".join(values[:4]))}</span>')
    if not chips:
        chips.append('<span class="flow-chip">No dependency detected by static scan</span>')
    diagram_label = f'Function flow for {row["object"]}'
    return (
        '<div class="function-flow-panel">'
        f'{render_mermaid_block(source, diagram_label)}'
        f'<div class="function-flow-chips">{"".join(chips)}</div>'
        '</div>'
    )


def render_function_sequence_diagrams(function_logic: dict) -> str:
    blocks = []
    for index, row in enumerate(function_logic.get("details", []), start=1):
        deps = ", ".join([*row.get("dependencies", [])[:5], *row.get("external_refs", [])[:5]]) or "No dependency detected by static scan"
        search = " ".join([row["object"], row["group"], row["business_logic"], deps])
        blocks.append(
            f'<details class="card search-item" data-search="{html_escape(search)}">'
            f'<summary>{html_escape(row["object"])} - {html_escape(row["group"])}</summary>'
            f'<p>{html_escape(row["business_logic"])}</p>'
            f'<p class="muted">Dependencies: {html_escape(deps)}. Flow is inferred from static SQL dependencies and source references. Legacy code source references are summarized separately and still do not prove production runtime frequency.</p>'
            f'{render_function_sequence_panel(row)}'
            f'</details>'
        )
    return "\n".join(blocks)


def evidence_links(evidence: list[dict], limit: int = 5) -> str:
    if not evidence:
        return '<span class="muted">No SQL evidence found by automated scan</span>'
    links = []
    for item in evidence[:limit]:
        links.append(
            f'<span class="code-ref">{html_escape(item["file"])}:{html_escape(item.get("line", 1))}</span>'
        )
    if len(evidence) > limit:
        links.append(f'<span class="muted">+{len(evidence) - limit} more</span>')
    return " ".join(links)


def pdf_ref_links(refs: list[dict], limit: int = 4) -> str:
    if not refs:
        return '<span class="muted">No PDF page match found by automated scan</span>'
    parts = []
    for ref in refs[:limit]:
        title = f'{ref["pdf"]}, page {ref["page"]}'
        snippet = compact(ref.get("snippet", ""), 150)
        parts.append(
            f'<div class="pdf-ref"><span class="code-ref">{html_escape(title)}</span>'
            f'<br><span class="muted">{html_escape(snippet)}</span></div>'
        )
    if len(refs) > limit:
        parts.append(f'<span class="muted">+{len(refs) - limit} more PDF pages</span>')
    return "".join(parts)


def csharp_links(evidence: list[dict], limit: int = 6) -> str:
    if not evidence:
        return '<span class="muted">No C# backend file found by automated scan</span>'
    parts = []
    for item in evidence[:limit]:
        parts.append(f'<span class="code-ref">{html_escape(item["file"])}:{html_escape(item["line"])}</span>')
    if len(evidence) > limit:
        parts.append(f'<span class="muted">+{len(evidence) - limit} more</span>')
    return " ".join(parts)


def table(headers: list[str], rows: list[list[str]], classes: str = "") -> str:
    head = "".join(f"<th>{html_escape(header)}</th>" for header in headers)
    body = "\n".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table class="{classes}"><thead><tr>{head}</tr></thead><tbody class="searchable-rows">{body}</tbody></table></div>'


def csharp_er_table_inventory(diagram: dict) -> str:
    rows = []
    relationships = diagram.get("relationships", [])
    for table_row in diagram.get("table_inventory", []):
        visible = csharp_er_visible_columns(table_row, relationships, limit=18)
        pk_columns = [column["name"] for column in table_row.get("columns", []) if column.get("is_primary_key")]
        fk_columns = sorted(
            {
                column
                for relationship in relationships
                if relationship["source"] == table_row["name"]
                for column in relationship["column"].split("_")
            }
        )
        search = " ".join([table_row["name"], *[column["name"] for column in table_row.get("columns", [])]])
        rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(table_row["name"])}</strong><br><span class="muted">{html_escape(table_row["schema"])}</span></div>',
                chip_list(pk_columns, limit=6, empty="No PK extracted"),
                chip_list(fk_columns, limit=8, empty="No FK relationship in this scope"),
                chip_list([column["name"] for column in visible], limit=18, empty="No columns extracted"),
                str(len(table_row.get("columns", []))),
                file_ref_links(table_row.get("evidence", []), limit=2),
            ]
        )
    return table(["Table", "PK columns", "FK/link columns", "Columns shown in Mermaid", "Total columns", "Evidence"], rows)


def csharp_er_relationship_table(diagram: dict) -> str:
    relationships = diagram.get("relationships", [])
    if not relationships:
        return '<p class="muted">No relationships found inside this diagram scope.</p>'
    rows = []
    for relationship in relationships:
        evidence_class = "declared" if relationship["kind"] == "declared" else "inferred"
        rows.append(
            [
                f'<span class="code-ref">{html_escape(relationship["source"])}</span>',
                html_escape(relationship["column"]),
                f'<span class="code-ref">{html_escape(relationship["target"])}</span>',
                f'<span class="er-rel-kind {evidence_class}">{html_escape(relationship["kind"])}</span>',
                html_escape(relationship["note"]),
                file_ref_links(relationship.get("evidence", []), limit=3),
            ]
        )
    return table(["Child / link table", "Column", "Parent / referenced table", "Evidence kind", "Note", "Source"], rows)


def render_csharp_domain_er_diagrams(csharp_sql_model: dict) -> str:
    blocks = []
    for diagram in csharp_sql_model.get("er_diagrams", []):
        search = " ".join(
            [
                diagram["title"],
                diagram["description"],
                *diagram.get("tables", []),
                *[
                    f'{relationship["source"]} {relationship["column"]} {relationship["target"]} {relationship["kind"]}'
                    for relationship in diagram.get("relationships", [])
                ],
            ]
        )
        blocks.append(
            f'<div class="card mermaid-er-card search-item" data-search="{html_escape(search)}">'
            f'<h4>{html_escape(diagram["title"])}</h4>'
            f'<p class="muted">{html_escape(diagram["description"])}</p>'
            f'<div class="er-mermaid-summary">'
            f'<span><strong>{diagram.get("table_count", 0)}</strong> C# EF tables</span>'
            f'<span><strong>{diagram.get("declared_relationship_count", 0)}</strong> declared migration FK relationships</span>'
            f'<span><strong>{diagram.get("inferred_relationship_count", 0)}</strong> inferred domain/configuration links</span>'
            f'</div>'
            f'{render_mermaid_block(diagram["mermaid"], diagram["title"], source_label="Mermaid ER source")}'
            f'<details class="er-relationship-details"><summary>Relationship evidence table</summary>{csharp_er_relationship_table(diagram)}</details>'
            f'<details class="er-relationship-details"><summary>Table inventory used by this diagram</summary>{csharp_er_table_inventory(diagram)}</details>'
            f'</div>'
        )
    return "\n".join(blocks)


def coverage_status_badge(status: str, confidence: str) -> str:
    css = "other"
    status_norm = normalize(status)
    if status_norm.startswith("yes") or status_norm.startswith("exact") or status_norm.startswith("full") or status_norm.startswith("vollstandig"):
        css = "yes"
    elif status_norm.startswith("partial") or status_norm.startswith("teilweise"):
        css = "partial"
    elif status_norm.startswith("no") or status_norm.startswith("none") or status_norm.startswith("nicht"):
        css = "no"
    confidence_display = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "hoch": "high",
        "mittel": "medium",
        "niedrig": "low",
    }.get(str(confidence), str(confidence))
    return (
        f'<span class="coverage-status {css}">{html_escape(status)}</span>'
        f'<br><span class="muted">Confidence: {html_escape(confidence_display)}</span>'
    )


def render_spec_coverage_overview(overview: dict) -> str:
    counts = overview.get("counts", {})
    definitions = overview.get("coverage_definitions", {})
    summary_cards = [
        ("Complete", counts.get("Complete", 0), definitions.get("Complete", "")),
        ("Partial", counts.get("Partial", 0), definitions.get("Partial", "")),
        ("Not found", counts.get("Not found", 0), definitions.get("Not found", "")),
    ]
    cards_html = "\n".join(
        f'<div class="metric search-item" data-search="{html_escape(label)} {html_escape(note)} Coverage">'
        f'<div class="metric-value">{html_escape(value)}</div><div class="metric-label">Coverage: {html_escape(label)}</div>'
        f'<p>{html_escape(note)}</p></div>'
        for label, value, note in summary_cards
    )

    rows = []
    for row in overview.get("rows", []):
        search = " ".join(
            [
                row.get("area", ""),
                row.get("product", ""),
                row.get("coverage", ""),
                row.get("legacy_meaning", ""),
                row.get("coverage_reason", ""),
                row.get("gap", ""),
                *row.get("spec_terms", []),
                *row.get("legacy_terms", []),
                *row.get("csharp_terms", []),
            ]
        )
        rows.append(
            [
                (
                    f'<div class="search-item" data-search="{html_escape(search)}">'
                    f'<strong>{html_escape(row.get("area", ""))}</strong><br>'
                    f'<span class="muted">{html_escape(row.get("product", ""))}</span>'
                    f'</div>'
                ),
                pdf_ref_links(row.get("pdf_refs", []), limit=2),
                evidence_links(row.get("legacy_sql_evidence", []), limit=5),
                html_escape(row.get("legacy_meaning", "")),
                csharp_links(row.get("csharp_evidence", []), limit=5),
                coverage_status_badge(row.get("coverage", "Unknown"), row.get("confidence", "unknown")),
                html_escape(row.get("coverage_reason", "")),
                html_escape(row.get("gap", "")),
            ]
        )

    gap_rows = []
    for row in overview.get("rows", []):
        if row.get("coverage") == "Complete":
            continue
        gap_rows.append(
            [
                f'<strong>{html_escape(row.get("area", ""))}</strong><br><span class="muted">{html_escape(row.get("product", ""))}</span>',
                coverage_status_badge(row.get("coverage", "Unknown"), row.get("confidence", "unknown")),
                html_escape(row.get("gap", "")),
                csharp_links(row.get("csharp_evidence", []), limit=4),
            ]
        )

    section = f"""
    <section id="spec-coverage-overview">
      <h2>Spec to Legacy SQL to C# - Coverage Overview</h2>
      <div class="explain search-item" data-search="spec overview coverage complete partial not found legacy sql csharp">
        <strong>How to read this overview:</strong> Each row starts with the specification document <code>{html_escape(overview.get("source_pdf", rel(PDF_SOURCES[0])))}</code>, then shows legacy SQL evidence and current implementation coverage. <strong>Complete</strong> means a clear implementation exists; <strong>Partial</strong> means the concept exists but is incomplete; <strong>Not found</strong> means no reliable implementation evidence was found.
      </div>
      <div class="grid">{cards_html}</div>
      {table(["Spec Concept", "Spec Source", "Legacy SQL Evidence", "Meaning in Legacy SQL", "C# Evidence", "C# Coverage", "Coverage Rationale", "Gap / Next Question"], rows, classes="overview-coverage-table")}
      <h3>Open Gaps: Partial / Not found</h3>
      {table(["Spec Concept", "Coverage", "Gap / Next Question", "C# Evidence"], gap_rows, classes="overview-gap-table")}
    </section>
    """
    return "\n".join(line.rstrip() for line in section.strip("\n").splitlines())


def requirement_ref_links(refs: list[dict], limit: int = 8, empty: str = "No directly linked requirement found") -> str:
    if not refs:
        return f'<span class="muted">{html_escape(empty)}</span>'
    parts = []
    for ref in refs[:limit]:
        title = f'{ref.get("title", "")}'
        reason = f'{ref.get("reason", "")}'
        parts.append(
            f'<div><span class="code-ref">{html_escape(ref.get("id", ""))}</span> '
            f'<span class="muted">{html_escape(title)}'
            f'{": " + html_escape(reason) if reason else ""}</span></div>'
        )
    if len(refs) > limit:
        parts.append(f'<span class="muted">+{len(refs) - limit} more</span>')
    return "".join(parts)


def render_acid_table_inventory(recommended_acid_er: dict) -> str:
    rows = []
    for table_row in recommended_acid_er.get("tables", []):
        column_text = ", ".join(
            f'{column["name"]} {column["type"]}{(" " + column["key"]) if column.get("key") else ""}'
            for column in table_row.get("columns", [])
        )
        status = table_row.get("implementation_status", "implement")
        rows.append(
            [
                f'<strong>{html_escape(table_row.get("name", ""))}</strong><br><span class="muted">{html_escape(table_row.get("kind", ""))}</span>',
                f'<span class="acid-status acid-status-{html_escape(status)}">{html_escape(table_row.get("implementation_label", ""))}</span>',
                html_escape(", ".join(table_row.get("legacy_tables", [])) or table_row.get("source", "")),
                html_escape(column_text),
                html_escape(table_row.get("note", "")),
            ]
        )
    no_domain_tables = recommended_acid_er.get("no_domain_tables", [])
    no_domain_html = ""
    if no_domain_tables:
        no_domain_html = (
            '<p class="muted"><strong>Do not port as C# domain tables:</strong> '
            f'{html_escape(", ".join(no_domain_tables))}</p>'
        )
    return (
        no_domain_html
        + table(
            ["SQL target table", "Implementation status", "Legacy evidence", "Recommended columns", "ACID rationale"],
            rows,
            classes="acid-table-inventory",
        )
    )


def render_acid_relationship_inventory(recommended_acid_er: dict) -> str:
    rows = []
    for relationship in recommended_acid_er.get("relationships", []):
        rows.append(
            [
                f'<span class="code-ref">{html_escape(relationship.get("source", ""))}</span>',
                html_escape(relationship.get("column", "")),
                f'<span class="code-ref">{html_escape(relationship.get("target", ""))}</span>',
                html_escape(relationship.get("kind", "")),
                html_escape(relationship.get("note", "")),
            ]
        )
    return table(["FK table", "FK column", "Referenced table", "Status", "Why this relationship"], rows)


def render_recommended_acid_er_diagrams(recommended_acid_er: dict) -> str:
    counts = recommended_acid_er.get("counts", {})
    status_counts = recommended_acid_er.get("counts_by_implementation_status", {})
    summary = (
        f'<span><strong>{html_escape(counts.get("diagrams", 0))}</strong> ER views</span>'
        f'<span><strong>{html_escape(counts.get("tables", 0))}</strong> SQL target tables</span>'
        f'<span><strong>{html_escape(counts.get("relationships", 0))}</strong> FK relationships</span>'
        f'<span><strong>{html_escape(counts.get("no_domain_tables", 0))}</strong> intentionally not ported</span>'
    )
    legend = "".join(
        f'<span class="acid-status acid-status-{status}"><strong>{html_escape(status_counts.get(status, 0))}</strong> {html_escape(label)}</span>'
        for status, label in ACID_TABLE_STATUS_LABELS.items()
    )
    diagram_html = []
    for diagram in recommended_acid_er.get("diagrams", []):
        table_names = " ".join(table.get("name", "") for table in diagram.get("tables", []))
        status_map = {}
        for table in diagram.get("tables", []):
            status = table.get("implementation_status", "")
            if not status:
                continue
            status_map[table.get("name", "")] = status
            status_map[table.get("entity_id", "")] = status
        status_json = json.dumps(status_map, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
        status_lines = []
        for status, label in ACID_TABLE_STATUS_LABELS.items():
            names = [
                table.get("name", "")
                for table in diagram.get("tables", [])
                if table.get("implementation_status") == status
            ]
            if names:
                status_lines.append(
                    f'<div><span class="acid-status acid-status-{status}">{html_escape(label)}</span> '
                    f'<span class="muted">{html_escape(", ".join(names))}</span></div>'
                )
        diagram_html.append(
            f"""
            <div class="card acid-er-card search-item" data-search="{html_escape(diagram.get('title', ''))} {html_escape(table_names)}">
              <h4>{html_escape(diagram.get("title", ""))}</h4>
              <p class="muted">{html_escape(diagram.get("description", ""))}</p>
              <div class="acid-er-status-list">{''.join(status_lines)}</div>
              <script type="application/json" class="acid-er-status-data">{status_json}</script>
              {render_mermaid_block(diagram.get("mermaid", "erDiagram"), diagram.get("title", "ACID ER"), source_label="Mermaid source for the ACID ER diagram")}
            </div>
            """
        )
    return f"""
      <h3>Recommended ACID Target Model: Complete And Focused ER Diagrams</h3>
      <div class="explain search-item" data-search="acid er diagramm spalten beziehungen primary key foreign key sql zielmodell">
        <strong>How to read this:</strong> The first diagram is the complete target model and contains each table once. The focused diagrams below intentionally repeat shared anchor tables such as Orders, Lookups, and AuditLog so each business area remains readable. Colors show implementation status: blue already exists in C#, green means extend an existing C# table, and orange means implement a new table.
      </div>
      <div class="er-mermaid-summary">{summary}</div>
      <div class="acid-er-legend">{legend}</div>
      {''.join(diagram_html)}
      <details class="card">
        <summary>Recommended SQL target tables and relationships as tables</summary>
        <h4>SQL Target Tables</h4>
        {render_acid_table_inventory(recommended_acid_er)}
        <h4>FK Relationships</h4>
        {render_acid_relationship_inventory(recommended_acid_er)}
      </details>
    """


def render_db_table_recommendations(db_recommendations: dict, domain_overlay: dict, recommended_acid_er: dict) -> str:
    rows = []
    for row in db_recommendations.get("rows", []):
        search = " ".join(
            [
                row.get("legacy_table", ""),
                row.get("coverage_status", ""),
                row.get("priority", ""),
                row.get("decision", ""),
                row.get("target_model", ""),
                row.get("target_model_label", ""),
                row.get("recommendation", ""),
                row.get("rationale", ""),
                row.get("coverage_rationale", ""),
                *row.get("concepts", []),
                *row.get("legacy_columns", []),
                *[ref.get("id", "") for ref in row.get("requirement_refs", [])],
            ]
        )
        current_surface = chip_list(
            row.get("current_csharp_surface", []),
            limit=8,
            empty="Keine direkte aktive C#-EF-Tabelle gefunden",
        )
        if row.get("concepts"):
            current_surface += f'<div class="muted">{html_escape("; ".join(row.get("concepts", [])[:4]))}</div>'
        evidence = (
            f'<div><strong>Legacy:</strong> {file_ref_links(row.get("legacy_evidence", []), limit=2)}</div>'
            f'<div><strong>C#:</strong> {file_ref_links(row.get("csharp_evidence", []), limit=3, empty="Keine C#-Quelle")}</div>'
        )
        rows.append(
            [
                (
                    f'<div class="search-item" data-search="{html_escape(search)}">'
                    f'<strong>{html_escape(row.get("legacy_table", ""))}</strong><br>'
                    f'<span class="muted">{html_escape(row.get("legacy_path", ""))}</span>'
                    f'</div>'
                ),
                coverage_status_badge(row.get("coverage_status", "Unknown"), row.get("confidence", "unknown")),
                f'<span class="coverage-status partial">{html_escape(row.get("priority", ""))}</span>',
                (
                    f'<strong>{html_escape(row.get("decision", ""))}</strong><br>'
                    f'{html_escape(row.get("recommendation", ""))}'
                ),
                html_escape(row.get("target_model_label") or row.get("target_model", "")),
                (
                    f'{html_escape(row.get("rationale", ""))}'
                    f'<div class="muted">{html_escape(row.get("coverage_rationale", ""))}</div>'
                ),
                requirement_ref_links(row.get("requirement_refs", [])),
                current_surface,
                evidence,
            ]
        )

    counts = db_recommendations.get("counts", {})
    coverage_counts = counts.get("by_coverage", {})
    priority_counts = counts.get("by_priority", {})
    coverage_summary = " ".join(
        f'<span><strong>{html_escape(count)}</strong> {html_escape(status)}</span>'
        for status, count in sorted(coverage_counts.items())
    )
    priority_summary = " ".join(
        f'<span><strong>{html_escape(count)}</strong> Priority {html_escape(priority)}</span>'
        for priority, count in sorted(priority_counts.items())
    )
    overlay_counts = (
        f'<span><strong>{html_escape(domain_overlay.get("current_table_count", 0))}</strong> existing C# tables, blue border</span>'
        f'<span><strong>{html_escape(domain_overlay.get("recommendation_count", 0))}</strong> recommendations, orange/grey</span>'
        f'<span><strong>{html_escape(domain_overlay.get("current_relationship_count", 0))}</strong> C# relationships</span>'
        f'<span><strong>{html_escape(domain_overlay.get("recommendation_edge_count", 0))}</strong> recommendation links</span>'
    )
    section = f"""
    <section id="db-table-recommendations">
      <h2>DB Table Recommendations For Legacy Gaps</h2>
      <div class="explain search-item" data-search="db table recommendations legacy partial no direct table csharp requirements acid target decision">
        <strong>Reading rule:</strong> This matrix covers all legacy tables with C# coverage status <em>Partial</em> or <em>No direct table</em>. Each row contains exactly one ACID target decision and one concrete target model. A recommendation does not automatically mean "copy the legacy table".
      </div>
      <div class="coverage-summary">{coverage_summary} {priority_summary}</div>
      {render_recommended_acid_er_diagrams(recommended_acid_er)}
      <details class="card">
        <summary>Planning overlay: current C# + DB recommendations</summary>
        <p class="muted"><strong>How to read the boxes:</strong> "Recommended" describes the domain decision. "C# target" is the confirmed target model for this recommendation. "Legacy evidence" is the legacy SQL table from which the gap was derived. Blue border means: already exists in C#. Orange border means: ACID extension in the C# data model. Grey dashed means: do not port directly as a C# domain table. This view is a rough navigation map; the ER diagrams above are authoritative.</p>
        <div class="er-mermaid-summary">{overlay_counts}</div>
        <div class="domain-overlay-card search-item" data-search="domain overlay current csharp db recommendations mermaid border color">
          {render_mermaid_block(domain_overlay.get("mermaid", "flowchart LR"), domain_overlay.get("title", "Domain Model Overlay"), source_label="Mermaid source of the domain model overlay")}
        </div>
      </details>
      {table(["Legacy Table", "C# Coverage", "Priority", "Recommendation", "Proposed Target Model", "Rationale", "Relevant Requirements", "Current C# Surface", "Evidence"], rows, classes="db-recommendation-table")}
    </section>
    """
    return "\n".join(line.rstrip() for line in section.strip("\n").splitlines())


def md_cell(value: object) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split())
    return text.replace("|", "\\|")


def md_code(value: object) -> str:
    text = md_cell(value)
    return f"`{text}`" if text else ""


MKDOCS_EN_TEXT = {
    "Vollständig": "Full",
    "Teilweise": "Partial",
    "Nicht vorhanden": "No direct evidence",
    "Nicht als C#-Fachtabelle übernehmen, Nummernvergabe über Datenbank-Sequenzen lösen": "Do not port as a C# domain table; solve number allocation with database sequences",
    "Die Tabelle ist ein Service-Endpunkt-Register (Servicename -> URL), also Laufzeitkonfiguration statt Fachdaten. In der neuen Anwendung gehört das in appsettings/Umgebungskonfiguration; das the specification stellt keine Anforderung an eine fachliche Verwaltung dieser Daten.": (
        "The table is a service-endpoint registry (service name -> URL), i.e. runtime configuration rather than business data. In the new application this belongs in appsettings/environment configuration; the specification places no requirement on managing this data as a business entity."
    ),
    "Die Tabelle ist eine trigger-gepflegte Sicherungskopie gelöschter TBilling-Zeilen, kein eigenständiger Fachbestand. Im Zielmodell ist Löschung ein append-only BillingEvents-Ereignis, wodurch dieselbe Nachvollziehbarkeit ohne doppelte Backup-Tabelle entsteht; technische Sicherung/Retention bleibt Aufgabe der Datenbankplattform.": (
        "The table is a trigger-maintained backup copy of deleted TBilling rows, not an independent business dataset. In the target model a deletion is an append-only BillingEvents event, which provides the same traceability without a duplicate backup table; technical backup/retention remains a database-platform concern."
    ),
    "Die Tabelle protokolliert DDL-/Schemaänderungen der Legacy-Datenbank über Datenbank-Trigger — ein Infrastruktur-Audit, keine {PROJECT-NAME}-Fachentität. In der neuen Anwendung liefern EF-Core-Migrationen plus Versionskontrolle dieselbe Schemahistorie verbindlich; eine Portierung würde Deployment-Belange in das Domänenmodell duplizieren.": (
        "The table logs DDL/schema changes of the legacy database via database triggers — an infrastructure audit, not a {PROJECT-NAME} business entity. In the new application, EF Core migrations plus version control provide the same schema history authoritatively; porting it would duplicate deployment concerns into the domain model."
    ),
    "Keine eigene Nummernkreis-Fachtabelle einführen. Formularnummern werden über native Datenbank-Sequenzen je Produktkennung und Einrichtungsjahr (spec ch. 11.13.11) vergeben — analog zu den bestehenden Legacy-Sequenzen APP_SEQ*; die Eindeutigkeit sichert die Datenbank, nicht eine Domänentabelle.": (
        "Do not introduce a dedicated number-range domain table. Form numbers are allocated through native database sequences per product code and creation year (spec ch. 11.13.11) — analogous to the existing legacy APP_SEQ* sequences; uniqueness is guaranteed by the database, not by a domain table."
    ),
    "C# hat Formularnummernlogik, aber keine legacygleiche Zählertabelle; eine eigenständige Tabelle hätte keine Beziehungen zum übrigen Fachmodell und wurde deshalb bewusst aus dem Zielmodell entfernt.": (
        "C# has form-number logic but no legacy-equivalent counter table; a standalone table would have no relationships to the rest of the domain model and was therefore deliberately removed from the target model."
    ),
    "Titelspalten behalten, Titelkataloge als Lookup-Typen führen": "Keep title columns, manage title catalogs as lookup types",
    "Keine dedizierte Titel-Tabelle einführen. Titel bleiben als längenbegrenzte Spalten auf den bestehenden Personen- und Identitätstabellen erhalten; die Auswahllisten 'Titel vorangestellt' und 'Titel danach' (spec ch. 11.5.3/11.5.4, neu in V1.9) werden als Lookup-Typen in Lookups gepflegt.": (
        "Do not introduce a dedicated title table. Titles remain length-constrained columns on the existing person and identity tables; the selection lists 'Titel vorangestellt' and 'Titel danach' (spec ch. 11.5.3/11.5.4, new in V1.9) are maintained as lookup types in Lookups."
    ),
    "C# speichert Titel bereits auf Personen-/Identifikationsdaten (TitlePrefix/TitleSuffix); the specification verlangt zusätzlich gepflegte Drop-down-Kataloge für vorangestellte und nachgestellte Titel.": (
        "C# already stores titles on person/identification data (TitlePrefix/TitleSuffix); the specification additionally demands maintained drop-down catalogs for preceding and post-nominal titles."
    ),
    "Post.Partner-Ausnahmen relational mit Produkt-/Auftragstypbezug (Ausnahmetypen PFU, WUN, PFP) und PLZ-Bezug speichern. Eindeutige Constraints verhindern doppelte Ausnahmezeilen; die Synchronisierung zum Online-Service (wirksam erst am Folgetag) bleibt eine Schnittstellenfrage.": (
        "Store Post.Partner exceptions relationally with product/order-type references (exception types PFU, WUN, PFP) and postal-code references. Unique constraints prevent duplicate exception rows; synchronization to the online service (effective only the next day) remains an interface question."
    ),
    "spec ch. 2 verlangt ausdrücklich die Integration der Post.Partner-Ausnahmetabelle in die example-order-DB; die Legacy-Pflege lief bisher als eigene Legacy-Code-Maske.": (
        "the specification ch. 2 explicitly demands integrating the Post.Partner exception table into the example-order-DB; legacy maintenance previously ran as a separate Legacy code screen."
    ),
    "Die Legacy-Tabelle wirkt wie Integrationsfeedback; im aktuellen C#-Persistenzmodell ist keine entsprechende fachliche Oberfläche sichtbar. the specification enthält keinen Feedback-/Registrierungs-Fachbedarf; die Tabelle bleibt reiner Legacy-Integrationsnachweis.": (
        "The legacy table looks like integration feedback; no corresponding business persistence surface is visible in the current C# model. the specification contains no feedback/registration business demand; the table remains pure legacy integration evidence."
    ),
    "Druck- und Etikettenläufe als PrintJobs plus PrintJobOrders speichern; die eine Legacy-Importtabelle wird normalisiert aufgeteilt, weil ein Drucklauf viele Aufträge bündelt (m:n). PrintJobs trägt den Lauf mit Status, Erstellzeit, Übergabezeit, Etikettenblattanzahl und ZUBA-PLZ (spec ch. 16.3.5); PrintJobOrders verbindet den Lauf mit den betroffenen Orders, damit Wiederholung und Nachdruck transaktional nachvollziehbar sind.": (
        "Store print and label runs as PrintJobs plus PrintJobOrders; the single legacy import table is split through normalization because one print run bundles many orders (m:n). PrintJobs carries the run with status, creation time, handoff time, label-sheet count, and ZUBA postal code (spec ch. 16.3.5); PrintJobOrders links the run to the affected Orders so repeat printing and reprints are transactionally traceable."
    ),
    "Gebühren, Zahlungsstatus, offene Inkassofälle und Exportbezüge in BillingRecords speichern. Orders referenziert den aktuellen BillingRecord; Detailverläufe werden über BillingEvents geführt. spec ch. 19: offene Fälle tragen den OPAL-Fehlertext und werden mit dem Ergebnis Kulanz bzw. Rechnung ausgelöst (jeweils mit Anmerkung) abgeschlossen.": (
        "Store fees, payment status, open collection cases, and export references in BillingRecords. Orders references the current BillingRecord; detailed history is kept through BillingEvents. Spec chapter 19: open cases carry the {EXTERNAL-SYSTEM} error text and are resolved with the outcome courtesy adjustment (goodwill) resp. invoice issued, each with a remark."
    ),
    "Create-, Update-, Cancel- und Admin-Aktionen in AuditLog speichern. Die Tabelle ist append-only, referenziert fachliche Aggregate per stabilem Schlüssel und speichert Benutzer-, Organisations-, IP- und Zeitkontext (spec ch. 7). Aktionsdomäne lt. Kap. 16.3.6/21.2: Neu, Datenkorrektur, Verlängerung, Verlängerung und Adressänderung, Storno, Widerruf, Etikettennachdruck, Verrechnung.": (
        "Store create, update, cancel, and admin actions in AuditLog. The table is append-only, references business aggregates by stable key, and stores user, organization, IP, and time context (spec ch. 7). Action domain per ch. 16.3.6/21.2: Neu, Datenkorrektur, Verlängerung, Verlängerung und Adressänderung, Storno, Widerruf, Etikettennachdruck, Verrechnung."
    ),
    "hoch": "high",
    "mittel": "medium",
    "niedrig": "low",
    "Produktkatalog und Formulararten": "Product catalog and form types",
    "Auftragskopf und zentraler Lebenszyklus": "Order header and core lifecycle",
    "Gültigkeit, Dauer und Produktregeln": "Validity, duration, and product rules",
    "Ursprung, Ziel, Adresse und Routing": "Origin, destination, address, and routing",
    "Personen, Empfänger, Kunden und Firmen": "Persons, recipients, customers, and companies",
    "Kundenidentifikation, SSO und ExampleCrm": "Customer identification, SSO, and ExampleCrm",
    "Sendungsarten und Sendungsauswahl": "Shipment types and shipment selection",
    "Postfachprodukte und Postfachverwaltung": "Postbox products and postbox management",
    "ASG-Abstellgenehmigung": "ASG drop-off authorization",
    "BatchOrder und Massenimport": "Collective example and bulk import",
    "Verrechnung, Inkasso und Zahlungsstatus": "Billing, collection, and payment status",
    "Druck, Etiketten und Dateischnittstelle": "Print, labels, and file interface",
    "Suche, Reports und Historienansichten": "Search, reports, and history views",
    "Berechtigungen und rollenbasierter Zugriff": "Permissions and role-based access",
    "Storno, Löschung und Audit-Trail": "Cancellation, deletion, and audit trail",
    "Alle spec products": "All example products",
    "Alle Auftragsprodukte": "All order products",
    "PUM und Online-/Kundenflüsse": "PUM and online/customer flows",
    "PF, PFU und zahlungspflichtige Produkte": "PF, PFU, and chargeable products",
    "Druckrelevante Produkte": "Print-relevant products",
    "Operative Anwender": "Operational users",
    "Anwendungsbetrieb": "Application operations",
    "Alle stornierbaren Produkte": "All cancellable products",
    "Für dieses spec concept existiert eine klare C#-Domain-, Persistenz- oder API-Oberfläche. Das ist trotzdem kein vollständiger Beweis für Verhaltensparität.": (
        "A clear C# domain, persistence, or API surface exists for this specconcept. "
        "This is still not full proof of behavior parity."
    ),
    "C# setzt Teile des spec/legacy concept um; Felder, Workflow-Schritte, Reports, Integrationen oder historisches Verhalten bleiben offen.": (
        "C# implements parts of the spec/legacy concept; fields, workflow steps, reports, "
        "integrations, or historical behavior remain open."
    ),
    "Der statische Scan hat keinen belastbaren C#-Implementierungsnachweis gefunden.": (
        "The static scan found no robust C# implementation evidence."
    ),
    "Legacy SQL speichert Produkt- bzw. Auftragsarten und Sendungszuordnungen in Katalogtabellen.": (
        "Legacy SQL stores product/order types and shipment mappings in catalog tables."
    ),
    "C# enthält DirectiveType, initialisierte Directives, Directive-Einstellungen und EF-Tabellen für die Katalogdaten.": (
        "C# contains DirectiveType, seeded Directives, Directive settings, and EF tables for catalog data."
    ),
    "Vollständig bedeutet hier, dass die Katalogoberfläche vorhanden ist; es beweist nicht, dass jeder Produktworkflow vollständig umgesetzt ist.": (
        "Full means the catalog surface exists; it does not prove that every product workflow is fully implemented."
    ),
    "Legacy SQL bündelt Aufträge in TOrderHead und speichert dort Gültigkeit, Formularnummer, Typ, Kontakt-, Druck-, Storno- und SSO-Felder.": (
        "Legacy SQL groups orders in TOrderHead and stores validity, form number, type, contact, print, cancellation, and SSO fields there."
    ),
    "C# besitzt das aktive DirectiveOrder-Aggregat und die Orders-Tabelle für Formularnummer, Gültigkeit, Typ, Zahlungsstatus, Routing und JSON-Auftragsdaten.": (
        "C# has the active DirectiveOrder aggregate and Orders table for form number, validity, type, payment status, routing, and JSON order data."
    ),
    "Legacy-Storno, Druckkennzeichen, Audit-Bezüge und mehrere historische Felder sind nicht eins zu eins als C#-Spalten vorhanden.": (
        "Legacy cancellation fields, print markers, audit references, and several historical fields are not present one-to-one as C# columns."
    ),
    "Legacy SQL speichert Datumsfelder und implementiert Aktuell-/Gültig-/Report-Filter in Funktionen.": (
        "Legacy SQL stores date fields and implements current/valid/report filters in functions."
    ),
    "C# speichert Gültigkeit und Produkteinstellungen; eine Parität zu allen SQL-Funktionsfällen für aktuell, abgelaufen oder storniert ist aber nicht belegt.": (
        "C# stores validity and product settings, but parity with all SQL function cases for current, expired, or cancelled orders is not proven."
    ),
    "Datums- und Statusübergänge müssen gegen bestätigte spec rules validiert werden, bevor dieser Bereich als fachlich vollständig gilt.": (
        "Date and status transitions must be validated against confirmed specrules before this area can be considered functionally complete."
    ),
    "Legacy SQL kombiniert Zieladresszeilen, Adressformatierungsfunktionen, PAC-Daten und Provider-Standortreferenzen.": (
        "Legacy SQL combines destination address rows, address-formatting functions, PAC data, and provider location references."
    ),
    "C# hat Routing-Entitäten und ein Address-Aggregat mit PAC-, PLZ-, Orts-, Straßen- und Hausnummernfeldern.": (
        "C# has routing entities and an Address aggregate with PAC, postal code, city, street, and house-number fields."
    ),
    "Provider-Standort, Postlagernd und das alte Adressformatierungsverhalten sind nicht vollständig als direkte C#-Tabellen abgebildet.": (
        "Provider location, general delivery, and legacy address-formatting behavior are not fully represented as direct C# tables."
    ),
    "Legacy SQL nutzt Detailzeilen und ExtPerson-/CLR-Wrapper, um legacy orders mit Personen- und Empfängerdaten zu verbinden.": (
        "Legacy SQL uses detail rows and ExtPerson/CLR wrappers to connect legacy orders with person and recipient data."
    ),
    "C# hat Entitäten für Kunden, Firmen, Auftraggeber und Identifikation; Parität zu ExtPerson bzw. dem Personenprovider ist aber nicht bestätigt.": (
        "C# has entities for customers, companies, order owners, and identification; parity with ExtPerson/person-provider behavior is not confirmed."
    ),
    "ExtPerson-Suche, Get-Person-Verhalten und die Semantik der Detailzeilen müssen auf Integrationsebene bestätigt werden.": (
        "ExtPerson search, get-person behavior, and detail-row semantics must be confirmed at integration level."
    ),
    "Legacy SQL speichert SSO-Identifikation, SSO-Löschung und Registrierungsfeedback in eigenen Tabellen.": (
        "Legacy SQL stores SSO identification, SSO deletion, and registration feedback in dedicated tables."
    ),
    "C# hat Kundenidentifikationsentitäten und ExampleCrm-/SSO-Integrationsfelder, aber keine dedizierten SSO-Persistenztabellen im Legacy-Stil.": (
        "C# has customer-identification entities and ExampleCrm/SSO integration fields, but no dedicated legacy-style SSO persistence tables."
    ),
    "Klären, ob SSO-Lebenszyklus und Audit-Speicherung in der C#-Erweiterung liegen oder von externen Systemen verantwortet werden.": (
        "Clarify whether the SSO lifecycle and audit storage belong in the C# extension or remain owned by external systems."
    ),
    "Legacy SQL speichert Sendungsartenkataloge und Produktzuordnungen.": (
        "Legacy SQL stores shipment-type catalogs and product mappings."
    ),
    "C# hat initialisierte Sendungsartgruppen und Sendungsarten, die vom Directive-Aggregat gehalten werden.": (
        "C# has seeded shipment type groups and shipment types owned by the Directive aggregate."
    ),
    "Auftragsspezifische Sendungsauswahlen sollten trotzdem pro Produktworkflow geprüft werden.": (
        "Order-specific shipment selections should still be checked per product workflow."
    ),
    "Legacy SQL enthält eigene Tabellen für Postfach-Stammdaten, Postfachstandorte und Postfachstatus.": (
        "Legacy SQL contains dedicated tables for postbox master data, postbox locations, and postbox status."
    ),
    "C# hat Postfach-Directive-Typen und eine Routing-Markierung für Postfachziele.": (
        "C# has postbox directive types and a routing marker for postbox destinations."
    ),
    "Eine dedizierte Verwaltung für Postfach-Stammdaten, Standort und Status ist nicht als aktive EF-Tabelle vorhanden.": (
        "Dedicated management of postbox master data, location, and status is not present as an active EF table."
    ),
    "Legacy SQL speichert Abstellorte und ASG-spezifische Werte.": (
        "Legacy SQL stores drop-off locations and ASG-specific values."
    ),
    "C# speichert ASG-Abstellort-lookup-Daten und ausgewählte Abstellfelder in polymorphen Auftragsdaten.": (
        "C# stores ASG drop-off lookup data and selected drop-off fields in polymorphic order data."
    ),
    "Das ist kein eins-zu-eins-Tabellenklon; Produktworkflow und Event-Verhalten müssen weiterhin auf Anforderungsebene validiert werden.": (
        "This is not a one-to-one table clone; product workflow and event behavior still need requirement-level validation."
    ),
    "Legacy SQL hat eine Staging-/Importtabelle und einen Transformations-/Speicherpfad für bulk order rows.": (
        "Legacy SQL has a staging/import table and a transformation/storage path for bulk order rows."
    ),
    "C# hat den Produkttyp SAM bzw. CollectiveDomainConceptA, aber keine dedizierte Import-/Staging-EF-Tabelle.": (
        "C# has the SAM / CollectiveDomainConceptA product type, but no dedicated import/staging EF table."
    ),
    "Massenimport-Verarbeitung, Dublettenprüfung und zeilenweise Validierung sind offene Implementierungsfragen.": (
        "Bulk import processing, duplicate checks, and row-by-row validation are open implementation questions."
    ),
    "Legacy SQL speichert detaillierte Verrechnungs-/Inkassozeilen, Status, Historie und Beträge.": (
        "Legacy SQL stores detailed billing/collection rows, status, history, and amounts."
    ),
    "C# speichert einen groben Zahlungsstatus am Auftrag in Orders.": (
        "C# stores a coarse payment status on the order in Orders."
    ),
    "Detaillierter Verrechnungslebenszyklus, Inkassometadaten, Beträge und Historie sind nicht durch gleichwertige C#-Tabellen abgebildet.": (
        "The detailed billing lifecycle, collection metadata, amounts, and history are not represented by equivalent C# tables."
    ),
    "Legacy SQL enthält Druckauswahl- und Druckhilfsfunktionen für Etiketten- und Kuvertausgaben.": (
        "Legacy SQL contains print-selection and print-helper functions for label and envelope output."
    ),
    "C# hat Hinweise auf Label-Request- bzw. Berechtigungsoberflächen; der Legacy-Druckdateivertrag ist aber nicht als offensichtliches C#-Äquivalent umgesetzt.": (
        "C# has evidence of label-request or permission surfaces, but the legacy print-file contract is not implemented as an obvious C# equivalent."
    ),
    "Druck/Kuvertierung separat als Schnittstellenvertrag prüfen, bevor Parität angenommen oder implementiert wird.": (
        "Review print/enveloping separately as an interface contract before assuming or implementing parity."
    ),
    "Legacy SQL enthält Suchfunktionen, Reports, Exporte, Historie und Logtabellen.": (
        "Legacy SQL contains search functions, reports, exports, history, and log tables."
    ),
    "C# zeigt Such-/Indexierungsnachweise über Typesense und Directive-Order-Filter.": (
        "C# shows search/indexing evidence through Typesense and directive-order filters."
    ),
    "Konkrete Legacy-Reports, Exporte sowie Historien-/Auditmasken sind nicht als vollständig nachgewiesen.": (
        "Specific legacy reports, exports, and history/audit screens are not proven complete."
    ),
    "Legacy SQL enthält Berechtigungstabellen sowie Datenbank-Grants und Rollen.": (
        "Legacy SQL contains permission tables plus database grants and roles."
    ),
    "C# hat ein Auth-Schema und ein Rollen-/Berechtigungsmodell, ist aber strukturell anders als die Legacy-Flags.": (
        "C# has an auth schema and role/permission model, but it is structurally different from the legacy flags."
    ),
    "Legacy-Betriebsrollen müssen mit Product-Owner-Bestätigung auf das C#-Autorisierungsmodell gemappt werden.": (
        "Legacy operational roles must be mapped to the C# authorization model with product-owner confirmation."
    ),
    "Legacy SQL enthält Storno-/Löschprozeduren, Stornospalten und Audit-Log-Schreibvorgänge.": (
        "Legacy SQL contains cancellation/deletion procedures, cancellation columns, and audit-log writes."
    ),
    "Der statische Scan fand kein klares aktives C#-Äquivalent für Storno-/Audit-Persistenz.": (
        "The static scan found no clear active C# equivalent for cancellation/audit persistence."
    ),
    "Dieser Bereich braucht explizite Anforderungen und Implementierungsdesign, bevor Legacy-Verhaltensannahmen entfernt oder geändert werden.": (
        "This area needs explicit requirements and implementation design before legacy behavior assumptions are removed or changed."
    ),
}

MKDOCS_EN_TEXT.update(
    {
        "ASG-Abstellorte im bestehenden Lookups-Modell belassen": "Keep ASG drop-off locations in the existing Lookups model",
        "Legacy-Berechtigungen in das bestehende C#-RBAC-Schema migrieren": "Migrate legacy permissions into the existing C# RBAC schema",
        "Bestehende OrderRoutingAddresses und OrderRoutingPostOfficeBoxes verwenden": "Use the existing OrderRoutingAddresses and OrderRoutingPostOfficeBoxes",
        "Änderungs- und Stornogründe im bestehenden Lookups-Modell führen": "Keep change and cancellation reasons in the existing Lookups model",
        "Bestehende Customers- und Companies-Teilnehmerentitäten verwenden": "Use the existing Customers and Companies participant entities",
        "Postfach-Stammdatenmodell ergänzen": "Add the postbox master-data model",
        "Postfach-Standortkatalog relational einführen": "Introduce a relational postbox-location catalog",
        "Postfachstatus im bestehenden Lookups-Modell führen": "Keep postbox status values in the existing Lookups model",
        "RegistrationFeedbackEvents als append-only Integrationslog einführen": "Introduce RegistrationFeedbackEvents as an append-only integration log",
        "SsoIdentifications als relationale Identifikationshistorie einführen": "Introduce SsoIdentifications as a relational identification history",
        "SsoDeletionEvents als append-only Audit-Tabelle einführen": "Introduce SsoDeletionEvents as an append-only audit table",
        "BatchImports als ACID-Importaggregat einführen": "Introduce BatchImports as an ACID import aggregate",
        "OrderShipmentTypeSelections als Join-Tabelle einführen": "Introduce OrderShipmentTypeSelections as a join table",
        "ServiceInformation nicht als C#-Fachtabelle portieren": "Do not port ServiceInformation as a C# domain table",
        "Titel als constrained columns auf Personendaten beibehalten": "Keep titles as constrained columns on person data",
        "BillingRecords als Verrechnungsaggregat einführen": "Introduce BillingRecords as the billing aggregate",
        "Bestehenden DirectivePaymentStatus / Orders.PaymentStatus verwenden": "Use the existing DirectivePaymentStatus / Orders.PaymentStatus",
        "Nicht als Business-Tabelle portieren": "Do not port as a business table",
        "BillingEvents als append-only Historientabelle einführen": "Introduce BillingEvents as an append-only history table",
        "PrintJobs als ACID-Jobtabelle einführen": "Introduce PrintJobs as an ACID job table",
        "ParcelPostExceptions als Regel-Ausnahmetabelle einführen": "Introduce ParcelPostExceptions as a rule-exception table",
        "AuditLog als append-only Fach-Audit-Tabelle einführen": "Introduce AuditLog as an append-only business audit table",
        "Nicht als C#-Domänentabelle portieren": "Do not port as a C# domain table",
        "ProviderLocations als synchronisiertes Standort-Read-Model einführen": "Introduce ProviderLocations as a synchronized location read model",
        "Fachliche Ownership klären": "Clarify business ownership",
        "Keine separate DropOffLocations-Tabelle einführen. Die clientbestätigte C#-Zielstruktur ist LookupConfiguration/Lookups mit LookupType.AsgDropOffLocation. Bei der Umsetzung nur prüfen, dass Sortierung, Aktiv-Status und Freitext-Erlaubnis vollständig im Lookup-Item-Modell abgebildet und die Auftragsdaten dagegen validiert werden.": (
            "Do not introduce a separate DropOffLocations table. The client-confirmed C# target surface is LookupConfiguration/Lookups with LookupType.AsgDropOffLocation. During implementation, only verify that sorting, active state, and free-text permission are fully represented in the lookup-item model and that order data is validated against it."
        ),
        "Die Legacy-Tabelle enthält die fachliche ASG-Abstellort-Auswahlliste. Der Client hat bestätigt, dass diese fachliche Liste im C#-System über LookupConfiguration verwaltet wird; technisch ist das die bestehende Lookups-Tabelle mit dem Schlüssel asg-drop-off-location.": (
            "The legacy table contains the business ASG drop-off selection list. The client confirmed that this list is managed in the C# system through LookupConfiguration; technically, this is the existing Lookups table with the key asg-drop-off-location."
        ),
        "Die fachlich bestätigten Legacy-Rechte als Daten in das bestehende Rollen- und Permission-Modell übernehmen. DB-Constraints sichern eindeutige Permission-Namen und konsistente Rollen-Zuordnungen.": (
            "Import the business-confirmed legacy rights as data into the existing role and permission model. DB constraints enforce unique permission names and consistent role assignments."
        ),
        "C# hat bereits ein strukturell anderes Rollen-/Permission-Schema. Wichtig ist daher die fachliche Rollenparität, nicht eine identische Tabellenstruktur.": (
            "C# already has a structurally different role/permission schema. The important target is business role parity, not an identical table structure."
        ),
        "Keine neue generische OrderRouting-Tabelle einführen. Die vorhandenen C#-Entitäten OrderRoutingAddresses, OrderRoutingPostOfficeBoxes und Addresses bleiben das Ziel für Ursprung, Ziel, PAC/PLZ und Postfachrouting; fehlende TDestination-Felder werden dort gezielt ergänzt.": (
            "Do not introduce a new generic OrderRouting table. The existing C# entities OrderRoutingAddresses, OrderRoutingPostOfficeBoxes, and Addresses remain the target for origin, destination, PAC/postal code, and postbox routing; missing TDestination fields should be added there deliberately."
        ),
        "Der C#-Backend-Code nutzt TPC-Entitäten für Routing statt einer einzelnen Tabelle. Diese Bestandsentitäten sind die passende Zieloberfläche für TDestination-Semantik.": (
            "The C# backend uses TPC entities for routing instead of a single table. These existing entities are the right target surface for TDestination semantics."
        ),
        "Keine separate OrderChangeReasons-Tabelle einführen. Die kontrollierte Liste wird als neuer Lookup-Typ in Lookups geführt; Audit- und Storno-Daten speichern den bestätigten Grundcode.": (
            "Do not introduce a separate OrderChangeReasons table. Keep the controlled list as a new lookup type in Lookups; audit and cancellation data store the confirmed reason code."
        ),
        "Der C#-Backend-Code hat mit Lookups bereits eine generische, konfigurierte Oberfläche für kontrollierte Katalogwerte. TOrderChangeReason passt in dieses vorhandene Muster.": (
            "The C# backend already has Lookups as a generic, configured surface for controlled catalog values. TOrderChangeReason fits that existing pattern."
        ),
        "Keine separate OrderRecipients-Tabelle einführen. Die bestehenden C#-Tabellen Customers und Companies bleiben die Auftrags-Teilnehmeroberfläche; fehlende Legacy-Detailsemantik wie laufende Nummer, NeuerEmpfaenger und Gültigkeits-/Stornozustand wird in den bestehenden Teilnehmer- und Auftragsdaten gezielt ergänzt.": (
            "Do not introduce a separate OrderRecipients table. The existing C# tables Customers and Companies remain the order-participant surface; missing legacy detail semantics such as sequence number, NeuerEmpfaenger, and validity/cancellation state should be added deliberately to the existing participant and order data."
        ),
        "DirectiveOrder besitzt bereits Customers- und Companies-Collections mit EF-Tabellen und DirectiveOrderId-Bezug. Diese vorhandenen Entitäten sind die passende Zieloberfläche für TOrderDetail; ein zusätzlicher Recipient-Klon wäre redundant.": (
            "DirectiveOrder already has Customers and Companies collections with EF tables and a DirectiveOrderId relation. These existing entities are the right target surface for TOrderDetail; an additional recipient clone would be redundant."
        ),
        "Postfachbestand, Größe, Status, PLZ/PF-Kombinationen und Verfügbarkeiten in einer PostOfficeBoxes-Tabelle mit FKs zu Standort und Status persistieren.": (
            "Persist postbox inventory, size, status, postal-code/postbox combinations, and availability in a PostOfficeBoxes table with FKs to location and status."
        ),
        "C# kennt Postfachprodukte und Routingmarker, aber keine vollständige Master-Data-Tabelle für Postfachbestand und Status.": (
            "C# knows postbox products and routing markers, but no complete master-data table for postbox inventory and status."
        ),
        "Postfachstandorte, PLZ/Ort/Filialbezüge und Standortgültigkeit in einer PostOfficeBoxLocations-Tabelle speichern. PostOfficeBoxes referenziert diese Tabelle per FK.": (
            "Store postbox locations, postal-code/city/branch references, and location validity in a PostOfficeBoxLocations table. PostOfficeBoxes references this table by FK."
        ),
        "Legacy SQL hat einen Standortkatalog; C# hat allgemeine Adressen und Routing, aber keinen entsprechenden Postfach-Standortbestand.": (
            "Legacy SQL has a location catalog; C# has general addresses and routing, but no equivalent postbox-location inventory."
        ),
        "Keine separate PostOfficeBoxStatuses-Tabelle einführen. Postfachstatuswerte werden als kontrollierter Lookup-Typ in Lookups geführt; PostOfficeBoxes speichert den bestätigten Statuscode.": (
            "Do not introduce a separate PostOfficeBoxStatuses table. Keep postbox status values as a controlled lookup type in Lookups; PostOfficeBoxes stores the confirmed status code."
        ),
        "Die Legacy-Tabelle enthält Statuswerte; C# hat dafür kein Spezialmodell, aber bereits die generische Lookups-Oberfläche.": (
            "The legacy table contains status values; C# has no special model for them, but it already has the generic Lookups surface."
        ),
        "Registrierungs- und Kundennummernfeedback als append-only Ereignisse speichern, damit jedes externe Feedback atomar mit dem betroffenen Auftrag nachvollziehbar bleibt.": (
            "Store registration and customer-number feedback as append-only events so every external feedback message remains atomically traceable to the affected order."
        ),
        "Die Legacy-Tabelle wirkt wie Integrationsfeedback; im aktuellen C#-Persistenzmodell ist keine entsprechende fachliche Oberfläche sichtbar.": (
            "The legacy table looks like integration feedback; no corresponding business persistence surface is visible in the current C# model."
        ),
        "SSO-Zuordnung, Level-90-Nachweis, Bearbeiter und Erfassungszeitpunkt in SsoIdentifications persistieren und per FK an Orders sowie CustomerIdentifications binden.": (
            "Persist SSO assignment, level-90 evidence, clerk, and capture time in SsoIdentifications and bind them by FK to Orders and CustomerIdentifications."
        ),
        "C# enthält Identifikations- und Integrationsfelder, aber kein direktes Legacy-Äquivalent für SSO-Identifizierungszeilen.": (
            "C# contains identification and integration fields, but no direct legacy equivalent for SSO identification rows."
        ),
        "Jede SSO-Löschung wird als unveränderliches Ereignis mit FK zu CustomerIdentifications und Orders gespeichert. Eine Löschung der aktiven Zuordnung erzeugt immer denselben Audit-Datensatz.": (
            "Store every SSO deletion as an immutable event with FKs to CustomerIdentifications and Orders. Deleting the active assignment always creates the same audit record."
        ),
        "Die Legacy-Tabelle ist lösch- und auditnah; C# hat dafür keinen direkten Persistenznachweis.": (
            "The legacy table is close to deletion and audit behavior; C# has no direct persistence evidence for it."
        ),
        "SAM-CSV-Importe werden über BatchImports, BatchImportRows und BatchImportErrors persistiert. Die eine Legacy-Staging-Tabelle wird dabei bewusst normalisiert auf drei Tabellen aufgeteilt: TBatchOrder wiederholt Batch-Kopfdaten (Firma, SAP-Deb.Nr.) auf jeder Zeile, hat keinen Batch-Status und presst mehrere Validierungsfehler in einzelne Textspalten (error, Dubletten). Im Zielmodell trägt BatchImports den Auftrag/Upload (ein Datensatz je Großkunden-Import), BatchImportRows je CSV-Zeile Status und Order-FK, BatchImportErrors beliebig viele strukturierte Fehler je Zeile. Nur erfolgreich validierte Zeilen erzeugen Orders; Jobstatus, Zeilenstatus und Fehler bleiben transaktional nachvollziehbar.": (
            "Persist SAM CSV imports through BatchImports, BatchImportRows, and BatchImportErrors. The single legacy staging table is deliberately normalized into three tables: TBatchOrder repeats batch header data (company, SAP debtor no.) on every row, has no batch status, and squeezes multiple validation errors into single text columns (error, Dubletten). In the target model BatchImports carries the upload (one record per bulk-customer import), BatchImportRows carries per-CSV-line status and the Order FK, and BatchImportErrors holds any number of structured errors per row. Only successfully validated rows create Orders; job status, row status, and errors remain transactionally traceable."
        ),
        "C# kennt den SAM-Produkttyp, aber kein Staging- und Row-Level-Modell für BatchOrder-Importe. Die flache Legacy-Tabelle mischt drei Lebenszyklen (Import-Job, CSV-Zeile, Fehler) in einem Datensatz.": (
            "C# knows the SAM product type, but no staging and row-level model for BatchOrder imports. The flat legacy table mixes three lifecycles (import job, CSV line, error) in a single record."
        ),
        "Pro Auftrag gewählte Sendungsarten werden in einer normalisierten Join-Tabelle gespeichert. Die Tabelle referenziert Orders und ShipmentTypes per FK und trägt die Auswahl für Filter, Druck und Reporting.": (
            "Store shipment types selected per order in a normalized join table. The table references Orders and ShipmentTypes by FK and carries the selection for filtering, printing, and reporting."
        ),
        "C# hat Sendungsart-Kataloge, aber kein klares normalisiertes per-order Äquivalent zur Legacy-Zuordnung.": (
            "C# has shipment-type catalogs, but no clear normalized per-order equivalent to the legacy mapping."
        ),
        "Keine neue C#-Fachtabelle anlegen. Serviceinformationen bleiben außerhalb des ACID-Domänenmodells, bis eine bestätigte Anforderung eine konkrete Verwaltung dieser Daten verlangt.": (
            "Do not create a new C# domain table. Keep service information outside the ACID domain model until a confirmed requirement asks for concrete management of this data."
        ),
        "Der statische Scan zeigt keine aktive C#-Persistenzoberfläche für diese Legacy-Tabelle.": (
            "The static scan shows no active C# persistence surface for this legacy table."
        ),
        "Keine dedizierte Titel-Lookup-Tabelle einführen. Titel bleiben als längenbegrenzte Spalten auf den bestehenden Personen- und Identitätstabellen erhalten.": (
            "Do not introduce a dedicated title lookup table. Keep titles as length-constrained columns on the existing person and identity tables."
        ),
        "C# speichert Titel bereits auf Personen-/Identifikationsdaten; die Legacy-Lookup-Tabelle ist nur als historischer Katalognachweis relevant.": (
            "C# already stores titles on person/identity data; the legacy lookup table is only relevant as historical catalog evidence."
        ),
        "Gebühren, Zahlungsstatus, offene Inkassofälle und Exportbezüge in BillingRecords speichern. Orders referenziert den aktuellen BillingRecord; Detailverläufe werden über BillingEvents geführt.": (
            "Store fees, payment status, open collection cases, and export references in BillingRecords. Orders references the current BillingRecord; detailed history is kept through BillingEvents."
        ),
        "Die Legacy-Tabelle enthält detaillierte Verrechnungsdaten; C# hat aktuell nur einen kompakten PaymentStatus auf Orders.": (
            "The legacy table contains detailed billing data; C# currently only has a compact PaymentStatus on Orders."
        ),
        "Keine separate BillingStatuses-Tabelle einführen. Der vorhandene Statusanker bleibt DirectivePaymentStatus auf Orders.PaymentStatus; BillingRecords und BillingEvents übernehmen den bestätigten Statuswert als transaktionales Feld.": (
            "Do not introduce a separate BillingStatuses table. The existing status anchor remains DirectivePaymentStatus on Orders.PaymentStatus; BillingRecords and BillingEvents carry the confirmed status value as a transactional field."
        ),
        "Der C#-Backend-Code hat bereits eine PaymentStatus-Spalte und ein DirectivePaymentStatus-Enum. Ein zusätzlicher Statuskatalog wäre ohne bestätigte neue Statuspflege redundant.": (
            "The C# backend already has a PaymentStatus column and a DirectivePaymentStatus enum. An additional status catalog would be redundant without confirmed new status maintenance."
        ),
        "Diese Backup-/Deleted-Tabelle nicht als aktive C#-Domänentabelle übernehmen. Fachliche Historie wird über BillingEvents abgedeckt; technische Retention bleibt außerhalb des {PROJECT-NAME}-Domänenmodells.": (
            "Do not take over this backup/deleted table as an active C# domain table. Business history is covered by BillingEvents; technical retention stays outside the {PROJECT-NAME} domain model."
        ),
        "Der Tabellenname und die Struktur sprechen für Legacy-Backupdaten statt aktiver Fachpersistenz.": (
            "The table name and structure indicate legacy backup data rather than active business persistence."
        ),
        "Jede fachliche Änderung an BillingRecords wird als unveränderlicher BillingEvents-Datensatz gespeichert. Statuswechsel, Betragsänderungen und Benutzerkontext bleiben damit revisionssicher.": (
            "Store every business change to BillingRecords as an immutable BillingEvents record. Status changes, amount changes, and user context remain audit-safe."
        ),
        "C# hat keinen direkten Nachweis für detaillierte Verrechnungshistorie.": (
            "C# has no direct evidence for detailed billing history."
        ),
        "Druck- und Etikettenläufe als PrintJobs speichern. Jeder Job bekommt Status, Erstellzeit, Übergabezeit und referenzierte Orders, damit Wiederholung und Nachdruck transaktional nachvollziehbar sind.": (
            "Store print and label runs as PrintJobs. Each job gets status, creation time, handoff time, and referenced Orders so repeat printing and reprints are transactionally traceable."
        ),
        "Die Legacy-Tabelle ist drucknah; C# zeigt aktuell kein direktes Print-Import-Persistenzmodell.": (
            "The legacy table is print-related; C# currently shows no direct print-import persistence model."
        ),
        "Paketpost-Ausnahmen relational mit Produkt-/Auftragstypbezug und PLZ-Bezug speichern. Eindeutige Constraints verhindern doppelte Ausnahmezeilen.": (
            "Store parcel-post exceptions relationally with product/order-type and postal-code references. Unique constraints prevent duplicate exception rows."
        ),
        "Der statische Scan zeigt keine aktive C#-Entsprechung und keine ausreichende Fachsemantik.": (
            "The static scan shows no active C# equivalent and not enough business semantics."
        ),
        "C# hat Formularnummernlogik, aber keine legacygleiche Zählertabelle.": (
            "C# has form-number logic, but no legacy-equivalent counter table."
        ),
        "Create-, Update-, Cancel- und Admin-Aktionen in AuditLog speichern. Die Tabelle ist append-only, referenziert fachliche Aggregate per stabilem Schlüssel und speichert Benutzer- sowie Zeitkontext.": (
            "Store create, update, cancel, and admin actions in AuditLog. The table is append-only, references business aggregates by stable key, and stores user and time context."
        ),
        "Legacy SQL schreibt Logdaten; C# zeigt aktuell keine gleichwertige fachliche Audit-Persistenz.": (
            "Legacy SQL writes log data; C# currently shows no equivalent business audit persistence."
        ),
        "Nicht in das C#-Domänenmodell übernehmen. EF-Migrationshistorie bleibt die maßgebliche technische Schemahistorie für die neue Anwendung.": (
            "Do not include this in the C# domain model. EF migration history remains the authoritative technical schema history for the new application."
        ),
        "Die Tabelle ist schema-/deploymentnah und keine sichtbare {PROJECT-NAME}-Fachentität.": (
            "The table is schema/deployment-related and not a visible {PROJECT-NAME} business entity."
        ),
        "Provider- und Filialstandorte in ProviderLocations synchronisieren. PAC, PLZ, Gültigkeit und Standorttyp erhalten eindeutige Keys und werden von Routing- und Postfachdaten per FK genutzt.": (
            "Synchronize provider and branch locations into ProviderLocations. PAC, postal code, validity, and location type get unique keys and are used by routing and postbox data through FKs."
        ),
        "Legacy SQL nutzt providerseitige Standortdaten; C# hat allgemeine Adressen, aber keinen direkten ref.RLocation-Ersatz.": (
            "Legacy SQL uses provider-side location data; C# has general addresses, but no direct ref.RLocation replacement."
        ),
        "Diese Legacy-Tabelle braucht eine explizite ACID-Entscheidung, bevor sie in die C#-Persistenz übernommen wird.": (
            "This legacy table needs an explicit ACID decision before it is included in C# persistence."
        ),
        "Der statische Scan fand keine klare C#-Abdeckung und keine spezifische Empfehlungsregel.": (
            "The static scan found no clear C# coverage and no specific recommendation rule."
        ),
    }
)

MKDOCS_EN_TEXT.update(
    {
        "Bestehende Orders-Tabelle wird als ACID-Anker genutzt; ASG-spezifische Abstellortauswahl liegt aktuell in den polymorphen Auftragsdaten.": "The existing Orders table is used as the ACID anchor; ASG-specific drop-off selection currently lives in polymorphic order data.",
        "Bestehender Produktkatalog als referenzielle Basis für Import-, Druck- und Regelbezüge.": "Existing product catalog used as the referential base for import, print, and rule references.",
        "Bestehende Adresstabelle bleibt das Ziel für normalisierte Routingadressen.": "The existing address table remains the target for normalized routing addresses.",
        "Titel bleiben constrained columns; SSO-Identifikation wird über Ereignis- und Historientabellen ergänzt.": "Titles remain constrained columns; SSO identification is added through event and history tables.",
        "Bestehender Personenanker für Empfänger- und Identitätsbezüge.": "Existing person anchor for recipient and identity references.",
        "Bestehender Firmenanker für Empfänger- und SAM-Bezüge.": "Existing company anchor for recipient and SAM references.",
        "Bestehende TPC-Tabelle für private Auftraggeber; Orders.OwnerId zeigt konzeptionell auf Auftraggeberdaten.": "Existing TPC table for private order owners; Orders.OwnerId conceptually points to owner data.",
        "Bestehende TPC-Tabelle für Firmen-Auftraggeber; keine neue Owner-Tabelle empfohlen.": "Existing TPC table for company order owners; no new owner table is recommended.",
        "Bestehende C#-Gruppierung für Sendungsarten je Directive; auftragsbezogene Auswahl bleibt separat zu prüfen.": "Existing C# grouping for shipment types per Directive; order-specific selection still needs separate review.",
        "Bestehender Sendungsartkatalog; auftragsbezogene Auswahl wird normalisiert ergänzt.": "Existing shipment-type catalog; order-specific selection is added in normalized form.",
        "Bestehende C#-Lookup-Tabelle, konfiguriert durch LookupConfiguration; ASG-Abstellorte liegen bereits unter LookupType.AsgDropOffLocation, weitere kontrollierte Kataloge werden als neue Lookup-Typen ergänzt.": "Existing C# lookup table configured through LookupConfiguration; ASG drop-off locations already live under LookupType.AsgDropOffLocation, and further controlled catalogs are added as new lookup types.",
        "Bestehende konkrete C#-Routingtabelle für Adressziele; Orders.OriginId/DestinationId verweist konzeptionell auf Routingentitäten.": "Existing concrete C# routing table for address destinations; Orders.OriginId/DestinationId conceptually points to routing entities.",
        "Bestehende konkrete C#-Routingtabelle für Postfachziele; sie ersetzt keinen Postfach-Stammdatenbestand.": "Existing concrete C# routing table for postbox destinations; it does not replace postbox master data.",
        "Normalisierte auftragsbezogene Sendungsartauswahl für Filter, Druck und Reporting.": "Normalized order-specific shipment-type selection for filtering, printing, and reporting.",
        "Append-only Fach-Audit für Create-, Update-, Cancel- und Admin-Aktionen.": "Append-only business audit for create, update, cancel, and admin actions.",
        "Serialisierbarer Nummernkreis für Formular- und technische Nummernvergabe.": "Serializable number range for form and technical number allocation.",
        "Regelausnahmen für paketpostnahe Sonderfälle mit eindeutigem Fachcode.": "Rule exceptions for parcel-post-related special cases with a unique business code.",
        "Synchronisiertes Standort-Read-Model für PAC-, Filial-, Routing- und Postfachbezüge.": "Synchronized location read model for PAC, branch, routing, and postbox references.",
        "Standortkatalog für Postfachbestand, Nummernkreise und Verfügbarkeit.": "Location catalog for postbox inventory, number ranges, and availability.",
        "Postfachbestand mit Standort, Status, Größe und Reservierungszustand.": "Postbox inventory with location, status, size, and reservation state.",
        "Historisiert SSO-Identifikationsnachweise mit Bezug zu Auftrag und Kunde.": "Stores SSO identification evidence history with references to order and customer.",
        "Append-only Ereignis für SSO-Löschungen mit revisionssicherem Hash.": "Append-only event for SSO deletions with an audit-safe hash.",
        "Append-only Feedbackprotokoll für externe Registrierungs- und Kundennummernrückmeldungen.": "Append-only feedback log for external registration and customer-number responses.",
        "Fachliches Verrechnungsaggregat für Betrag, Status, Debitor und Exportstatus.": "Business billing aggregate for amount, status, debtor, and export status.",
        "Append-only Historie für Statuswechsel, Betragsänderungen und fachliche Löschereignisse.": "Append-only history for status changes, amount changes, and business deletion events.",
        "Transaktionaler Kopf für SAM- und Massenimportläufe.": "Transactional header for SAM and bulk import runs.",
        "Zeilenebene des Imports; erfolgreiche Zeilen referenzieren den erzeugten Auftrag.": "Import row level; successful rows reference the created order.",
        "Validierungsfehler je Importzeile, ohne fehlerhafte Nutzdaten zu verlieren.": "Validation errors per import row without losing invalid payload data.",
        "Transaktionaler Druck- und Etikettenlauf mit Status und Übergabezeit.": "Transactional print and label run with status and handoff time.",
        "Verbindet Druckläufe mit Aufträgen, Kuverts und Etikettenzahlen.": "Connects print runs with orders, envelopes, and label counts.",
        "Bestehende Rollentabelle; Legacy-Rollen werden als bestätigte Rollendaten migriert.": "Existing role table; legacy roles are migrated as confirmed role data.",
        "Bestehende Permission-Tabelle; Legacy-Rechte werden als bestätigte Permission-Daten migriert.": "Existing permission table; legacy rights are migrated as confirmed permission data.",
        "Zieltabelle für rollenbasierte Legacy-Rechte; verbindet Rollen und Permissions referenziell.": "Target table for role-based legacy rights; connects roles and permissions referentially.",
        "Abstellort -> asg-drop-off-location lookup": "Drop-off location -> asg-drop-off-location lookup",
        "Aktion/Typ -> permission names and roles": "Action/type -> permission names and roles",
        "PAC/PLZ/Ort/Strasse/Hnr -> Addresses": "PAC/postal code/city/street/house number -> Addresses",
        "Postfach/postlagernd -> OrderRoutingPostOfficeBoxes": "postbox/general delivery -> OrderRoutingPostOfficeBoxes",
        "Postfach products -> DirectiveType/PostOfficeBox directives": "postbox products -> DirectiveType/PostOfficeBox directives",
        "legacy provider Standort/location master data": "legacy provider location master data",
    }
)


def mkdocs_en(value: object) -> str:
    text = "" if value is None else str(value)
    return MKDOCS_EN_TEXT.get(text, text)


def md_cell_en(value: object) -> str:
    return md_cell(mkdocs_en(value))


def md_br(items: Iterable[str], empty: str = "No evidence found in the static scan.") -> str:
    values = [item for item in items if item]
    return "<br>".join(values) if values else empty


def md_pdf_refs(refs: list[dict], limit: int = 3) -> str:
    return md_br(
        (
            f"{md_code(ref.get('pdf'))} page {md_cell(ref.get('page'))}: "
            f"{md_cell(', '.join(ref.get('terms', [])))}"
        )
        for ref in refs[:limit]
    )


def md_sql_refs(refs: list[dict], limit: int = 4) -> str:
    return md_br(
        (
            f"{md_code('{}:{}'.format(ref.get('file'), ref.get('line', 1)))} - "
            f"{md_cell(ref.get('object', ''))} ({md_cell(ref.get('category', 'SQL'))})"
        )
        for ref in refs[:limit]
    )


def md_csharp_refs(refs: list[dict], limit: int = 4) -> str:
    return md_br(md_code(f"{ref.get('file')}:{ref.get('line', 1)}") for ref in refs[:limit])


def md_file_refs(refs: list[dict], limit: int = 3) -> str:
    return md_br(md_code(f"{ref.get('file')}:{ref.get('line', 1)}") for ref in refs[:limit])


def html_cell(value: object) -> str:
    return html_escape(str(value)) if value not in (None, "") else ""


def html_cell_en(value: object) -> str:
    return html_escape(mkdocs_en(str(value))) if value not in (None, "") else ""


def html_evidence_list(items: Iterable[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return '<span class="sql-landscape-muted">No evidence found in the static scan.</span>'
    return "<br>".join(values)


def html_pdf_refs(refs: list[dict], limit: int = 3) -> str:
    return html_evidence_list(
        f"<code>{html_cell(ref.get('pdf'))}</code> page {html_cell(ref.get('page'))}: "
        f"{html_cell(', '.join(ref.get('terms', [])))}"
        for ref in refs[:limit]
    )


def html_sql_refs(refs: list[dict], limit: int = 4) -> str:
    return html_evidence_list(
        f"<code>{html_cell('{}:{}'.format(ref.get('file'), ref.get('line', 1)))}</code> - "
        f"{html_cell(ref.get('object', ''))} ({html_cell(ref.get('category', 'SQL'))})"
        for ref in refs[:limit]
    )


def html_code_refs(refs: list[dict], limit: int = 4) -> str:
    return html_evidence_list(
        f"<code>{html_cell('{}:{}'.format(ref.get('file'), ref.get('line', 1)))}</code>" for ref in refs[:limit]
    )


def html_requirement_links(refs: list[dict]) -> str:
    # use_directory_urls is false, so .md sources resolve to .html pages.
    return html_evidence_list(
        f'<a href="{html_cell((ref.get("href") or "").replace(".md", ".html"))}">{html_cell(ref.get("id"))}</a>'
        f" -- {html_cell(ref.get('title'))}"
        for ref in refs
        if ref.get("id")
    )


SQL_CHIP_KINDS = {
    "Full": "full",
    "Partial": "partial",
    "No direct evidence": "none",
    "No direct table": "none",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def html_chip(label: str, fallback_kind: str = "info") -> str:
    return f'<span class="sql-chip sql-chip-{SQL_CHIP_KINDS.get(label, fallback_kind)}">{html_cell(label)}</span>'


def html_card_detail_rows(pairs: list[tuple[str, str]]) -> str:
    return "".join(f"<dt>{html_cell(label)}</dt><dd>{content}</dd>" for label, content in pairs if content)


def md_requirement_links(refs: list[dict]) -> str:
    links = [
        f"[{md_cell(ref.get('id'))}]({md_cell(ref.get('href'))}) -- {md_cell(ref.get('title'))}"
        for ref in refs
        if ref.get("id")
    ]
    return "<br>".join(links) if links else "No evidence found in the static scan."


def md_mermaid_fence(source: str) -> str:
    return f"```mermaid\n{source.strip()}\n```"


def md_mermaid_div(source: str) -> str:
    return f'<div class="mermaid">\n{html_escape(source.strip())}\n</div>'


MKDOCS_ACID_STATUS_LABELS = {
    "exists": "Already exists in C#",
    "extend": "Extend existing C# table",
    "implement": "Implement new table",
}


def render_spec_mkdocs_er_diagrams(recommended_acid_er: dict) -> str:
    diagram_sections = []
    for diagram in recommended_acid_er.get("diagrams", []):
        table_rows = []
        status_map = {}
        status_lines = []
        for status, label in ACID_TABLE_STATUS_LABELS.items():
            names = [
                table.get("name", "")
                for table in diagram.get("tables", [])
                if table.get("implementation_status") == status
            ]
            if names:
                status_lines.append(
                    f'<div><span class="acid-status acid-status-{html_escape(status)}">{html_escape(label)}</span> '
                    f'<span class="sql-landscape-muted">{html_escape(", ".join(names))}</span></div>'
                )
        for table_row in diagram.get("tables", []):
            status = table_row.get("implementation_status", "")
            if status:
                status_map[table_row.get("name", "")] = status
                status_map[table_row.get("entity_id", "")] = status
            table_rows.append(
                "| "
                + " | ".join(
                    [
                        md_code(table_row.get("name")),
                        md_cell(
                            MKDOCS_ACID_STATUS_LABELS.get(
                                table_row.get("implementation_status", ""),
                                table_row.get("implementation_label", ""),
                            )
                        ),
                        md_br([md_code(value) for value in table_row.get("legacy_tables", [])]),
                        md_cell_en(table_row.get("note")),
                    ]
                )
                + " |"
            )
        status_json = json.dumps(status_map, ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
        diagram_sections.append(
            f"""### {md_cell_en(diagram.get("title"))}

{md_cell_en(diagram.get("description"))}

<div class="sql-landscape-er-card acid-er-card" markdown="1">

<div class="acid-er-status-list">{''.join(status_lines)}</div>
<script type="application/json" class="acid-er-status-data">{status_json}</script>

<div class="sql-landscape-table sql-landscape-er" markdown="1">

{md_mermaid_div(diagram.get("mermaid", "erDiagram"))}

</div>

</div>

| Target entity | Implementation status | Legacy evidence | Note |
|---|---|---|---|
{chr(10).join(table_rows)}
"""
        )
    return "\n".join(diagram_sections)


RECOMMENDED_ENTITY_SECTION_START = "<!-- legacy-sql-recommended-entities:start -->"
RECOMMENDED_ENTITY_SECTION_END = "<!-- legacy-sql-recommended-entities:end -->"

PRIORITY_EN_LABELS = {
    "hoch": "high",
    "mittel": "medium",
    "niedrig": "low",
}

RECOMMENDED_ENTITY_ACTIONS = {
    "exists": "Use existing C# table/model",
    "extend": "Extend existing C# table/model",
    "implement": "Create new DB table",
    "review": "Review DB model",
}


def requirement_features_from_path(path: Path) -> list[str]:
    if not path.exists():
        return []
    frontmatter = extract_frontmatter(read_text(path))
    features = re.findall(r"(?m)^feature:\s*(FEAT-\d+)\s*$", frontmatter)
    return sorted(dict.fromkeys(features))


def target_model_status(target_model: str) -> str:
    table = ACID_RECOMMENDED_TABLES.get(target_model)
    return acid_table_status(table) if table else "review"


def target_model_current_state(entry: dict) -> str:
    status = entry.get("implementation_status", "review")
    coverage = entry.get("coverage_status", "Unknown")
    if status == "implement":
        if coverage == "No direct table":
            return "No direct C# table was found for this legacy concept."
        return "C# has partial behavior or lookup coverage, but no normalized ACID table for this target yet."
    if status == "extend":
        return "A related C# table/model exists, but it does not fully cover this legacy concept yet."
    if status == "exists":
        return "The target C# table/model already exists; confirm field and behavior mapping instead of creating a duplicate."
    return "The target model needs manual architecture review before implementation."


def recommended_entity_followup_entries(db_recommendations: dict) -> dict[Path, list[dict]]:
    entries_by_page: dict[Path, list[dict]] = defaultdict(list)
    seen: set[tuple[Path, str, str]] = set()
    for row in db_recommendations.get("rows", []):
        target_model = row.get("target_model", "")
        legacy_table = row.get("legacy_table", "")
        if not target_model or target_model == "NoCSharpDomainTable" or not legacy_table:
            continue
        implementation_status = target_model_status(target_model)
        entry = {
            "target_model": target_model,
            "target_model_label": row.get("target_model_label") or target_model,
            "legacy_table": legacy_table,
            "implementation_status": implementation_status,
            "action": RECOMMENDED_ENTITY_ACTIONS.get(implementation_status, RECOMMENDED_ENTITY_ACTIONS["review"]),
            "priority": PRIORITY_EN_LABELS.get(row.get("priority", ""), row.get("priority", "medium")),
            "coverage_status": row.get("coverage_status", "Unknown"),
            "rationale": row.get("rationale") or row.get("coverage_rationale", ""),
            "recommendation": row.get("recommendation", ""),
            "target_fields": row.get("target_fields", []),
        }
        for ref in row.get("requirement_refs", []):
            ref_path_value = ref.get("path")
            if not ref_path_value:
                continue
            requirement_path = ROOT / ref_path_value
            for page_path in [requirement_path, *[FEATURES_ROOT / f"{feature_id}.md" for feature_id in requirement_features_from_path(requirement_path)]]:
                if not page_path.exists():
                    continue
                key = (page_path, target_model, legacy_table)
                if key in seen:
                    continue
                seen.add(key)
                entries_by_page[page_path].append(entry)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    for entries in entries_by_page.values():
        entries.sort(
            key=lambda item: (
                priority_order.get(item.get("priority", ""), 9),
                item.get("target_model", ""),
                item.get("legacy_table", ""),
            )
        )
    return entries_by_page


# Aggregate target models whose companion tables belong to the same create
# decision and are rendered along with the main schema.
RECOMMENDED_ENTITY_COMPANION_TABLES = {
    "BatchImports": ["BatchImportRows", "BatchImportErrors"],
    "PrintJobs": ["PrintJobOrders"],
}


def sql_type_label(column_type: str) -> str:
    parts = column_type.split("_")
    if len(parts) == 1:
        return column_type
    return f"{parts[0]}({','.join(parts[1:])})"


def target_field_reason(target_fields: list[dict], column_name: str) -> str:
    for field in target_fields:
        name = field.get("name", "")
        if name == column_name or name.endswith(f".{column_name}") or column_name in [
            part.strip() for part in name.replace("/", ",").split(",")
        ]:
            return field.get("reason", "")
    return ""


def acid_schema_lines(table_name: str, target_fields: list[dict], indent: str) -> list[str]:
    table = ACID_RECOMMENDED_TABLES.get(table_name)
    if not table:
        return []
    lines = [
        f"{indent}**Schema `{table_name}`**",
        "",
        f"{indent}| Column | Type | Key | Purpose |",
        f"{indent}|---|---|---|---|",
    ]
    for column_type, name, key in table["columns"]:
        key_label = key if key in {"PK", "FK", "UK"} else ""
        lines.append(
            f"{indent}| `{name}` | {sql_type_label(column_type)} | {key_label} | "
            f"{target_field_reason(target_fields, name)} |"
        )
    lines.append("")
    return lines


def recommended_entity_acceptance_criteria(entry: dict) -> list[str]:
    status = entry.get("implementation_status", "review")
    target_label = entry.get("target_model_label", "")
    target_fields = entry.get("target_fields", [])
    field_names = [field.get("name", "") for field in target_fields if field.get("name")]
    field_list = ", ".join(f"`{name}`" for name in field_names)
    if status == "implement":
        tables = [entry.get("target_model", "")] + RECOMMENDED_ENTITY_COMPANION_TABLES.get(
            entry.get("target_model", ""), []
        )
        table_list = ", ".join(f"`{name}`" for name in tables if name)
        return [
            f"- [ ] An EF Core migration creates {table_list} with the documented columns, primary keys, and foreign keys.",
            f"- [ ] An integration test connects to the database and persists and reads `{entry.get('target_model')}` rows end-to-end through the application persistence layer.",
            f"- [ ] Foreign-key and unique constraints of {table_list} are enforced by the database and covered by a failing-write test.",
        ]
    if status == "extend":
        fields_text = field_list or "the documented fields"
        return [
            f"- [ ] An EF Core migration adds {fields_text} to `{target_label}` without breaking existing rows.",
            f"- [ ] An integration test persists and reads back the new fields of `{target_label}` end-to-end.",
        ]
    if status == "exists":
        fields_text = f" for {field_list}" if field_list else ""
        return [
            f"- [ ] The existing `{target_label}` mapping covers this requirement{fields_text}; stored values are validated against it in an integration test.",
        ]
    return [
        f"- [ ] The database impact of `{target_label}` is decided and recorded before implementation starts.",
    ]


RECOMMENDED_ENTITY_HEADING_VERBS = {
    "implement": "Create table",
    "extend": "Extend",
    "exists": "Use existing",
    "review": "Review",
}


def recommended_entity_target_names(entry: dict) -> list[str]:
    if entry.get("implementation_status") == "implement":
        return [entry.get("target_model", "")] + RECOMMENDED_ENTITY_COMPANION_TABLES.get(
            entry.get("target_model", ""), []
        )
    return [entry.get("target_model_label", "")]


def recommended_entity_heading(entry: dict) -> tuple[str, str, str]:
    """Returns (heading verb, target text with backticks, action text) for one entry."""
    status = entry.get("implementation_status", "review")
    verb = RECOMMENDED_ENTITY_HEADING_VERBS.get(status, "Review")
    targets = recommended_entity_target_names(entry)
    target_text = ", ".join(f"`{name}`" for name in targets if name)
    action = entry.get("action", "")
    if status == "implement" and len(targets) > 1:
        verb = "Create tables"
        action = f"Create {len(targets)} new DB tables (one legacy table, normalized)"
    return verb, target_text, action


def render_recommended_entity_followup_block(entries: list[dict], subheading: str = "####") -> str:
    lines: list[str] = [
        RECOMMENDED_ENTITY_SECTION_START,
        "*Generated from the [SQL Landscape](../legacy-coverage-landscape.md#schema-recommendations) analysis."
        " These are not approved migrations by themselves; resolve them against the requirement scope and architecture.*",
        "",
        "| Action | Target | Priority | Legacy source |",
        "|---|---|---|---|",
    ]
    for entry in entries:
        verb, target_text, _ = recommended_entity_heading(entry)
        lines.append(
            f"| {verb} | {target_text} | {entry.get('priority')} | `{entry.get('legacy_table')}` |"
        )
    lines.append("")

    for entry in entries:
        status = entry.get("implementation_status", "review")
        target_fields = entry.get("target_fields", [])
        verb, target_text, action = recommended_entity_heading(entry)

        lines.append(f"{subheading} {verb} {target_text}")
        lines.append("")
        lines.append(
            f"*Action: {action} · Priority: {entry.get('priority')} · "
            f"Legacy source: `{entry.get('legacy_table')}` · "
            f"Details: [SQL Landscape](../legacy-coverage-landscape.md#schema-recommendations)*"
        )
        lines.append("")
        recommendation = mkdocs_en(entry.get("recommendation", ""))
        rationale = mkdocs_en(entry.get("rationale", ""))
        if recommendation:
            lines.append(f"**Decision:** {recommendation}")
            lines.append("")
        if rationale:
            lines.append(f"**Why:** {rationale}")
            lines.append("")
        if status == "implement":
            schema_tables = [entry.get("target_model", "")] + RECOMMENDED_ENTITY_COMPANION_TABLES.get(
                entry.get("target_model", ""), []
            )
            for table_name in schema_tables:
                lines.extend(acid_schema_lines(table_name, target_fields, ""))
        elif target_fields:
            label = "Fields to add" if status == "extend" else "Fields/attributes to verify"
            lines.append(f"**{label}**")
            lines.append("")
            lines.append("| Field | Type | Reason |")
            lines.append("|---|---|---|")
            for field in target_fields:
                lines.append(f"| `{field.get('name')}` | {field.get('type')} | {field.get('reason')} |")
            lines.append("")
        lines.append("**Database acceptance criteria**")
        lines.append("")
        lines.extend(recommended_entity_acceptance_criteria(entry))
        lines.append("")

    lines.append(RECOMMENDED_ENTITY_SECTION_END)
    return "\n".join(lines)


def replace_recommended_entity_block(text: str, block: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf"\n*{re.escape(RECOMMENDED_ENTITY_SECTION_START)}.*?{re.escape(RECOMMENDED_ENTITY_SECTION_END)}\n*",
        re.S,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return text, False
    start = matches[0].start()
    end = matches[-1].end()
    updated = text[:start].rstrip() + f"\n\n{block}\n\n" + text[end:].lstrip()
    return updated.rstrip() + "\n", True


def normalize_recommended_entity_heading(text: str) -> str:
    for level in ("###", "##"):
        for old_heading in ("Implementation Questions", "Database Implementation Questions"):
            text = text.replace(
                f"\n{level} {old_heading}\n\n{RECOMMENDED_ENTITY_SECTION_START}",
                f"\n{level} Database Implementation\n\n{RECOMMENDED_ENTITY_SECTION_START}",
            )
    return text


def insert_requirement_followup_block(text: str, block: str) -> str:
    replaced, found = replace_recommended_entity_block(text, block)
    if found:
        return normalize_recommended_entity_heading(replaced)
    insertion = f"\n\n### Database Implementation\n\n{block}\n"
    marker = "\n### Architecture"
    if marker in text:
        return text.replace(marker, insertion + marker, 1)
    return text.rstrip() + insertion


def insert_feature_followup_block(text: str, block: str) -> str:
    replaced, found = replace_recommended_entity_block(text, block)
    if found:
        return normalize_recommended_entity_heading(replaced)
    open_questions = re.search(r"(?m)^## Open questions[^\n]*$", text)
    if open_questions:
        next_heading = re.search(r"(?m)^##\s+", text[open_questions.end() :])
        insert_at = len(text) if not next_heading else open_questions.end() + next_heading.start()
        if next_heading:
            return text[:insert_at].rstrip() + f"\n\n{block}\n\n" + text[insert_at:].lstrip()
        return text[:insert_at].rstrip() + f"\n\n{block}\n"
    insertion = f"\n\n## Database Implementation\n\n{block}\n"
    marker = "\n## Out of scope"
    if marker in text:
        return text.replace(marker, insertion + marker, 1)
    return text.rstrip() + insertion


def remove_recommended_entity_block(text: str) -> str:
    pattern = re.compile(
        r"(?:(?:^|\n)#{2,3} Database Implementation(?: Questions)?\n+)?"
        + re.escape(RECOMMENDED_ENTITY_SECTION_START)
        + r".*?"
        + re.escape(RECOMMENDED_ENTITY_SECTION_END)
        + r"\n?",
        re.S,
    )
    updated = pattern.sub("\n", text)
    updated = re.sub(r"\n{3,}", "\n\n", updated)
    return updated.rstrip() + "\n"


def write_recommended_entity_followups(db_recommendations: dict) -> list[Path]:
    changed_paths = []
    entries_by_page = recommended_entity_followup_entries(db_recommendations)
    for page_path, entries in entries_by_page.items():
        original = read_text(page_path)
        if page_path.parent == FEATURES_ROOT:
            block = render_recommended_entity_followup_block(entries, subheading="###")
            updated = insert_feature_followup_block(original, block)
        else:
            block = render_recommended_entity_followup_block(entries, subheading="####")
            updated = insert_requirement_followup_block(original, block)
        if updated != original:
            page_path.write_text(updated, encoding="utf-8")
            changed_paths.append(page_path)
    # Remove stale blocks from pages that no longer have any recommended entity
    # (e.g. their only target model was dropped from the ACID model).
    for pages_root in (REQUIREMENTS_ROOT, FEATURES_ROOT):
        for page_path in sorted(pages_root.glob("*.md")):
            if page_path in entries_by_page:
                continue
            original = read_text(page_path)
            if RECOMMENDED_ENTITY_SECTION_START not in original:
                continue
            updated = remove_recommended_entity_block(original)
            if updated != original:
                page_path.write_text(updated, encoding="utf-8")
                changed_paths.append(page_path)
    return sorted(changed_paths)


def render_spec_coverage_mkdocs_page(
    overview: dict,
    db_recommendations: dict,
    recommended_acid_er: dict,
    generated_at: str,
) -> str:
    counts = overview.get("counts", {})
    definitions = overview.get("coverage_definitions", {})
    summary_rows = "\n".join(
        f"| {md_cell_en(status)} | {counts.get(status, 0)} | {md_cell_en(definitions.get(status, ''))} |"
        for status in ["Complete", "Partial", "Not found"]
    )

    coverage_cards = []
    for row in overview.get("rows", []):
        detail_rows = html_card_detail_rows(
            [
                ("Meaning in legacy SQL", html_cell_en(row.get("legacy_meaning"))),
                ("Coverage rationale", html_cell_en(row.get("coverage_reason"))),
                ("specsource", html_pdf_refs(row.get("pdf_refs", []))),
                ("Legacy SQL evidence", html_sql_refs(row.get("legacy_sql_evidence", []))),
                ("C# evidence", html_code_refs(row.get("csharp_evidence", []))),
                ("Relevant requirements", html_requirement_links(row.get("requirement_refs", []))),
            ]
        )
        coverage_cards.append(
            '<article class="sql-card">'
            f'<div class="sql-card-head"><strong>{html_cell_en(row.get("area"))}</strong>'
            f'{html_chip(mkdocs_en(row.get("coverage", "")))}'
            f'{html_chip("Confidence: " + mkdocs_en(row.get("confidence", "")))}'
            f'<span class="sql-landscape-muted">{html_cell_en(row.get("product"))}</span></div>'
            f'<p class="sql-card-lead"><strong>Gap / next question:</strong> {html_cell_en(row.get("gap"))}</p>'
            f'<details class="sql-card-details"><summary>Details &amp; evidence</summary><dl>{detail_rows}</dl></details>'
            "</article>"
        )

    gap_cards = []
    for row in overview.get("rows", []):
        if row.get("coverage") == "Complete":
            continue
        detail_rows = html_card_detail_rows(
            [
                ("C# evidence", html_code_refs(row.get("csharp_evidence", []))),
            ]
        )
        gap_cards.append(
            '<article class="sql-card">'
            f'<div class="sql-card-head"><strong>{html_cell_en(row.get("area"))}</strong>'
            f'{html_chip(mkdocs_en(row.get("coverage", "")))}'
            f'{html_chip("Confidence: " + mkdocs_en(row.get("confidence", "")))}</div>'
            f'<p class="sql-card-lead">{html_cell_en(row.get("gap"))}</p>'
            f'<details class="sql-card-details"><summary>Details &amp; evidence</summary><dl>{detail_rows}</dl></details>'
            "</article>"
        )

    no_migration_rows = []
    for row in db_recommendations.get("rows", []):
        if row.get("target_model") != "NoCSharpDomainTable":
            continue
        no_migration_rows.append(
            "| "
            + " | ".join(
                [
                    md_code(row.get("legacy_table")),
                    md_cell_en(row.get("decision")),
                    md_cell_en(row.get("rationale")),
                    md_cell_en(row.get("recommendation")),
                ]
            )
            + " |"
        )

    recommendation_cards = []
    for row in db_recommendations.get("rows", []):
        if row.get("target_model") == "NoCSharpDomainTable":
            continue
        target_field_lines = "".join(
            f"<li><code>{html_cell(field.get('name'))}</code>: {html_cell(field.get('type'))} &mdash; "
            f"{html_cell(field.get('reason'))}</li>"
            for field in row.get("target_fields", [])
        )
        detail_rows = html_card_detail_rows(
            [
                ("Recommendation", html_cell_en(row.get("recommendation"))),
                (
                    "Field changes",
                    f'<ul class="sql-card-fields">{target_field_lines}</ul>' if target_field_lines else "",
                ),
                (
                    "Rationale",
                    html_cell(
                        f"{mkdocs_en(row.get('rationale', ''))} {mkdocs_en(row.get('coverage_rationale', ''))}".strip()
                    ),
                ),
                (
                    "Current C# surface",
                    html_evidence_list(
                        html_cell_en(value)
                        for value in [*(row.get("current_csharp_surface") or []), *(row.get("concepts") or [])]
                    ),
                ),
                ("Legacy SQL evidence", html_code_refs(row.get("legacy_evidence", []), limit=3)),
                ("C# evidence", html_code_refs(row.get("csharp_evidence", []))),
                ("Relevant requirements", html_requirement_links(row.get("requirement_refs", []))),
            ]
        )
        target_label = row.get("target_model_label") or row.get("target_model") or ""
        recommendation_cards.append(
            '<article class="sql-card">'
            f'<div class="sql-card-head"><code>{html_cell(row.get("legacy_table"))}</code>'
            f'<span class="sql-card-arrow">&#8594;</span><strong>{html_cell(target_label)}</strong>'
            f'{html_chip(mkdocs_en(row.get("priority", "")))}'
            f'{html_chip(mkdocs_en(row.get("coverage_status", "")))}</div>'
            f'<p class="sql-card-lead">{html_cell_en(row.get("decision"))}</p>'
            f'<details class="sql-card-details"><summary>Details &amp; evidence</summary><dl>{detail_rows}</dl></details>'
            "</article>"
        )

    return f"""---
title: "SQL Landscape"
type: legacy-coverage-landscape
change_history:
  - "**2026-06-10**: Added the first generated MkDocs view of spec-to-legacy-SQL-to-C# coverage."
  - "**2026-06-10**: Renamed the page to SQL Landscape, widened tables, and added relevant requirements."
  - "**2026-06-10**: Widened the coverage matrix and reduced the requirements column to REQ links."
  - "**2026-06-10**: Changed the requirements column to `REQ link -- title`."
  - "**2026-06-10**: Changed the requirements column to one requirement per line."
  - "**2026-06-10**: Doubled the width of the open gaps table."
  - "**2026-06-10**: Rendered the open gaps table as a wide viewport table outside the normal text flow."
  - "**2026-06-11**: Added database table recommendations for legacy tables with partial or missing C# coverage."
  - "**2026-06-11**: Added recommended ACID ER diagrams and anchored target entities as implementation questions in affected requirements/features."
  - "**2026-06-12**: Re-analyzed against spec V1.9, userflow/{PROJECT-NAME}-summary screens, legacy SQL, and the C# backend: switched spec source to V1.9, extended Orders/PostOfficeBoxes/BillingRecords/PrintJobs/AuditLog target columns, added the OrderDocuments table (Spec chapter 17 FMS metadata), removed the rejected OrderRecipients/OrderChangeReasons/PostOfficeBoxStatuses/BillingStatuses tables, and raised the partner exception-table priority."
  - "**2026-06-12**: Removed the unconnected NumberRanges table from the target model (form numbers now via database sequences per product code and year) and made the Coverage Matrix and Recommendation Table readable with collapsible evidence columns and narrower layouts."
  - "**2026-06-12**: Replaced the wide Coverage Matrix and Recommendation Table with one card per concept/legacy table: status chips and the key statement stay visible, all evidence sits in a collapsible details section at normal page width."
  - "**2026-06-12**: Converted the Open Gaps table to the same card layout."
  - "**2026-06-12**: Added a 'Field changes' section to every Recommendation card listing the concrete fields to add on the target model with type and reason."
  - "**2026-06-12**: Moved the no-port legacy tables out of the Recommendation cards into the new section 'Legacy Tables Without Migration' with strengthened rationales."
  - "**2026-06-12**: Restructured the requirement-page database follow-up blocks: action bullets encode create/extend/use with the affected fields, and a collapsible 'DB details' section carries full schemas (columns, types, PK/FK), fields to add, and the detailed rationale in English."
  - "**2026-06-12**: Renamed the requirement section to 'Database Implementation', removed the note wrapper, expanded the details as 'Proposed schema changes', and added generated database acceptance criteria (migration, end-to-end persistence, constraint checks) per affected requirement."
  - "**2026-06-12**: Regrouped the Database Implementation blocks per target: a summary table plus one subsection per target (Decision, Why, fields/schema table, acceptance criteria) instead of information split across three lists."
  - "**2026-06-12**: Normalized aggregates now name all created tables in headings and summaries (e.g. 'Create tables BatchImports, BatchImportRows, BatchImportErrors'), and the TBatchOrder/Import_LabelPrint decisions explain why one legacy table becomes several normalized tables."
---

# SQL Landscape

<style>
  .sql-landscape-table {{
    overflow-x: auto;
    margin: 1rem 0 1.5rem;
    padding-bottom: .5rem;
  }}
  .sql-landscape-cards {{
    display: grid;
    gap: .75rem;
    margin: 1rem 0 1.5rem;
  }}
  .sql-card {{
    border: 1px solid #d6dde8;
    border-radius: 8px;
    background: #fff;
    padding: .7rem .9rem;
  }}
  .sql-card-head {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: .45rem;
    margin-bottom: .3rem;
  }}
  .sql-card-head strong {{
    font-size: .92rem;
  }}
  .sql-card-arrow {{
    color: #94a3b8;
    font-weight: 700;
  }}
  .sql-chip {{
    display: inline-flex;
    border-radius: 999px;
    border: 1px solid #d6dde8;
    padding: .12rem .55rem;
    font-size: .68rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
    background: #f8fafc;
    color: #475569;
  }}
  .sql-chip-full {{ background: #ecfdf3; border-color: #059669; color: #065f46; }}
  .sql-chip-partial {{ background: #fffbeb; border-color: #d97706; color: #92400e; }}
  .sql-chip-none, .sql-chip-high {{ background: #fef2f2; border-color: #dc2626; color: #991b1b; }}
  .sql-chip-medium {{ background: #fffbeb; border-color: #d97706; color: #92400e; }}
  .sql-chip-low {{ background: #f8fafc; border-color: #cbd5e1; color: #64748b; }}
  .sql-card-lead {{
    margin: .2rem 0 .35rem;
    font-size: .85rem;
    line-height: 1.5;
  }}
  .sql-card-details summary {{
    cursor: pointer;
    color: #2563eb;
    font-weight: 600;
    font-size: .8rem;
  }}
  .sql-card-details dl {{
    display: grid;
    grid-template-columns: 11rem minmax(0, 1fr);
    gap: .35rem .9rem;
    margin: .55rem 0 0;
    font-size: .8rem;
    line-height: 1.5;
  }}
  .sql-card-details dt {{
    font-weight: 700;
    color: #475569;
  }}
  .sql-card-details dd {{
    margin: 0;
    overflow-wrap: anywhere;
  }}
  .sql-card-fields {{
    margin: 0;
    padding-left: 1.1rem;
  }}
  .sql-card-fields li {{
    margin: 0 0 .25rem;
  }}
  .sql-landscape-er {{
    width: 100%;
    max-width: 100%;
    max-height: 82vh;
    overflow: auto;
    border: 1px solid #d6dde8;
    border-radius: 8px;
    background: #fff;
    padding: .75rem;
    margin: .75rem 0 0;
    position: relative;
    z-index: 1;
  }}
  .sql-landscape-er .mermaid {{
    display: block;
    min-width: 1500px;
    width: max-content;
    max-width: none;
    margin: 0;
    padding: 0;
    background: transparent;
    color: #17202a;
    font-size: .78rem;
    line-height: 1.35;
    white-space: pre;
    position: static !important;
  }}
  .sql-landscape-er .mermaid[data-processed="true"] {{
    white-space: normal;
  }}
  .sql-landscape-er svg {{
    display: block;
    min-width: 1500px;
    max-width: none !important;
    height: auto;
    background: #fff;
    position: static !important;
    overflow: visible;
  }}
  .sql-landscape-er-card {{
    width: calc(100vw - 2rem);
    max-width: none;
    margin-left: calc(50% - 50vw + 1rem);
    margin-right: calc(50% - 50vw + 1rem);
    border: 1px solid #d6dde8;
    border-radius: 8px;
    padding: 1rem;
    margin-top: 1rem;
    margin-bottom: 1.5rem;
    background: #fff;
    overflow: hidden;
    clear: both;
  }}
  .acid-er-status-list {{
    display: grid;
    gap: .35rem;
    margin: 0 0 .6rem;
    font-size: .72rem;
    position: relative;
    z-index: 2;
    background: #fff;
  }}
  .acid-er-status-list div {{
    display: flex;
    flex-wrap: wrap;
    gap: .4rem;
    align-items: center;
  }}
  .acid-status {{
    display: inline-flex;
    width: max-content;
    border-radius: 999px;
    border: 1px solid #d6dde8;
    padding: .18rem .5rem;
    font-size: .68rem;
    font-weight: 700;
    line-height: 1.2;
    white-space: nowrap;
  }}
  .acid-status-exists {{ background: #eff6ff; border-color: #2563eb; color: #1e3a8a; }}
  .acid-status-extend {{ background: #ecfdf3; border-color: #059669; color: #065f46; }}
  .acid-status-implement {{ background: #fff7ed; border-color: #ea580c; color: #9a3412; }}
  .sql-landscape-muted {{
    color: #64748b;
  }}
  .sql-landscape-table th,
  .sql-landscape-table td {{
    vertical-align: top;
  }}
</style>

!!! warning "Evidence status"
    This page is a derived analysis from the legacy SQL report, not a new business source of truth. The official specification remains authoritative; legacy SQL is supporting database evidence, and C# matches show only statically found implementation surfaces.

Generated at: `{md_cell(generated_at)}`<br>
Analysis source: `{md_cell(rel(DATA_JSON))}`<br>
Primary specsource: `{md_cell(overview.get("source_pdf", rel(PDF_SOURCES[0])))}`

## Summary

| Coverage status | Count | Meaning |
|---|---:|---|
{summary_rows}

## Coverage Matrix

One card per specconcept. The visible part shows the coverage status and the open gap; meaning,
rationale, specsource, Legacy SQL evidence, C# evidence, and relevant requirements are inside
*Details &amp; evidence*.

<div class="sql-landscape-cards sql-landscape-matrix">
{chr(10).join(coverage_cards)}
</div>

## Open Gaps

One card per specconcept whose C# coverage is not yet Full. The visible sentence is the gap /
next question; the supporting C# evidence sits inside *Details &amp; evidence*.

<div class="sql-landscape-cards sql-landscape-gaps">
{chr(10).join(gap_cards)}
</div>

<a id="schema-recommendations"></a>

## Database Table Recommendations

This table only considers legacy tables with the C# coverage statuses `Partial` and `No direct table`. A recommendation does not automatically mean that the legacy table should be copied one-to-one. Each row contains exactly one ACID target decision and one concrete target model; alternative target variants are intentionally not listed here.

<a id="recommended-acid-er-diagrams"></a>

## Recommended ACID ER Diagrams

The first diagram is the complete proposed target model and contains each table once. The focused diagrams below intentionally repeat shared anchor tables such as Orders, Lookups, and AuditLog so each business area remains readable. These diagrams are implementation decisions for this analysis, not EF migrations to apply automatically. The status under each diagram shows which tables already exist in C#, which existing tables should be extended, and which tables should be implemented.

{render_spec_mkdocs_er_diagrams(recommended_acid_er)}

## Recommendation Table

One card per legacy table, headed `legacy table` &#8594; **proposed target model** with priority and
coverage chips. The visible sentence is the target decision; the full recommendation, rationale,
field changes, current C# surface, Legacy SQL evidence, C# evidence, and relevant requirements are
inside *Details &amp; evidence*. Legacy tables that deliberately get no migration are listed in
[Legacy Tables Without Migration](#legacy-tables-without-migration) instead.

<div class="sql-landscape-cards sql-landscape-recommendations">
{chr(10).join(recommendation_cards)}
</div>

<a id="legacy-tables-without-migration"></a>

## Legacy Tables Without Migration

These legacy tables are deliberately **not** migrated into the C# domain model. The decision is
final for this analysis unless a confirmed requirement changes it; the rationale explains what
covers each concern instead.

| Legacy table | Decision | Rationale | What covers it instead |
|---|---|---|---|
{chr(10).join(no_migration_rows)}

## Reading Rules

- **Full** only means that a clear C# surface was found for the specconcept. It does not prove full behavior parity.
- **Partial** means the concept is visible in C#, but fields, workflows, reports, integrations, or historical behavior remain open.
- **No direct evidence** means the static scan found no robust C# implementation evidence.
- Legacy SQL evidence is supporting evidence. It does not replace the specor confirmed requirements.
"""


def render_legacy_csharp_table_coverage(csharp_sql_model: dict) -> str:
    rows = []
    coverage_rows = csharp_sql_model.get("legacy_table_coverage", [])
    counts = Counter(row.get("status", "Unknown") for row in coverage_rows)
    summary = " ".join(
        f'<span><strong>{html_escape(count)}</strong> {html_escape(status)}</span>'
        for status, count in sorted(counts.items())
    )
    for row in coverage_rows:
        search = " ".join(
            [
                row.get("legacy_table", ""),
                row.get("status", ""),
                row.get("rationale", ""),
                *row.get("csharp_tables", []),
                *row.get("concepts", []),
                *row.get("legacy_columns", []),
            ]
        )
        csharp_surface = chip_list(row.get("csharp_tables", []), limit=10, empty="No active C# EF table found")
        if row.get("csharp_columns"):
            csharp_surface += (
                '<div class="muted coverage-columns">C# columns: '
                f'{html_escape(", ".join(row.get("csharp_columns", [])[:12]))}'
                f'{" ..." if len(row.get("csharp_columns", [])) > 12 else ""}</div>'
            )
        rows.append(
            [
                (
                    f'<div class="search-item" data-search="{html_escape(search)}">'
                    f'<strong>{html_escape(row.get("legacy_table", ""))}</strong><br>'
                    f'<span class="muted">{html_escape(row.get("legacy_path", ""))}</span>'
                    f'</div>'
                ),
                coverage_status_badge(row.get("status", "Unknown"), row.get("confidence", "unknown")),
                csharp_surface,
                chip_list(row.get("concepts", []), limit=8, empty="No mapped concept found"),
                html_escape(row.get("rationale", "")),
                chip_list(row.get("legacy_columns", [])[:10], limit=10, empty="No legacy columns extracted"),
                file_ref_links(row.get("legacy_evidence", []), limit=2),
                file_ref_links(row.get("csharp_evidence", []), limit=4, empty="No C# source evidence"),
            ]
        )
    return (
        f'<div class="coverage-summary">{summary}</div>'
        + table(
            [
                "Legacy SQL table",
                "In C#?",
                "C# EF/domain table surface",
                "Concept / field link",
                "Rationale and boundary",
                "Legacy columns",
                "Legacy source",
                "C# source",
            ],
            rows,
            classes="coverage-table",
        )
    )


def render_csharp_sql_model_section(csharp_sql_model: dict) -> str:
    migration_counts = csharp_sql_model.get("migration_counts", {})
    raw_sql_files = csharp_sql_model.get("raw_sql_files", [])
    ps_sql_scripts = csharp_sql_model.get("powershell_sql_scripts", [])
    csharp_er_diagrams_html = render_csharp_domain_er_diagrams(csharp_sql_model)
    legacy_table_coverage_table = render_legacy_csharp_table_coverage(csharp_sql_model)
    overview_rows = []
    for row in csharp_sql_model.get("summary", []):
        search = " ".join([row["topic"], row["answer"]])
        overview_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["topic"])}</strong></div>',
                html_escape(row["answer"]),
                file_ref_links(row.get("evidence", []), limit=5),
            ]
        )
    overview_table = table(["Question", "Answer", "C# evidence"], overview_rows)

    schema_rows = []
    for row in csharp_sql_model.get("schemas", []):
        search = " ".join([row["schema"], row["role"], *row.get("tables", [])])
        schema_rows.append(
            [
                f'<span class="search-item code-pill" data-search="{html_escape(search)}">{html_escape(row["schema"])}</span>',
                html_escape(row["role"]),
                html_escape(", ".join(row.get("tables", []))),
                file_ref_links(row.get("evidence", []), limit=3),
            ]
        )
    schema_table = table(["Schema", "Role", "Tables discovered from migrations", "Evidence"], schema_rows)

    domain_rows = []
    for row in csharp_sql_model.get("domain_model", []):
        search = " ".join([row["model"], row["role"], *row.get("mapped_tables", [])])
        domain_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["model"])}</strong></div>',
                html_escape(row["role"]),
                html_escape(", ".join(row.get("mapped_tables", []))),
                file_ref_links(row.get("evidence", []), limit=5),
            ]
        )
    domain_table = table(["Domain / persistence model", "What it represents", "Mapped table surface", "Evidence"], domain_rows)

    config_rows = []
    for row in csharp_sql_model.get("configuration_rows", []):
        search = " ".join([row["entity"], row["configuration"], *row.get("tables", []), *row.get("patterns", [])])
        config_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["entity"])}</strong><br><span class="muted">{html_escape(row["configuration"])}</span></div>',
                html_escape(", ".join(row.get("tables", [])) or "Base/abstract mapping; concrete table in derived configuration"),
                html_escape(", ".join(row.get("patterns", [])) or "No mapping pattern extracted"),
                file_ref_links(row.get("evidence", []), limit=2),
            ]
        )
    config_table = table(["EF configuration", "Table mapping", "Persistence patterns", "Evidence"], config_rows)

    repository_rows = []
    for row in csharp_sql_model.get("repository_rows", []):
        search = f'{row["interface"]} {row["implementation"]}'
        repository_rows.append(
            [
                f'<span class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["interface"])}</strong></span>',
                html_escape(row["implementation"]),
                file_ref_links(row.get("evidence", []), limit=4),
            ]
        )
    repository_table = table(["Application port", "Infrastructure adapter", "Evidence"], repository_rows)

    diagram_source = "\n".join(
        [
            "flowchart LR",
            '  API["API endpoints"] --> App["MediatR application handlers"]',
            '  App --> Ports["Repository interfaces"]',
            '  Ports --> Repos["Infrastructure repositories"]',
            '  Repos --> DirectivesDb["DirectivesDbContext"]',
            '  Domain["DDD domain aggregates"] -.-> DirectivesDb',
            '  Config["EF entity configurations"] -.-> DirectivesDb',
            '  Migrations["DirectivesDb migrations"] -.-> Sql["SQL Server {PROJECT-NAME}Db"]',
            '  DirectivesDb --> Sql',
            '  Sql --> Tables["Orders, Directives, Addresses, Lookups, auth Roles"]',
            '  Worker["Worker host"] --> QueueDb["QueueDbContext"]',
            '  QueueDb --> Work["work Lock, Queue, ScheduledTask"]',
        ]
    )

    raw_sql_note = (
        f"No standalone .sql files were found under csharp/. EF migration files are the active schema source; "
        f"{len(ps_sql_scripts)} PowerShell scripts contain operational SQL snippets."
    )
    if raw_sql_files:
        raw_sql_note = f"Standalone .sql files found under csharp/: {', '.join(raw_sql_files)}"

    section = f"""
    <section id="csharp-sql-model">
      <h2>Existing C# SQL And Persistence Model</h2>
      <div class="explain search-item" data-search="csharp sql persistence db schema domain model ef core migrations">
        <strong>Short answer:</strong> the C# folder has an active SQL Server persistence model, but it is expressed through EF Core DbContext, entity configurations, migrations, repositories, and DDD domain aggregates. It is not a direct clone of the imported legacy SQL database project. DirectivesDb has {html_escape(migration_counts.get("DirectivesDb", 0))} migration files; QueueDb has {html_escape(migration_counts.get("QueueDb", 0))} migration file. {html_escape(raw_sql_note)}
      </div>
      {render_mermaid_block(diagram_source, "C# SQL and persistence model flow")}
      <h3>C# Persistence Inventory</h3>
      {overview_table}
      <h3>EF-Managed Database Schemas</h3>
      {schema_table}
      <h3>C# Domain Model ER Diagrams</h3>
      <p class="muted">These Mermaid ER diagrams are generated from C# EF migrations plus EF/domain configuration evidence. Solid relationships are declared migration foreign keys; dotted relationships are domain/configuration links that are visible in C# but not enforced as database FKs in the current migrations.</p>
      {csharp_er_diagrams_html}
      <h3>Legacy SQL Tables Already Represented In C#</h3>
      <p class="muted">This table compares every non-generated legacy SQL table with the active C# EF/domain model. <strong>Yes</strong> means a clear active C# table/domain equivalent exists; <strong>Partial</strong> means the concept appears in C# but not as a one-to-one table clone; <strong>No direct table</strong> means no active EF table equivalent was found by the static scan. Legacy SQL remains supporting evidence, not the active C# schema.</p>
      {legacy_table_coverage_table}
      <h3>Domain Model And Table Surface</h3>
      {domain_table}
      <h3>EF Configuration Files</h3>
      <p class="muted">These configuration classes are the source-level mapping between the DDD domain model and SQL Server tables. They define table names, keys, relationships, owned value objects, conversions, and JSON-backed columns.</p>
      {config_table}
      <h3>Repository Boundary</h3>
      {repository_table}
    </section>
    """
    return "\n".join(line.rstrip() for line in section.strip("\n").splitlines())


def render_report(data: dict) -> str:
    files: list[SqlFile] = data["files"]
    pdfs: list[dict] = data["pdfs"]
    category_counts = count_by_category(files)
    schema_counts = count_by_schema(files)
    sqlproj_count = sum(1 for f in files if f.in_sqlproj)
    generated_count = sum(1 for f in files if f.generated)
    table_files = [f for f in files if f.category == "Table"]
    external_refs = Counter(ref for f in files for ref in f.external_refs)
    risk_counts = Counter(flag for f in files for flag in f.risk_flags)
    mutation_files = [f for f in files if f.mutations]
    central = dependency_rank(files)
    topic_comparison = data["topic_comparison"]
    semantic_map = data["semantic_map"]
    print_fields = data["print_fields"]
    csharp_backend = data["csharp_backend"]
    csharp_sql_model = data["csharp_sql_model"]
    product_sql = data["product_sql"]
    function_logic = data["function_logic"]
    diagram_sources = data["diagram_sources"]
    legacy_code = data["legacy_code"]
    spec_coverage_overview = data["spec_coverage_overview"]
    db_table_recommendations = data["db_table_recommendations"]
    domain_model_recommendation_er = data["domain_model_recommendation_er"]
    recommended_acid_er = data["recommended_acid_er_diagrams"]

    summary_cards = [
        ("SQL files", len(files), f"All .sql files under legacy-sql/{LEGACY_DB_NAME}"),
        ("In SQL project", sqlproj_count, "Build Include entries in the .sqlproj file"),
        ("Generated SQL", generated_count, "obj/Debug generated scripts kept as legacy snapshot artifacts"),
        ("Tables", sum(1 for f in files if f.category == "Table"), "Table files, including embedded triggers/indexes"),
        ("Stored procedures", sum(1 for f in files if f.category == "Stored procedure"), "Primary candidates for stored business behavior"),
        ("Functions", sum(1 for f in files if f.category == "Function"), "Search, report, address, print helpers"),
        ("Official PDFs", len(pdfs), "Client source documents compared"),
        ("Legacy code files", legacy_code.get("files_scanned", 0), "Legacy app files scanned for SQL call sites"),
        ("CF SQL objects", legacy_code.get("distinct_sql_objects_hit", 0), "Imported SQL objects referenced by static Legacy code scan"),
        ("External refs", len(external_refs), "Distinct external DB/schema references"),
    ]

    cards_html = "\n".join(
        f'<div class="metric search-item" data-search="{html_escape(label)} {html_escape(note)}">'
        f'<div class="metric-value">{value}</div><div class="metric-label">{html_escape(label)}</div>'
        f'<p>{html_escape(note)}</p></div>'
        for label, value, note in summary_cards
    )

    plan_steps = [
        ("1. Freeze provenance", "Record submodule/repo URL, commit, branch, snapshot date, and owner. Do not edit imported SQL."),
        ("2. Inventory every file", "Classify all SQL by schema/type, separate SQL project build files from generated obj/Debug artifacts."),
        ("3. Build schema model", "Extract tables, columns, keys, indexes, triggers, synonyms, and external database references."),
        ("4. Review stored behavior", "Prioritize procedures/functions that mutate state, parse XML, call the external search API, write logs, or generate print output."),
        ("5. Compare to official PDFs", "Use the client spec PDFs as primary source documents; SQL is supporting evidence."),
        ("6. Derive diagrams", "Maintain core persistence flow, print interface, schema inventory, Legacy code call-site, and dependency diagrams."),
        ("7. Record risks and questions", "Turn ambiguous SQL behavior into client questions, not inferred requirements."),
        ("8. Update requirements only after confirmation", "Confirmed observations belong under docs/requirements; generated analysis stays in reports/evaluations."),
    ]
    plan_html = "\n".join(
        f'<li class="search-item" data-search="{html_escape(title)} {html_escape(body)}"><strong>{html_escape(title)}</strong><br>{html_escape(body)}</li>'
        for title, body in plan_steps
    )

    source_rows = []
    for pdf in pdfs:
        source_rows.append(
            [
                html_escape(pdf["name"]),
                html_escape(pdf["path"]),
                str(pdf["pages"]),
                f'{pdf["chars"]:,}',
                str(len(pdf["headings"])),
            ]
        )
    sql_commit = data["sql_git"].get("commit") or "unknown"
    source_rows.append(
        [
            f"{LEGACY_DB_NAME} SQL repository",
            html_escape(rel(SQL_ROOT)),
            "-",
            "-",
            f"git commit {html_escape(sql_commit[:12])}",
        ]
    )
    source_rows.append(
        [
            "Legacy code legacy application",
            html_escape(legacy_code.get("root", rel(LEGACY_CODE_ROOT))),
            "-",
            "-",
            (
                f"datasource {html_escape(legacy_code.get('datasource') or 'unknown')}; "
                f"{legacy_code.get('files_with_sql_hits', 0)} files with imported SQL hits"
            ),
        ]
    )
    sources_table = table(["Source", "Path", "Pages", "Extracted chars", "Notes"], source_rows)

    diagram_source_rows = []
    for row in diagram_sources:
        search = " ".join([row["diagram"], row["answer"], row["source_basis"]])
        diagram_source_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["diagram"])}</strong><br>{html_escape(row["answer"])}</div>',
                html_escape(row["source_basis"]),
                pdf_ref_links(row["pdf_refs"]),
                file_ref_links(row["file_refs"], limit=12, empty="No file evidence"),
            ]
        )
    diagram_sources_table = table(["Diagram", "Source basis", "PDF sources", "File / SQL sources"], diagram_source_rows)

    cf_summary_rows = [
        ["Datasource", html_escape(legacy_code.get("datasource") or "unknown"), file_ref_links(legacy_code.get("datasource_refs", []), limit=4)],
        ["Files scanned", str(legacy_code.get("files_scanned", 0)), html_escape(legacy_code.get("root", rel(LEGACY_CODE_ROOT)))],
        ["Files with imported SQL hits", str(legacy_code.get("files_with_sql_hits", 0)), f"Static references to objects present in legacy-sql/{LEGACY_DB_NAME}"],
        ["Distinct imported SQL objects hit", str(legacy_code.get("distinct_sql_objects_hit", 0)), "Object names matched against imported SQL definitions"],
        ["Stored procedure calls matched", str(legacy_code.get("matched_stored_proc_calls", 0)), "cfstoredproc procedure names found in imported SQL snapshot"],
        ["Stored procedure calls unmatched", str(legacy_code.get("unmatched_stored_proc_calls", 0)), "Likely external or older-schema dependencies; review manually"],
    ]
    legacy_code_summary_table = table(["Metric", "Value", "Evidence / note"], cf_summary_rows)

    cf_proc_rows = []
    for call in legacy_code.get("stored_proc_calls", []):
        status = "matched" if call.get("matched") else "unmatched"
        cf_proc_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(call["procedure"] + " " + status)}"><strong>{html_escape(call["procedure"])}</strong><br><span class="muted">{html_escape(status)}</span></div>',
                html_escape(call.get("matched_object") or "No imported SQL match"),
                html_escape(call.get("sql_file") or "External / not in imported SQL snapshot"),
                f'<span class="code-ref">{html_escape(call["file"])}:{html_escape(call["line"])}</span>',
            ]
        )
    legacy_code_proc_table = table(["Legacy code procedure call", "Imported SQL object", "SQL source", "CF source"], cf_proc_rows)
    legacy_code_overview_diagram = render_legacy_code_overview_diagram(legacy_code)
    legacy_code_procedure_diagram = render_legacy_code_procedure_diagram(legacy_code)
    legacy_code_domain_diagram = render_legacy_code_domain_diagram(legacy_code)

    cf_object_rows = []
    for row in legacy_code.get("top_objects", [])[:20]:
        cf_object_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(row["object"] + " " + row["kind"])}"><strong>{html_escape(row["object"])}</strong><br><span class="muted">{html_escape(row["kind"])}</span></div>',
                str(row.get("hits", 0)),
                str(row.get("qualified_hits", 0)),
                html_escape(row.get("sql_file", "")),
                file_ref_links(row.get("refs", []), limit=3),
            ]
        )
    legacy_code_object_table = table(["Imported SQL object", "CF hits", "Qualified hits", "SQL source", "Example CF refs"], cf_object_rows)

    cf_file_rows = []
    for row in legacy_code.get("top_files", [])[:20]:
        cf_file_rows.append(
            [
                f'<span class="code-ref">{html_escape(row["file"])}</span>',
                str(row.get("object_count", 0)),
                html_escape(", ".join(row.get("objects", [])[:10])),
            ]
        )
    legacy_code_file_table = table(["Legacy code file", "Imported SQL objects", "Examples"], cf_file_rows)

    semantic_rows = []
    for item in semantic_map:
        search = " ".join(item["doc_terms"] + item["sql_terms"] + [item["official_topic"], item["status"], item["action"]])
        semantic_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(item["official_topic"])}</strong><br><span class="muted">Doc hits: {item["doc_hits"]}; SQL files: {item["evidence_count"]}</span></div>',
                pdf_ref_links(item["pdf_refs"]),
                html_escape(", ".join(item["sql_terms"])),
                html_escape(item["status"]),
                evidence_links(item["evidence"]),
                html_escape(item["action"]),
            ]
        )
    semantic_table = table(["Official topic", "PDF source pages", "SQL terms", "Status", "SQL evidence", "Action"], semantic_rows)

    topic_rows = []
    for row in topic_comparison:
        search = " ".join(row["terms"] + [row["topic"], row["review"]])
        topic_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["topic"])}</strong><br><span class="muted">{html_escape(", ".join(row["terms"]))}</span></div>',
                str(row["doc_count"]),
                pdf_ref_links(row["pdf_refs"]),
                str(row["sql_count"]),
                evidence_links(row["evidence"]),
                html_escape(row["review"]),
            ]
        )
    topic_table = table(["Topic", "PDF hits", "PDF source pages", "SQL hits", "SQL evidence", "Review focus"], topic_rows)

    print_rows = []
    for field_row in print_fields:
        search = " ".join([field_row["code"], field_row["field"], field_row["status"]])
        print_rows.append(
            [
                f'<span class="search-item code-pill" data-search="{html_escape(search)}">{html_escape(field_row["code"])}</span>',
                html_escape(field_row["field"]),
                pdf_ref_links(field_row["pdf_refs"], limit=2),
                html_escape(field_row["status"]),
                evidence_links(field_row["evidence"]),
            ]
        )
    print_table = table(["Field", "Official name", "PDF source pages", "Automated SQL mapping", "SQL evidence"], print_rows)

    product_rows = []
    for row in product_sql:
        product_label = (
            f'<div class="search-item" data-search="{html_escape(row["code"] + " " + row["name"] + " " + row["pdf_source"])}">'
            f'<strong>{html_escape(row["code"])} - {html_escape(row["name"])}</strong>'
            f'<br><span class="muted">Source: {html_escape(row["pdf_source"])}</span>'
            f'{pdf_ref_links(row["pdf_refs"], limit=2)}</div>'
        )
        if row["evidence"]:
            sql_items = "<br>".join(
                f'<span class="code-ref">{html_escape(item["object"])} ({html_escape(item["category"])})</span> '
                f'<span class="muted">{html_escape(item["file"])}:{html_escape(item["line"])}</span>'
                for item in row["evidence"]
            )
            if row["evidence_count"] > len(row["evidence"]):
                sql_items += f'<br><span class="muted">+{row["evidence_count"] - len(row["evidence"])} more matching SQL files</span>'
        else:
            sql_items = '<span class="muted">No direct SQL file/entity match found by automated scan</span>'
        product_rows.append([product_label, sql_items])
    product_table = table(["Product", "Relevant SQL files / entities"], product_rows)

    csharp_rows = []
    for row in csharp_backend:
        search = " ".join([row["capability"], row["expected"], row["status"], *row["terms"]])
        csharp_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["capability"])}</strong><br><span class="muted">{html_escape(row["expected"])}</span></div>',
                pdf_ref_links(row["pdf_refs"]),
                html_escape(row["status"]),
                html_escape(", ".join(row["terms"])),
                csharp_links(row["evidence"]),
            ]
        )
    csharp_table = table(["Capability / behavior", "PDF/source refs", "C# status", "Scan terms", "C# backend evidence"], csharp_rows)

    function_group_rows = []
    for row in function_logic["groups"]:
        search = " ".join([row["name"], row["logic"], row["review"], *row["functions"]])
        function_group_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["name"])}</strong><br><span class="muted">{row["count"]} function files</span></div>',
                html_escape(row["logic"]),
                pdf_ref_links(row["pdf_refs"]),
                file_ref_links(row["evidence"], limit=10, empty="No SQL function evidence"),
                html_escape(row["review"]),
            ]
        )
    function_groups_table = table(
        ["Function kind", "Business logic", "PDF sources", "SQL function sources", "Review focus"],
        function_group_rows,
    )

    function_detail_rows = []
    for row in function_logic["details"]:
        deps = [*row["dependencies"], *row["external_refs"]]
        dep_text = ", ".join(dict.fromkeys(deps[:10])) or "-"
        comment = f'<br><span class="muted">SQL comment: {html_escape(row["comment"])}</span>' if row["comment"] else ""
        search = " ".join([row["object"], row["file"], row["group"], row["return_shape"], row["business_logic"], dep_text])
        function_detail_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(row["object"])}</strong><br><span class="muted">{html_escape(row["file"])}</span></div>',
                html_escape(row["group"]),
                html_escape(row["return_shape"]),
                html_escape(row["business_logic"]) + comment,
                html_escape(dep_text),
                file_ref_links(row["source_refs"], limit=2, empty="No source line"),
            ]
        )
    function_details_table = table(
        ["Function", "Kind", "Return shape", "Business logic", "Key dependencies", "Source"],
        function_detail_rows,
    )
    er_diagrams_html = render_er_diagrams(table_files)
    function_group_flow_html = render_function_group_flow(function_logic)
    function_sequence_html = render_function_sequence_diagrams(function_logic)

    queue_html = "\n".join(
        '<div class="card search-item" data-search="{}"><h3>{}</h3><p>{}</p><p class="code-list">{}</p></div>'.format(
            html_escape(item["area"] + " " + " ".join(item["objects"]) + " " + item["why"]),
            html_escape(item["area"]),
            html_escape(item["why"]),
            " ".join(f"<code>{html_escape(obj)}</code>" for obj in item["objects"]),
        )
        for item in MANUAL_REVIEW_QUEUE
    )

    table_rows = []
    for sql_file in sorted(table_files, key=lambda f: f.primary_object):
        search = " ".join(
            [
                sql_file.primary_object,
                sql_file.rel,
                " ".join(col["name"] for col in sql_file.columns),
                " ".join(sql_file.risk_flags),
            ]
        )
        table_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(sql_file.primary_object)}</strong><br><span class="muted">{html_escape(sql_file.rel)}</span></div>',
                str(len(sql_file.columns)),
                str(len(sql_file.fks)),
                str(sql_file.indexes),
                html_escape(", ".join(sql_file.risk_flags[:4]) or "-"),
                html_escape(", ".join(col["name"] for col in sql_file.columns[:12]) + (" ..." if len(sql_file.columns) > 12 else "")),
            ]
        )
    tables_table = table(["Table", "Columns", "FKs", "Indexes", "Flags", "Column sample"], table_rows)

    file_rows = []
    for sql_file in files:
        search = " ".join(
            [
                sql_file.rel,
                sql_file.primary_object,
                sql_file.primary_kind,
                sql_file.category,
                " ".join(sql_file.risk_flags),
                " ".join(sql_file.doc_hits),
                " ".join(sql_file.dependencies),
                " ".join(sql_file.external_refs),
            ]
        )
        file_rows.append(
            [
                f'<div class="search-item" data-search="{html_escape(search)}"><strong>{html_escape(sql_file.primary_object)}</strong><br><span class="muted">{html_escape(sql_file.rel)}</span></div>',
                html_escape(sql_file.category),
                "yes" if sql_file.in_sqlproj else "no",
                str(sql_file.loc),
                str(len(sql_file.dependencies)),
                html_escape(", ".join(sql_file.risk_flags[:5]) or "-"),
                html_escape(", ".join(sql_file.doc_hits[:4]) or "-"),
            ]
        )
    files_table = table(["Object/file", "Category", "SQLProj", "LOC", "Deps", "Risk flags", "Doc topics"], file_rows)

    central_rows = [
        [
            f'<span class="search-item" data-search="{html_escape(row["object"])}">{html_escape(row["object"])}</span>',
            str(row["inbound"]),
            str(row["outbound"]),
            str(row["score"]),
        ]
        for row in central
    ]
    central_table = table(["Object", "Inbound refs", "Outbound refs", "Weighted score"], central_rows)

    external_rows = [
        [
            f'<span class="search-item" data-search="{html_escape(ref)}">{html_escape(ref)}</span>',
            str(count),
        ]
        for ref, count in external_refs.most_common(40)
    ]
    external_table = table(["External reference", "Occurrences/files"], external_rows)

    risk_rows = [
        [f'<span class="search-item" data-search="{html_escape(flag)}">{html_escape(flag)}</span>', str(count)]
        for flag, count in risk_counts.most_common()
    ]
    risk_table = table(["Risk/attention flag", "Files"], risk_rows)

    mutation_rows = [
        [
            f'<div class="search-item" data-search="{html_escape(sql_file.primary_object + " " + sql_file.rel)}"><strong>{html_escape(sql_file.primary_object)}</strong><br><span class="muted">{html_escape(sql_file.rel)}</span></div>',
            ", ".join(f"{key}: {value}" for key, value in sql_file.mutations.items()),
            html_escape(", ".join(sql_file.risk_flags)),
        ]
        for sql_file in sorted(mutation_files, key=lambda f: (-sum(f.mutations.values()), f.rel))
    ]
    mutation_table = table(["Mutating object/file", "Mutation count", "Flags"], mutation_rows)

    pdf_heading_blocks = []
    for pdf in pdfs:
        heading_items = "\n".join(
            f'<li class="search-item" data-search="{html_escape(heading)}">{html_escape(heading)}</li>'
            for heading in pdf["headings"][:180]
        )
        pdf_heading_blocks.append(
            f'<details class="card"><summary>{html_escape(pdf["name"])} - first {min(180, len(pdf["headings"]))} extracted headings</summary><ol>{heading_items}</ol></details>'
        )

    open_questions = [
        "Which statically identified Legacy code call sites are active in production, and which are scheduled jobs, UI paths, or obsolete files?",
        f"Is the {LEGACY_DB_NAME} SQL project still live for another application, or is it only a historical snapshot?",
        "Will the C# extension read/write this legacy database, migrate selected behavior, or only reproduce behavior in a new store?",
        "Which external systems remain authoritative for the external search API/PAC, IDM/SSO, billing, and print-provider handoff?",
        "Are generated obj/Debug SQL files relevant release artifacts, or should future analysis ignore them completely?",
        f"Which spec requirements are confirmed for the C# extension versus historical {LEGACY_DB_NAME} behavior only?",
    ]
    question_html = "\n".join(
        f'<li class="search-item" data-search="{html_escape(question)}">{html_escape(question)}</li>'
        for question in open_questions
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Legacy SQL Analysis - {html_escape(LEGACY_DB_NAME)}</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #b21f2d;
      --accent-2: #0f766e;
      --accent-3: #3858a6;
      --soft: #eef2f7;
      --warn: #f7efe2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
      color: var(--ink);
      background: var(--bg);
    }}
    header {{
      background: #1d2939;
      color: white;
      padding: 28px 32px 20px;
    }}
    header h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    header p {{ margin: 0; color: #d7dce5; max-width: 1120px; }}
    nav {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(255,255,255,.96);
      border-bottom: 1px solid var(--line);
      padding: 12px 32px;
      display: flex;
      gap: 18px;
      align-items: center;
      flex-wrap: wrap;
    }}
    nav a {{ color: var(--accent-3); text-decoration: none; font-weight: 600; font-size: 14px; }}
    #search {{
      min-width: 280px;
      max-width: 520px;
      flex: 1;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      font-size: 15px;
    }}
    main {{ padding: 24px 32px 56px; max-width: 1500px; margin: 0 auto; }}
    section {{ margin: 0 0 28px; }}
    h2 {{ font-size: 23px; margin: 0 0 12px; }}
    h3 {{ margin: 0 0 8px; font-size: 17px; }}
    p {{ margin: 0 0 10px; }}
    .chapter {{
      border-top: 3px solid #1d2939;
      padding-top: 18px;
      margin-top: 34px;
    }}
    .chapter h2 {{ font-size: 26px; }}
    .chapter-intro {{ max-width: 1020px; color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
    .metric, .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 1px 2px rgba(16,24,40,.04);
    }}
    .metric-value {{ font-size: 28px; font-weight: 750; color: var(--accent); }}
    .metric-label {{ font-weight: 700; margin-bottom: 4px; }}
    .muted {{ color: var(--muted); }}
    .warning {{ background: var(--warn); border-left: 4px solid #c47d1d; padding: 12px 14px; border-radius: 6px; }}
    .explain {{ background: #eef6f4; border-left: 4px solid var(--accent-2); padding: 12px 14px; border-radius: 6px; margin: 8px 0 12px; }}
    .pdf-ref {{ margin: 0 0 6px; }}
    .table-wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; font-size: 13px; }}
    th {{ background: var(--soft); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #344054; }}
    tr:hover td {{ background: #fafbfd; }}
    code, .code-ref, .code-pill {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      background: #eef2f7;
      border: 1px solid #dde3ed;
      border-radius: 5px;
      padding: 2px 5px;
      display: inline-block;
      margin: 1px;
    }}
    .code-list code {{ margin: 2px 4px 2px 0; }}
    ol, ul {{ margin-top: 8px; }}
    li {{ margin: 7px 0; }}
    details summary {{ cursor: pointer; font-weight: 700; }}
    .diagram {{
      width: 100%;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 8px 0 12px;
    }}
    .wide {{ min-height: 220px; }}
    .svg-box {{ fill: #fff; stroke: #cbd5e1; stroke-width: 1.4; }}
    .svg-box.muted {{ fill: #f2f4f7; stroke-dasharray: 5 4; }}
    .svg-box-title {{ font-size: 16px; font-weight: 700; fill: #17202a; }}
    .svg-label {{ font-size: 12px; fill: #667085; }}
    .svg-title {{ font-size: 18px; font-weight: 750; fill: #17202a; }}
    .svg-bar {{ fill: #b21f2d; opacity: .88; }}
    .svg-count {{ font-size: 13px; fill: #17202a; font-weight: 650; }}
    .svg-arrow {{ stroke: #64748b; stroke-width: 1.6; }}
    .svg-arrowhead {{ fill: #64748b; }}
    .svg-er-link {{ stroke: #3858a6; stroke-width: 1.45; opacity: .78; }}
    .svg-er-link-inferred {{ stroke: #b45309; stroke-width: 1.35; stroke-dasharray: 6 5; opacity: .85; }}
    .function-map {{
      display: grid;
      grid-template-columns: minmax(180px, .7fr) auto minmax(320px, 2.4fr) auto minmax(200px, .8fr);
      gap: 12px;
      align-items: stretch;
      background: #fff;
      border-radius: 8px;
      border: 1px solid var(--line);
      padding: 14px;
      margin: 10px 0 14px;
    }}
    .function-map-stage, .function-map-card {{
      border: 1px solid #d6dde8;
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
    }}
    .function-map-stage h4, .function-map-card h4 {{ margin: 0 0 6px; font-size: 15px; }}
    .function-map-stage p, .function-map-card p {{ margin: 0 0 5px; }}
    .function-map-groups {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; }}
    .function-map-card {{ padding: 9px 10px; }}
    .function-map-card-head {{ display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }}
    .function-map-card small {{ color: var(--muted); line-height: 1.35; }}
    .function-map-count {{
      min-width: 32px;
      text-align: center;
      border-radius: 999px;
      color: #fff;
      background: var(--accent-3);
      font-weight: 750;
      padding: 2px 7px;
    }}
    .cf-overview-diagram {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) auto minmax(190px, 1fr) auto minmax(190px, 1fr) auto minmax(190px, 1fr);
      gap: 10px;
      align-items: stretch;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin: 8px 0 14px;
    }}
    .cf-stage, .cf-proc-col {{
      border: 1px solid #d6dde8;
      border-radius: 8px;
      padding: 10px 11px;
      background: #fff;
      min-width: 0;
    }}
    .cf-stage h4, .cf-proc-col h4, .cf-domain-card h4 {{ margin: 0 0 6px; font-size: 14px; }}
    .cf-stage p, .cf-proc-col p, .cf-domain-card p {{ margin: 4px 0 0; }}
    .cf-stage small {{ color: var(--muted); }}
    .cf-arrow, .cf-mini-arrow {{
      align-self: center;
      text-align: center;
      color: var(--muted);
      font-weight: 750;
      white-space: nowrap;
    }}
    .cf-proc-grid, .cf-domain-grid {{
      display: grid;
      gap: 10px;
      margin: 8px 0 14px;
    }}
    .cf-proc-card {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto minmax(220px, .95fr) auto minmax(260px, 1.1fr);
      gap: 10px;
      align-items: stretch;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 10px;
    }}
    .cf-domain-grid {{ grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); }}
    .cf-domain-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }}
    .cf-domain-columns {{
      display: grid;
      grid-template-columns: minmax(0, .85fr) minmax(0, 1.15fr);
      gap: 12px;
      margin-top: 10px;
    }}
    .cf-file-list {{
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
      margin-top: 6px;
    }}
    .function-map-arrow {{
      align-self: center;
      color: var(--muted);
      font-weight: 700;
      text-align: center;
      white-space: nowrap;
    }}
    .function-flow-panel {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
      margin: 10px 0 4px;
    }}
    .function-sequence-steps {{
      list-style: none;
      counter-reset: flow-step;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 8px;
    }}
    .function-sequence-steps li {{
      counter-increment: flow-step;
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 10px;
      align-items: start;
      padding: 8px 10px;
      border-left: 3px solid var(--accent-3);
      background: #f8fafc;
      border-radius: 6px;
      margin: 0;
    }}
    .function-sequence-steps li strong::before {{
      content: counter(flow-step) ". ";
      color: var(--accent-3);
    }}
    .function-sequence-steps li span {{ color: #344054; }}
    .function-flow-chips {{ margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }}
    .flow-chip {{
      display: inline-block;
      border: 1px solid #d6dde8;
      background: #eef2f7;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      color: #344054;
    }}
    .coverage-summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 8px 0;
    }}
    .coverage-summary span,
    .coverage-status {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
    }}
    .coverage-summary span {{ background: #eef2f7; border: 1px solid #d6dde8; color: #344054; }}
    .coverage-status.yes {{ background: #dcfce7; color: #166534; }}
    .coverage-status.partial {{ background: #fef3c7; color: #92400e; }}
    .coverage-status.no {{ background: #fee2e2; color: #991b1b; }}
    .coverage-status.other {{ background: #e0e7ff; color: #3730a3; }}
    .coverage-columns {{ margin-top: 5px; overflow-wrap: anywhere; }}
    .coverage-table {{ min-width: 1280px; }}
    .overview-coverage-table {{ min-width: 1420px; }}
    .overview-gap-table {{ min-width: 980px; }}
    .er-model {{
      display: grid;
      grid-template-columns: minmax(300px, .85fr) minmax(0, 1.35fr);
      gap: 14px;
      align-items: start;
      margin-top: 10px;
    }}
    .er-card-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .er-card {{
      border: 1px solid #d6dde8;
      border-radius: 8px;
      background: #fff;
      padding: 11px 12px;
      min-width: 0;
    }}
    .er-card-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
      border-bottom: 1px solid #eef2f7;
      padding-bottom: 6px;
      margin-bottom: 8px;
    }}
    .er-card-head h4 {{
      margin: 0;
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    .er-card-head span, .er-card-meta {{
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }}
    .er-card-meta {{ display: flex; gap: 8px; margin-bottom: 8px; }}
    .er-columns {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 4px;
    }}
    .er-columns li {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(70px, .7fr);
      gap: 6px;
      align-items: baseline;
      margin: 0;
      font-size: 11px;
    }}
    .er-columns code {{
      overflow-wrap: anywhere;
      background: transparent;
      border: 0;
      padding: 0;
      margin: 0;
      font-size: 11px;
    }}
    .er-col-badge {{
      border-radius: 999px;
      color: #fff;
      font-size: 10px;
      font-weight: 750;
      padding: 1px 5px;
    }}
    .er-col-badge.id {{ background: var(--accent-3); }}
    .er-col-badge.fk {{ background: #b45309; }}
    .er-col-badge.empty {{
      visibility: hidden;
      min-width: 20px;
    }}
    .er-card-details {{
      margin-top: 7px;
      padding-top: 6px;
      border-top: 1px solid #eef2f7;
    }}
    .er-card-details summary {{ font-size: 12px; color: var(--muted); }}
    .er-card-details p {{ font-size: 12px; margin-top: 5px; overflow-wrap: anywhere; }}
    .er-relationship-panel {{
      border: 1px solid #d6dde8;
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }}
    .er-relationship-panel h4 {{ margin: 0 0 6px; }}
    .er-relationship-list {{ display: grid; gap: 8px; margin-top: 10px; }}
    .er-relation {{
      border-left: 4px solid var(--accent-3);
      background: #f8fafc;
      border-radius: 6px;
      padding: 8px 9px;
      display: grid;
      gap: 5px;
      font-size: 12px;
    }}
    .er-relation .code-ref {{ overflow-wrap: anywhere; }}
    .er-relation.inferred {{ border-left-color: #b45309; }}
    .er-arrow-text {{ color: #344054; }}
    .er-rel-kind {{
      width: max-content;
      border-radius: 999px;
      color: #fff;
      background: var(--accent-3);
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 750;
    }}
    .er-relation.inferred .er-rel-kind {{ background: #b45309; }}
    .er-relationship-details {{ margin-top: 10px; }}
    .er-diagram {{ min-height: 360px; }}
    .mermaid-card {{ margin: 8px 0 14px; }}
    .mermaid-card-grid {{
      display: grid;
      gap: 12px;
      margin: 8px 0 14px;
    }}
    .mermaid-card summary {{
      font-size: 15px;
      margin-bottom: 8px;
      overflow-wrap: anywhere;
    }}
    .mermaid-er-card {{ margin-bottom: 16px; }}
    .er-mermaid-summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 12px;
    }}
    .er-mermaid-summary span {{
      border: 1px solid #d6dde8;
      border-radius: 999px;
      background: #f8fafc;
      padding: 4px 9px;
      color: #344054;
      font-size: 12px;
    }}
    .acid-er-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 6px 0 14px;
    }}
    .acid-status {{
      display: inline-flex;
      align-items: center;
      width: max-content;
      border-radius: 999px;
      border: 1px solid #d6dde8;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.2;
      white-space: nowrap;
    }}
    .acid-status-exists {{ background: #eff6ff; border-color: #2563eb; color: #1e3a8a; }}
    .acid-status-extend {{ background: #ecfdf3; border-color: #059669; color: #065f46; }}
    .acid-status-implement {{ background: #fff7ed; border-color: #ea580c; color: #9a3412; }}
    .acid-er-status-list {{
      display: grid;
      gap: 6px;
      margin: 8px 0 10px;
      font-size: 12px;
    }}
    .acid-er-status-list div {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      align-items: center;
    }}
    .mermaid-diagram-wrap {{
      overflow: auto;
      background: #fff;
      border: 1px solid #d6dde8;
      border-radius: 8px;
      padding: 16px;
      margin-top: 8px;
    }}
    .mermaid-diagram-wrap .mermaid {{
      min-width: 760px;
      margin: 0;
      color: #17202a;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 13px;
      line-height: 1.4;
      white-space: pre;
    }}
    .mermaid-diagram-wrap svg {{
      min-width: 760px;
      max-width: none;
      height: auto;
    }}
    .mermaid-er-wrap .mermaid,
    .mermaid-er-wrap svg {{
      min-width: 980px;
    }}
    .mermaid-sequence-wrap .mermaid,
    .mermaid-sequence-wrap svg,
    .mermaid-flowchart-wrap .mermaid,
    .mermaid-flowchart-wrap svg {{
      min-width: 760px;
    }}
    .domain-overlay-card .mermaid-flowchart-wrap .mermaid,
    .domain-overlay-card .mermaid-flowchart-wrap svg {{
      min-width: 2600px;
    }}
    .mermaid-card .function-flow-chips strong {{
      align-self: center;
      font-size: 12px;
      color: #344054;
      margin-right: 2px;
    }}
    .mermaid-source-details {{ margin-top: 10px; }}
    .mermaid-source {{
      overflow: auto;
      max-height: 420px;
      margin: 8px 0 0;
      padding: 12px;
      background: #0f172a;
      color: #e5e7eb;
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.45;
    }}
    .er-rel-kind.declared {{ background: var(--accent-3); }}
    .er-rel-kind.inferred {{ background: #b45309; }}
    .two-col {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }}
    @media (max-width: 900px) {{
      main, header, nav {{ padding-left: 16px; padding-right: 16px; }}
      .two-col {{ grid-template-columns: 1fr; }}
      .er-model {{ grid-template-columns: 1fr; }}
      .er-columns li {{ grid-template-columns: minmax(0, 1fr) auto; }}
      .er-columns li .muted {{ grid-column: 1 / -1; }}
      .function-map {{ grid-template-columns: 1fr; }}
      .function-map-arrow {{ white-space: normal; }}
      .cf-overview-diagram, .cf-proc-card, .cf-domain-columns {{ grid-template-columns: 1fr; }}
      .cf-arrow, .cf-mini-arrow {{ white-space: normal; }}
      .function-sequence-steps li {{ grid-template-columns: 1fr; }}
      header h1 {{ font-size: 24px; }}
    }}
    .hidden-by-search {{ display: none !important; }}
  </style>
</head>
<body>
  <header>
    <h1>Legacy SQL Analysis - {LEGACY-DB-NAME}</h1>
    <p>Generated {html_escape(generated_at)}. Scope: client-provided SQL for the legacy legacy-code-backed {LEGACY-SYSTEM} database layer, compared with the official client spec PDFs and the available Legacy code legacy source under <code>{html_escape(legacy_code.get("root", rel(LEGACY_CODE_ROOT)))}</code>. Legacy code findings are static source references, not production runtime telemetry.</p>
  </header>
  <nav>
    <input id="search" type="search" placeholder="Search report: object, table, PDF topic, risk, field...">
    <a href="#chapter-overview">Overview</a>
    <a href="#db-table-recommendations">DB Recommendations</a>
    <a href="#chapter-sql-landscape">SQL Landscape</a>
    <a href="#chapter-sql-pdf">SQL + PDFs</a>
    <a href="#chapter-csharp-gap">SQL vs C#</a>
    <a href="#chapter-function-flows">Function Flows</a>
    <a href="#chapter-review">Review & Risks</a>
  </nav>
  <main>
    <section id="chapter-overview" class="chapter">
      <h2>Chapter 1 - Overview: Spec, Legacy SQL, and C# Coverage</h2>
      <p class="chapter-intro">A spec-document-anchored matrix to read the official specification, legacy SQL evidence, and current C# implementation coverage in one place. This is the fastest view for planning and stakeholder conversations.</p>
    </section>

    {render_spec_coverage_overview(spec_coverage_overview)}
    {render_db_table_recommendations(db_table_recommendations, domain_model_recommendation_er, recommended_acid_er)}

    <section id="chapter-sql-landscape" class="chapter">
      <h2>Chapter 2 - Legacy SQL Landscape</h2>
      <p class="chapter-intro">Inventory, database shape, ER diagrams, SQL flow hypotheses, and Legacy code call-site evidence. This chapter describes what exists in the legacy SQL project before comparing it to PDFs or C#.</p>
    </section>

    <section id="overview">
      <h2>Executive Summary</h2>
      <div class="warning search-item" data-search="legacy code static call-site evidence official documents primary sql secondary runtime telemetry">
        <strong>Important constraint:</strong> the Legacy code legacy application is now available as static source under <code>{html_escape(legacy_code.get("root", rel(LEGACY_CODE_ROOT)))}</code>, and this report maps direct SQL references from that source. The mapping proves source-level call sites, but not production datasource configuration, runtime frequency, scheduled-job activation, or complete user-flow reachability.
      </div>
      <div class="grid">{cards_html}</div>
    </section>

    <section id="plan">
      <h2>Investigation Plan</h2>
      <ol>{plan_html}</ol>
    </section>

    <section id="sources">
      <h2>Sources And Authority</h2>
      <p>The official PDFs are treated as primary client source documents. Legacy SQL is supporting evidence for existing or historical database behavior. Legacy code is supporting runtime-call-site evidence because it shows which legacy source files reference imported SQL objects. Confirmed requirements should be curated under <code>docs/requirements/</code>; this report remains generated analysis under <code>reports/evaluations/</code>.</p>
      <p class="muted">Terminology used below: <strong>Primary Spec PDF</strong> means <code>{html_escape(PDF_SOURCES[0].name)}</code>; <strong>Print Spec Document PDF</strong> means <code>{html_escape(PDF_SOURCES[1].name)}</code>; <strong>Legacy SQL repo</strong> means <code>{html_escape(rel(SQL_ROOT))}</code>; <strong>Legacy code app</strong> means <code>{html_escape(legacy_code.get("root", rel(LEGACY_CODE_ROOT)))}</code>. These are separate sources, not aliases for each other.</p>
      {sources_table}
    </section>

    <section id="diagrams">
      <h2>Diagrams</h2>
      <h3>Legacy Code Static SQL Call-Site Evidence</h3>
      <div class="explain search-item" data-search="legacy code sql connection call site datasource legacy integrated">
        <strong>What was found:</strong> the Legacy code app defines datasource <code>{html_escape(legacy_code.get("datasource") or "unknown")}</code> and the static scan found <strong>{legacy_code.get("files_with_sql_hits", 0)}</strong> Legacy code files referencing <strong>{legacy_code.get("distinct_sql_objects_hit", 0)}</strong> imported SQL objects. This makes Legacy code a real supporting source for call-site mapping, while unresolved production deployment details remain open.
      </div>
      <h4>Legacy code To SQL Overview</h4>
      {legacy_code_overview_diagram}
      <h4>Legacy code Procedure Call Map</h4>
      {legacy_code_procedure_diagram}
      <h4>Legacy code Functional Area Map</h4>
      {legacy_code_domain_diagram}
      <details class="card">
        <summary>Legacy code evidence tables</summary>
      {legacy_code_summary_table}
      <h4>Stored Procedure Calls - Table Detail</h4>
      {legacy_code_proc_table}
      <h4>Most Referenced Imported SQL Objects From Legacy code - Table Detail</h4>
      {legacy_code_object_table}
      <h4>Legacy code Files With Most Imported SQL References - Table Detail</h4>
      {legacy_code_file_table}
      </details>
      <h3>Diagram Source Evidence</h3>
      {diagram_sources_table}
      <div class="two-col">
        <div>
          <h3>Object Categories</h3>
          {svg_bar_chart(category_counts, "SQL files by category")}
        </div>
        <div>
          <h3>Schemas</h3>
          {svg_bar_chart(schema_counts, "Definitions by schema")}
        </div>
      </div>
      <h3>Core Persistence Hypothesis</h3>
      <div class="explain search-item" data-search="core persistence hypothesis explanation">
        <strong>How to read this:</strong> this is the likely database save path inferred from SQL files, especially <code>P_STORE_ORDER_XML</code> and its called procedures. It writes head/detail/destination/billing tables, calls external API/CLR wrappers for person data, and writes audit logs. Legacy code now adds static call-site evidence for this path, but the diagram is still not production runtime telemetry and does not prove execution frequency.
      </div>
      {svg_core_flow()}
      <h3>Print Datafile Flow</h3>
      <div class="explain search-item" data-search="print datafile flow explanation">
        <strong>How to read this:</strong> this diagram is deliberately mixed-source. The print spec PDF defines the K/N/D/E datafile contract for the print provider. The SQL files show the legacy implementation: <code>LabelPrint</code> calls <code>FilterByOrderLabels</code> for K/N rows, fetches person rows for D/E rows through external API/CLR wrappers, emits pipe-delimited output, and writes envelope tracking rows into <code>TEnvelope_BAA</code>.
      </div>
      {svg_print_flow()}
    </section>

    <section id="er-diagrams">
      <h2>ER Diagrams</h2>
      <p class="muted">These ER diagrams are generated as Mermaid ER diagrams from SQL table files. Solid relationships are declared foreign keys extracted from DDL; dotted relationships are inferred from column names such as <code>FK_OrderHead</code> and require manual review. If Mermaid rendering is unavailable, each card keeps the Mermaid source visible.</p>
      {er_diagrams_html}
    </section>

    <section id="inventory">
      <h2>SQL Inventory</h2>
      <h3>Tables</h3>
      {tables_table}
      <h3>Central Objects By Reference Score</h3>
      {central_table}
      <h3>All SQL Files</h3>
      {files_table}
    </section>

    <section id="chapter-sql-pdf" class="chapter">
      <h2>Chapter 3 - Requirements Cross-Check: SQL + PDFs</h2>
      <p class="chapter-intro">Maps legacy SQL evidence against the official specification documents. PDF content remains the primary client source; SQL is supporting implementation and historical behavior evidence.</p>
    </section>

    <section id="comparison">
      <h2>Official Document Comparison</h2>
      <h3>Semantic Map</h3>
      {semantic_table}
      <h3>Domain Topic Coverage</h3>
      {topic_table}
      <h3>Druck/Kuvertierung Datafile Field Mapping</h3>
      <p class="muted">Automated mapping uses field names and semantic aliases from the official print document. It is a review guide, not a final interface specification.</p>
      {print_table}
    </section>

    <section id="products">
      <h2>Products To SQL</h2>
      <p class="muted">Products come from the specstart page form type list. The main list is on page 9, section 8.2; PF and REC subtype details continue on page 10. SQL relevance is an automated term-based scan and should be reviewed manually before turning it into requirements.</p>
      {product_table}
    </section>

    <section id="chapter-csharp-gap" class="chapter">
      <h2>Chapter 4 - Implementation Gap: SQL/PDF vs C#</h2>
      <p class="chapter-intro">Compares official requirements and legacy SQL topics with the current C# backend surface. This is evidence of implementation coverage, not a behavior-parity proof.</p>
    </section>

    <section id="csharp-backend">
      <h2>C# Backend Comparison</h2>
      <p class="muted">This compares legacy SQL/PDF topics with files already present under <code>csharp/src/backend</code>. It is evidence of implementation surface, not a full behavioral parity proof.</p>
      {csharp_table}
    </section>

    {render_csharp_sql_model_section(csharp_sql_model)}

    <section id="chapter-function-flows" class="chapter">
      <h2>Chapter 5 - SQL Function Behavior And Flows</h2>
      <p class="chapter-intro">Groups SQL Server functions by business role and renders Mermaid flow diagrams. These flows show dependencies visible in SQL, not confirmed Legacy code runtime call paths.</p>
    </section>

    <section id="sql-functions">
      <h2>SQL Functions: Business Logic</h2>
      <p class="muted">In the SQL inventory, category <code>Function</code> means SQL Server user-defined functions: reusable read/format/lookup routines, including table-valued functions and CLR/provider wrappers. They are not UI features. The descriptions below are static interpretations of the SQL files and linked PDF evidence; Legacy code call-site evidence is summarized separately and should be treated as source evidence, not runtime telemetry.</p>
      <h3>High-Level Function Flow</h3>
      {function_group_flow_html}
      <h3>Function Groups</h3>
      {function_groups_table}
      <h3>Function Detail</h3>
      {function_details_table}
      <h3>Per-Function Mermaid Flow Diagrams</h3>
      <p class="muted">Each flow diagram is generated from static dependencies, external references, source lines, and the function's business role. Use it as an investigation map; do not treat it as a proven runtime trace.</p>
      {function_sequence_html}
    </section>

    <section id="chapter-review" class="chapter">
      <h2>Chapter 6 - Review Queue, Risks, And Appendix</h2>
      <p class="chapter-intro">Manual review targets, automated attention flags, external dependencies, open client questions, and source-document appendix material.</p>
    </section>

    <section id="review-queue">
      <h2>Manual Review Queue</h2>
      <div class="grid">{queue_html}</div>
    </section>

    <section id="risks">
      <h2>Risks And Questions</h2>
      <div class="two-col">
        <div>
          <h3>Automated Attention Flags</h3>
          {risk_table}
        </div>
        <div>
          <h3>External References</h3>
          {external_table}
        </div>
      </div>
      <h3>Mutating SQL Objects</h3>
      {mutation_table}
      <h3>Open Client Questions</h3>
      <ol>{question_html}</ol>
    </section>

    <section id="appendix">
      <h2>Appendix</h2>
      <h3>Extracted PDF Headings</h3>
      {"".join(pdf_heading_blocks)}
      <h3>Generation Notes</h3>
      <div class="card">
        <p>Generated from <code>{html_escape(rel(SQL_ROOT))}</code>, <code>{html_escape(rel(PDF_SOURCES[0]))}</code>, and <code>{html_escape(rel(PDF_SOURCES[1]))}</code>.</p>
        <p>Report data JSON: <code>{html_escape(rel(DATA_JSON))}</code></p>
      </div>
    </section>
  </main>
  <script>
    const search = document.getElementById('search');
    function matchesText(el, q) {{
      if (!q) return true;
      const haystack = ((el.dataset.search || '') + ' ' + el.textContent).toLowerCase();
      return q.split(/\\s+/).every(part => haystack.includes(part));
    }}
    function applySearch() {{
      const q = search.value.trim().toLowerCase();
      document.querySelectorAll('.search-item').forEach(el => {{
        el.classList.toggle('hidden-by-search', !matchesText(el, q));
      }});
      document.querySelectorAll('tbody.searchable-rows tr').forEach(row => {{
        row.classList.toggle('hidden-by-search', !matchesText(row, q));
      }});
    }}
    search.addEventListener('input', applySearch);
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>
    function applyAcidErStatusColors() {{
      const palette = {{
        exists: {{ fill: '#eff6ff', stroke: '#2563eb' }},
        extend: {{ fill: '#ecfdf3', stroke: '#059669' }},
        implement: {{ fill: '#fff7ed', stroke: '#ea580c' }}
      }};
      const normalizeText = value => (value || '').replace(/\\s+/g, '').trim().toLowerCase();
      const normalizeLoose = value => normalizeText(value).replace(/[^a-z0-9]/g, '');
      document.querySelectorAll('.acid-er-card').forEach(card => {{
        const data = card.querySelector('.acid-er-status-data');
        const svg = card.querySelector('.mermaid-diagram-wrap svg');
        if (!data || !svg) return;
        let statuses = {{}};
        try {{
          statuses = JSON.parse(data.textContent || '{{}}');
        }} catch (error) {{
          return;
        }}
        const statusByLabel = new Map();
        Object.entries(statuses).forEach(([label, status]) => {{
          if (!label || !status) return;
          statusByLabel.set(normalizeText(label), status);
          statusByLabel.set(normalizeLoose(label), status);
        }});
        svg.querySelectorAll('text').forEach(text => {{
          const status = statusByLabel.get(normalizeText(text.textContent)) || statusByLabel.get(normalizeLoose(text.textContent));
          const colors = palette[status];
          if (!colors) return;
          let group = text.closest('g');
          let depth = 0;
          while (group && depth < 6) {{
            const textCount = group.querySelectorAll('text').length;
            const shapes = Array.from(group.querySelectorAll('rect, polygon, path')).filter(shape => {{
              const stroke = (shape.getAttribute('stroke') || '').toLowerCase();
              const fill = (shape.getAttribute('fill') || '').toLowerCase();
              return stroke !== 'none' || fill === '#fff' || fill === '#ffffff' || fill === 'white' || fill === '';
            }});
            if (textCount > 1 && shapes.length) {{
              shapes.forEach(shape => {{
                shape.style.setProperty('fill', colors.fill, 'important');
                shape.style.setProperty('stroke', colors.stroke, 'important');
                shape.style.setProperty('stroke-width', '2px', 'important');
              }});
              group.classList.add(`acid-er-entity-${{status}}`);
              break;
            }}
            group = group.parentElement ? group.parentElement.closest('g') : null;
            depth += 1;
          }}
        }});
      }});
    }}
    if (window.mermaid) {{
      mermaid.initialize({{
        startOnLoad: false,
        securityLevel: 'loose',
        theme: 'base',
        themeVariables: {{
          primaryColor: '#ffffff',
          primaryBorderColor: '#3858a6',
          primaryTextColor: '#17202a',
          lineColor: '#64748b',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
        }},
        er: {{
          useMaxWidth: false
        }},
        sequence: {{
          useMaxWidth: false,
          mirrorActors: false,
          showSequenceNumbers: true,
          wrap: true,
          width: 150
        }}
      }});
      if (mermaid.run) {{
        const renderMermaidBlocks = async () => {{
          for (const block of Array.from(document.querySelectorAll('.mermaid'))) {{
            try {{
              await mermaid.run({{ nodes: [block] }});
            }} catch (error) {{
              console.error('Mermaid render failed for one diagram', error);
            }}
          }}
          applyAcidErStatusColors();
        }};
        renderMermaidBlocks();
      }} else {{
        mermaid.init(undefined, document.querySelectorAll('.mermaid'));
        setTimeout(applyAcidErStatusColors, 250);
      }}
    }}
  </script>
</body>
</html>"""


def serializable_data(data: dict) -> dict:
    files: list[SqlFile] = data["files"]
    return {
        "generated_at": data["generated_at"],
        "sql_root": rel(SQL_ROOT),
        "sql_git": data["sql_git"],
        "pdfs": [
            {
                "path": pdf["path"],
                "name": pdf["name"],
                "pages": pdf["pages"],
                "chars": pdf["chars"],
                "heading_count": len(pdf["headings"]),
                "headings": pdf["headings"],
            }
            for pdf in data["pdfs"]
        ],
        "sql_files": [
            {
                "path": sql_file.rel,
                "category": sql_file.category,
                "in_sqlproj": sql_file.in_sqlproj,
                "generated": sql_file.generated,
                "primary_object": sql_file.primary_object,
                "primary_kind": sql_file.primary_kind,
                "loc": sql_file.loc,
                "definitions": sql_file.definitions,
                "columns": sql_file.columns,
                "foreign_keys": sql_file.fks,
                "indexes": sql_file.indexes,
                "statistics": sql_file.stats,
                "grants": sql_file.grants,
                "mutations": dict(sql_file.mutations),
                "dependencies": sorted(sql_file.dependencies),
                "external_refs": sorted(sql_file.external_refs),
                "risk_flags": sql_file.risk_flags,
                "doc_hits": sql_file.doc_hits,
            }
            for sql_file in files
        ],
        "topic_comparison": data["topic_comparison"],
        "spec_coverage_overview": data["spec_coverage_overview"],
        "db_table_recommendations": data["db_table_recommendations"],
        "domain_model_recommendation_er": data["domain_model_recommendation_er"],
        "recommended_acid_er_diagrams": data["recommended_acid_er_diagrams"],
        "semantic_map": data["semantic_map"],
        "print_fields": data["print_fields"],
        "product_sql": data["product_sql"],
        "csharp_backend": data["csharp_backend"],
        "csharp_sql_model": data["csharp_sql_model"],
        "function_logic": data["function_logic"],
        "legacy_code": data["legacy_code"],
        "diagram_sources": data["diagram_sources"],
    }


def main() -> int:
    if not SQL_ROOT.exists():
        raise SystemExit(f"Missing SQL root: {SQL_ROOT}")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    files, _ = analyze_sql_files()
    pdfs = extract_pdf_data()
    csharp_files = read_csharp_files()
    requirements = read_requirement_pages()
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "pdfs": pdfs,
        "sql_git": {
            "commit": run_git(["rev-parse", "HEAD"], SQL_ROOT),
            "branch": run_git(["branch", "--show-current"], SQL_ROOT),
            "remote": run_git(["config", "--get", "remote.origin.url"], SQL_ROOT),
        },
    }
    data["topic_comparison"] = build_topic_comparison(files, pdfs)
    data["semantic_map"] = build_semantic_map(files, pdfs)
    data["print_fields"] = build_print_field_mapping(files, pdfs)
    data["product_sql"] = build_product_sql_mapping(files, pdfs)
    data["csharp_backend"] = build_csharp_backend_comparison(csharp_files, pdfs)
    data["csharp_sql_model"] = build_csharp_sql_model(files)
    data["spec_coverage_overview"] = build_spec_coverage_overview(files, pdfs, csharp_files, requirements)
    data["db_table_recommendations"] = build_db_table_recommendations(data["csharp_sql_model"], requirements)
    data["domain_model_recommendation_er"] = build_domain_model_recommendation_er(
        data["csharp_sql_model"],
        data["db_table_recommendations"],
    )
    data["recommended_acid_er_diagrams"] = build_recommended_acid_er_diagrams(data["db_table_recommendations"])
    data["function_logic"] = build_function_business_logic(files, pdfs)
    data["legacy_code"] = build_legacy_code_callsite_analysis(files)
    data["diagram_sources"] = build_diagram_sources(files, pdfs, data["legacy_code"])

    DATA_JSON.write_text(json.dumps(serializable_data(data), indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(render_report(data), encoding="utf-8")
    MKDOCS_COVERAGE_PAGE.write_text(
        render_spec_coverage_mkdocs_page(
            data["spec_coverage_overview"],
            data["db_table_recommendations"],
            data["recommended_acid_er_diagrams"],
            data["generated_at"],
        ),
        encoding="utf-8",
    )
    followup_pages = write_recommended_entity_followups(data["db_table_recommendations"])
    print(f"Wrote {rel(REPORT)}")
    print(f"Wrote {rel(DATA_JSON)}")
    print(f"Wrote {rel(MKDOCS_COVERAGE_PAGE)}")
    if followup_pages:
        print(f"Updated {len(followup_pages)} requirement/feature pages with recommended entity questions")
    print(f"Analyzed {len(files)} SQL files and {len(pdfs)} PDFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
