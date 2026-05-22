from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from xml.etree import ElementTree

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reporting import AuditLog, Booking, TraveltekBookingUpdate, TraveltekSyncRun
from app.services.master_booking_import import (
    determine_atol_review_status,
    determine_booking_company,
    normalise_booking_ref,
    normalise_booking_status,
    parse_date,
    parse_datetime,
    parse_elements,
    parse_int,
    parse_money,
)


TRAVELTEK_NAMESPACE = "http://fusionapi.traveltek.net/0.9/xsds"
FIELD_DEFINITIONS = {
    "imported_booking_status": {
        "label": "Booking status",
        "candidates": ("status", "bookingstatus", "booking_status"),
        "parser": "status",
    },
    "customer_last_name": {
        "label": "Customer / lead name",
        "candidates": ("leadname", "leadpassenger", "customername", "customer", "lastname", "last_name", "surname"),
        "parser": "text",
    },
    "agent_in_charge": {
        "label": "Agent in charge",
        "candidates": ("agentincharge", "agent", "consultant", "consultantname", "salesperson", "bookedby"),
        "parser": "text",
    },
    "destination": {
        "label": "Destination",
        "candidates": ("destination", "resort", "region", "location"),
        "parser": "text",
    },
    "travel_elements_raw": {
        "label": "Travel elements",
        "candidates": ("elements", "products", "producttype", "type"),
        "parser": "text",
    },
    "departure_date": {
        "label": "Departure date",
        "candidates": ("departuredate", "departdate", "depdate", "startdate"),
        "parser": "date",
    },
    "return_date": {
        "label": "Return date",
        "candidates": ("returndate", "returneddate", "enddate"),
        "parser": "date",
    },
    "passenger_count": {
        "label": "Passenger count",
        "candidates": ("pax", "passengers", "passengercount", "totalpax", "numberofpassengers"),
        "parser": "int",
    },
    "booking_date": {
        "label": "Booking date",
        "candidates": ("bookingdate", "datebooked", "bookeddate", "createddate"),
        "parser": "datetime",
    },
    "customer_balance_due_date": {
        "label": "Customer balance due date",
        "candidates": ("duedate", "balanceduedate", "customerbalanceduedate", "paymentduedate"),
        "parser": "date",
    },
    "imported_customer_outstanding": {
        "label": "Imported customer outstanding",
        "candidates": ("outstanding", "customeroutstanding", "balancedue", "customerbalancedue"),
        "parser": "money",
    },
    "imported_supplier_outstanding": {
        "label": "Imported supplier outstanding",
        "candidates": ("outstandingsupplier", "supplieroutstanding", "supplierbalancedue"),
        "parser": "money",
    },
    "non_trusted_total_received": {
        "label": "Traveltek customer paid",
        "candidates": ("totalreceived", "totalpaid", "customerpaid", "paid", "amountpaid"),
        "parser": "money",
    },
    "non_trusted_paid_supplier": {
        "label": "Traveltek supplier paid",
        "candidates": ("paidsupp", "paidsupplier", "supplierpaid", "paidtosupplier"),
        "parser": "money",
    },
    "non_trusted_projected_profit": {
        "label": "Traveltek projected profit",
        "candidates": ("profitprojected", "projectedprofit", "profit", "margin"),
        "parser": "money",
    },
    "gross_booking_value": {
        "label": "Gross booking value",
        "candidates": ("totalcost", "totalprice", "totalsell", "totalvalue", "gross"),
        "parser": "money",
    },
    "expected_supplier_nett": {
        "label": "Expected supplier nett",
        "candidates": ("nett", "net", "nettcost", "suppliernett", "suppliercost"),
        "parser": "money",
    },
}
BOOKING_REF_CANDIDATES = (
    "bookingreference",
    "bookingref",
    "booking_ref",
    "externalreference",
    "externalref",
    "reference",
)
BOOKING_ELEMENT_NAMES = {"booking", "portfolio", "enquiry", "item", "row", "result"}


@dataclass
class TraveltekBookingData:
    values: dict[str, Any]
    source: dict[str, Any]


class TraveltekConfigurationError(RuntimeError):
    pass


class TraveltekApiError(RuntimeError):
    pass


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1].strip().lower()


def normalise_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def element_to_source(element: ElementTree.Element) -> dict[str, Any]:
    return {
        "tag": local_name(element.tag),
        "attributes": dict(element.attrib),
        "text": (element.text or "").strip() or None,
        "children": [element_to_source(child) for child in list(element)[:40]],
    }


def flatten_xml(element: ElementTree.Element, output: dict[str, str] | None = None) -> dict[str, str]:
    if output is None:
        output = {}

    element_name = local_name(element.tag)
    text = (element.text or "").strip()
    if text and element_name not in output:
        output[element_name] = text

    for attr_name, value in element.attrib.items():
        key = normalise_key(attr_name)
        if value is not None and key not in output:
            output[key] = str(value).strip()

    for child in element:
        flatten_xml(child, output)

    return output


def value_from_candidates(flattened: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    normalised = {normalise_key(key): value for key, value in flattened.items() if value not in {None, ""}}
    for candidate in candidates:
        value = normalised.get(normalise_key(candidate))
        if value not in {None, ""}:
            return value
    return None


def parse_traveltek_value(value: str | None, parser: str) -> Any:
    if value is None:
        return None
    if parser == "money":
        return parse_money(value)
    if parser == "date":
        return parse_date(value)
    if parser == "datetime":
        return parse_datetime(value)
    if parser == "int":
        return parse_int(value)
    if parser == "status":
        return value.strip()
    return value.strip() or None


def display_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def values_are_equal(current_value: Any, traveltek_value: Any) -> bool:
    if current_value is None and traveltek_value in {None, ""}:
        return True
    if isinstance(current_value, Decimal) or isinstance(traveltek_value, Decimal):
        if current_value is None or traveltek_value is None:
            return False
        return Decimal(current_value).quantize(Decimal("0.01")) == Decimal(traveltek_value).quantize(Decimal("0.01"))
    if isinstance(current_value, datetime) or isinstance(traveltek_value, datetime):
        return display_value(current_value) == display_value(traveltek_value)
    if isinstance(current_value, date) or isinstance(traveltek_value, date):
        return display_value(current_value) == display_value(traveltek_value)
    return str(current_value or "").strip().lower() == str(traveltek_value or "").strip().lower()


def build_request_xml(action: str, attributes: dict[str, str]) -> str:
    request = ElementTree.Element("request", xmlns=TRAVELTEK_NAMESPACE)
    ElementTree.SubElement(
        request,
        "auth",
        username=settings.traveltek_username,
        password=settings.traveltek_password,
    )
    method_attributes = {"action": action}
    if settings.traveltek_sitename.strip():
        method_attributes["sitename"] = settings.traveltek_sitename.strip()
    method_attributes.update({key: value for key, value in attributes.items() if value})
    ElementTree.SubElement(request, "method", **method_attributes)
    return ElementTree.tostring(request, encoding="unicode")


def call_traveltek(action: str, attributes: dict[str, str]) -> ElementTree.Element:
    if not settings.traveltek_api_configured:
        raise TraveltekConfigurationError("Traveltek API is not configured in Render yet.")

    request_xml = build_request_xml(action, attributes)
    encoded = urllib.parse.urlencode({"xml": request_xml}).encode("utf-8")
    request = urllib.request.Request(
        settings.traveltek_api_base_url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise TraveltekApiError(f"Traveltek API returned HTTP {exc.code}: {response_text[:500]}") from exc
    except urllib.error.URLError as exc:
        raise TraveltekApiError(f"Traveltek API request failed: {exc}") from exc

    try:
        root = ElementTree.fromstring(response_text)
    except ElementTree.ParseError as exc:
        raise TraveltekApiError("Traveltek API returned a response that was not valid XML.") from exc

    if root.attrib.get("success", "Y").upper() == "N":
        error_text = " ".join(
            (element.text or "").strip()
            for element in root.iter()
            if local_name(element.tag) in {"error", "message"} and (element.text or "").strip()
        )
        raise TraveltekApiError(error_text or "Traveltek API returned an error.")

    return root


def fetch_booking_by_reference(booking_ref: str) -> TraveltekBookingData:
    root = call_traveltek("getportfolio", {"bookingreference": booking_ref})
    flattened = flatten_xml(root)
    values = extract_booking_values(flattened)
    return TraveltekBookingData(
        values=values,
        source={
            "action": "getportfolio",
            "extracted": {key: display_value(value) for key, value in values.items()},
            "sample": element_to_source(root),
        },
    )


def extract_booking_values(flattened: dict[str, str]) -> dict[str, Any]:
    booking_ref = normalise_booking_ref(value_from_candidates(flattened, BOOKING_REF_CANDIDATES))
    values: dict[str, Any] = {}
    if booking_ref:
        values["booking_ref"] = booking_ref
        values["booking_company"] = determine_booking_company(booking_ref)

    for field_name, definition in FIELD_DEFINITIONS.items():
        raw_value = value_from_candidates(flattened, definition["candidates"])
        try:
            parsed_value = parse_traveltek_value(raw_value, definition["parser"])
        except ValueError:
            parsed_value = None
        if parsed_value is not None:
            values[field_name] = parsed_value

    imported_status = values.get("imported_booking_status")
    if imported_status is not None:
        values["normalised_status"] = normalise_booking_status(str(imported_status))

    element_flags = parse_elements(values.get("travel_elements_raw"))
    values.update(element_flags)
    values["atol_review_status"] = determine_atol_review_status(element_flags)
    return values


def booking_elements_from_response(root: ElementTree.Element) -> list[ElementTree.Element]:
    matches_by_reference: dict[str, ElementTree.Element] = {}
    for element in root.iter():
        if element is root:
            continue

        element_name = local_name(element.tag)
        flattened = flatten_xml(element, {})
        booking_ref = normalise_booking_ref(value_from_candidates(flattened, BOOKING_REF_CANDIDATES))
        if booking_ref and element_name in BOOKING_ELEMENT_NAMES:
            matches_by_reference.setdefault(booking_ref, element)

    if matches_by_reference:
        return list(matches_by_reference.values())

    flattened_root = flatten_xml(root, {})
    if value_from_candidates(flattened_root, BOOKING_REF_CANDIDATES):
        return [root]
    return []


def getbookings_attributes(start_date: date, end_date: date, date_type: str) -> dict[str, str]:
    attributes = {
        "datefrom": start_date.isoformat(),
        "dateto": end_date.isoformat(),
    }
    if date_type == "departure_date":
        attributes["datetype"] = "departuredate"
    return attributes


def sort_booking_elements(elements: list[ElementTree.Element], date_type: str) -> list[ElementTree.Element]:
    sort_field = "departure_date" if date_type == "departure_date" else "booking_date"

    def sort_key(element: ElementTree.Element) -> tuple[date, str]:
        values = extract_booking_values(flatten_xml(element, {}))
        date_value = values.get(sort_field)
        if isinstance(date_value, datetime):
            return date_value.date(), str(values.get("booking_ref") or "")
        if isinstance(date_value, date):
            return date_value, str(values.get("booking_ref") or "")
        return date.min, str(values.get("booking_ref") or "")

    return sorted(elements, key=sort_key, reverse=True)


def apply_booking_values_from_traveltek(
    db: Session,
    values: dict[str, Any],
) -> tuple[str, bool, bool]:
    booking_ref = values.get("booking_ref")
    if not booking_ref:
        raise ValueError("Traveltek booking did not include a booking reference.")

    writable_values = {
        key: value
        for key, value in values.items()
        if key != "booking_ref" and hasattr(Booking, key) and value is not None
    }
    booking = db.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
    if booking is None:
        db.add(Booking(booking_ref=booking_ref, **writable_values))
        return booking_ref, True, False

    changed = False
    for field_name, value in writable_values.items():
        if not values_are_equal(getattr(booking, field_name), value):
            setattr(booking, field_name, value)
            changed = True
    return booking_ref, False, changed


def import_traveltek_bookings_by_date_range(
    db: Session,
    start_date: date,
    end_date: date,
    date_type: str,
    limit: int,
    actor_user_id: int | None,
) -> TraveltekSyncRun:
    normalised_date_type = date_type if date_type in {"booking_date", "departure_date"} else "departure_date"
    run = TraveltekSyncRun(sync_type=f"booking_import_{normalised_date_type}", requested_by_user_id=actor_user_id)
    db.add(run)
    db.flush()

    if not settings.traveltek_api_configured:
        run.status = "failed"
        run.error_summary = "Traveltek API is not configured in Render yet."
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    max_limit = min(limit, settings.traveltek_max_calls_per_run)
    errors: list[str] = []
    created_count = 0
    updated_count = 0

    try:
        run.api_call_count += 1
        root = call_traveltek(
            "getbookings",
            getbookings_attributes(start_date, end_date, normalised_date_type),
        )
        booking_elements = sort_booking_elements(booking_elements_from_response(root), normalised_date_type)[:max_limit]
    except TraveltekApiError as exc:
        run.status = "failed"
        run.error_summary = str(exc)
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    for booking_element in booking_elements:
        flattened = flatten_xml(booking_element, {})
        values = extract_booking_values(flattened)
        booking_ref = values.get("booking_ref")
        if booking_ref:
            try:
                run.api_call_count += 1
                detail = fetch_booking_by_reference(booking_ref)
                values.update(detail.values)
            except TraveltekApiError as exc:
                errors.append(f"{booking_ref}: detail lookup failed, imported list data only. {exc}")

        try:
            imported_ref, created, changed = apply_booking_values_from_traveltek(db, values)
            run.checked_bookings += 1
            if created:
                created_count += 1
            elif changed:
                updated_count += 1
            db.add(
                AuditLog(
                    actor_user_id=actor_user_id,
                    action="traveltek_booking_import_row",
                    table_name="bookings",
                    record_id=None,
                    description=f"Traveltek booking import processed {imported_ref}.",
                    after_data={
                        "booking_ref": imported_ref,
                        "created": created,
                        "changed": changed,
                    },
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    run.proposals_created = created_count + updated_count
    if errors and run.checked_bookings == 0:
        run.status = "failed"
    elif errors:
        run.status = "completed_with_errors"
    else:
        run.status = "completed"
    run.error_summary = " ".join(errors[:5]) if errors else None
    run.finished_at = datetime.now(UTC)
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="traveltek_booking_import",
            table_name="traveltek_sync_runs",
            record_id=run.id,
            description=(
                f"Traveltek booking import created {created_count} booking(s), "
                f"updated {updated_count} booking(s), and checked {run.checked_bookings} booking(s)."
            ),
            after_data={
                "datefrom": start_date.isoformat(),
                "dateto": end_date.isoformat(),
                "date_type": normalised_date_type,
                "created": created_count,
                "updated": updated_count,
                "checked": run.checked_bookings,
                "api_calls": run.api_call_count,
            },
        )
    )
    db.commit()
    db.refresh(run)
    return run


def candidate_active_bookings(db: Session, limit: int) -> list[Booking]:
    today = date.today()
    statement = (
        select(Booking)
        .where(or_(Booking.normalised_status.is_(None), Booking.normalised_status.not_in(("cancelled", "completed"))))
        .where((Booking.departure_date.is_(None)) | (Booking.departure_date >= today))
        .order_by(Booking.departure_date.asc().nullslast(), Booking.updated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement))


def create_update_proposal(
    db: Session,
    run: TraveltekSyncRun,
    booking: Booking,
    field_name: str,
    current_value: Any,
    traveltek_value: Any,
    source: dict[str, Any],
) -> bool:
    existing_open = db.scalar(
        select(TraveltekBookingUpdate).where(
            TraveltekBookingUpdate.booking_ref == booking.booking_ref,
            TraveltekBookingUpdate.field_name == field_name,
            TraveltekBookingUpdate.status.in_(("open", "reviewing")),
        )
    )
    if existing_open is not None:
        existing_open.current_value = display_value(current_value)
        existing_open.traveltek_value = display_value(traveltek_value)
        existing_open.sync_run_id = run.id
        existing_open.raw_source = source
        return False

    db.add(
        TraveltekBookingUpdate(
            sync_run_id=run.id,
            booking_id=booking.id,
            booking_ref=booking.booking_ref,
            field_name=field_name,
            field_label=FIELD_DEFINITIONS[field_name]["label"],
            current_value=display_value(current_value),
            traveltek_value=display_value(traveltek_value),
            raw_source=source,
        )
    )
    return True


def scan_active_bookings_for_traveltek_updates(
    db: Session,
    limit: int,
    actor_user_id: int | None,
) -> TraveltekSyncRun:
    run = TraveltekSyncRun(requested_by_user_id=actor_user_id)
    db.add(run)
    db.flush()

    if not settings.traveltek_api_configured:
        run.status = "failed"
        run.error_summary = "Traveltek API is not configured in Render yet."
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    errors: list[str] = []
    created_count = 0
    max_limit = min(limit, settings.traveltek_max_calls_per_run)
    bookings = candidate_active_bookings(db, max_limit)

    for booking in bookings:
        try:
            run.api_call_count += 1
            traveltek_booking = fetch_booking_by_reference(booking.booking_ref)
            run.checked_bookings += 1

            for field_name, traveltek_value in traveltek_booking.values.items():
                current_value = getattr(booking, field_name)
                if field_name == "imported_booking_status":
                    current_value = booking.imported_booking_status or booking.normalised_status
                    if values_are_equal(normalise_booking_status(current_value), normalise_booking_status(traveltek_value)):
                        continue
                elif values_are_equal(current_value, traveltek_value):
                    continue

                if create_update_proposal(
                    db=db,
                    run=run,
                    booking=booking,
                    field_name=field_name,
                    current_value=current_value,
                    traveltek_value=traveltek_value,
                    source=traveltek_booking.source,
                ):
                    created_count += 1
        except TraveltekApiError as exc:
            errors.append(f"{booking.booking_ref}: {exc}")
        except Exception as exc:
            errors.append(f"{booking.booking_ref}: {exc}")

    run.proposals_created = created_count
    if errors and run.checked_bookings == 0:
        run.status = "failed"
    elif errors:
        run.status = "completed_with_errors"
    else:
        run.status = "completed"
    run.error_summary = " ".join(errors[:5]) if errors else None
    run.finished_at = datetime.now(UTC)
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="traveltek_active_booking_check",
            table_name="traveltek_sync_runs",
            record_id=run.id,
            description=(
                f"Traveltek check scanned {run.checked_bookings} booking(s), "
                f"used {run.api_call_count} API call(s), and created {created_count} update suggestion(s)."
            ),
        )
    )
    db.commit()
    db.refresh(run)
    return run
