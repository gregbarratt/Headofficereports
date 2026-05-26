from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reporting import AuditLog, Booking, Setting, TraveltekBookingUpdate, TraveltekSyncRun
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


FIELD_DEFINITIONS = {
    "imported_booking_status": {
        "label": "Booking status",
        "candidates": ("status", "bookingstatus", "booking_status"),
        "parser": "status",
    },
    "customer_last_name": {
        "label": "Customer / lead name",
        "candidates": (
            "leadname",
            "leadpassenger",
            "leadpassengername",
            "customername",
            "customerlastname",
            "lastname",
            "last_name",
            "surname",
        ),
        "parser": "text",
    },
    "destination": {
        "label": "Destination",
        "candidates": ("destination", "resort", "region", "location"),
        "parser": "text",
    },
    "supplier_references_raw": {
        "label": "Supplier references",
        "candidates": (
            "supplierreference",
            "supplier_reference",
            "supplierref",
            "supplier_ref",
            "supplierbookingreference",
            "supplier_booking_reference",
            "supplierbookingref",
            "supplier_booking_ref",
            "supplierlocator",
            "supplier_locator",
            "supplierconfirmation",
            "supplier_confirmation",
            "providerreference",
            "provider_reference",
            "providerref",
            "provider_ref",
        ),
        "parser": "text",
    },
    "departure_date": {
        "label": "Departure date",
        "candidates": ("departuredate", "departdate", "depdate", "startdate"),
        "parser": "date",
    },
    "return_date": {
        "label": "Return date",
        "candidates": (
            "returndate",
            "returneddate",
            "retdate",
            "returningdate",
            "dateback",
            "dateofreturn",
            "holidayenddate",
            "enddate",
            "todate",
            "arrivaldate",
            "checkoutdate",
            "check_out_date",
        ),
        "parser": "date",
    },
    "passenger_count": {
        "label": "Passenger count",
        "candidates": (
            "pax",
            "paxcount",
            "passengercount",
            "passengers",
            "totalpax",
            "totalpassengers",
            "passengertotal",
            "numberofpassengers",
            "noofpassengers",
            "numberofpax",
            "noofpax",
        ),
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
        "label": "Traveltek customer outstanding",
        "candidates": (
            "outstanding",
            "customeroutstanding",
            "customer_outstanding",
            "balancedue",
            "balance_due",
            "customerbalancedue",
            "customer_balance_due",
        ),
        "parser": "money",
    },
    "imported_supplier_outstanding": {
        "label": "Traveltek due to suppliers",
        "candidates": (
            "duetosuppliers",
            "due_to_suppliers",
            "duetosupplier",
            "supplierdue",
            "supplieroutstanding",
            "supplierbalancedue",
            "outstandingsupplier",
            "outstanding_supplier",
            "totalsupplierdue",
            "total_supplier_due",
            "supplierstotaldue",
            "suppliers_total_due",
        ),
        "parser": "money",
    },
    "non_trusted_total_due": {
        "label": "Traveltek total due",
        "candidates": ("totaldue", "total_due", "totalduetosupplier", "supplierstotaldue", "suppliertotaldue"),
        "parser": "money",
    },
    "non_trusted_total_received": {
        "label": "Traveltek total amount paid",
        "candidates": (
            "totalamountpaid",
            "total_amount_paid",
            "amountpaid",
            "amount_paid",
            "totalpaid",
            "totalreceived",
            "customerpaid",
            "customer_paid",
            "paid",
        ),
        "parser": "money",
    },
    "non_trusted_paid_supplier": {
        "label": "Traveltek paid to supplier",
        "candidates": (
            "paidtosupplier",
            "paid_to_supplier",
            "paidtosuppliers",
            "paid_to_suppliers",
            "paidsupplier",
            "paidsuppliers",
            "paidsupp",
            "paidtosupp",
            "supplierpaid",
            "supplier_paid",
            "supplierspaid",
            "suppliers_paid",
            "supplierpaidtotal",
            "supplier_paid_total",
            "totalsupplierpaid",
            "total_supplier_paid",
            "supplierstotalpaid",
            "suppliers_total_paid",
            "supplierpayment",
            "supplierpayments",
            "supplierpaymentsmade",
        ),
        "parser": "money",
    },
    "non_trusted_projected_profit": {
        "label": "Traveltek profit",
        "candidates": ("profitprojected", "projectedprofit", "profit", "margin"),
        "parser": "money",
    },
    "gross_booking_value": {
        "label": "Traveltek total cost",
        "candidates": (
            "totalcost",
            "total_cost",
            "holidayprice",
            "holiday_price",
            "totalprice",
            "totalsell",
            "totalvalue",
            "gross",
        ),
        "parser": "money",
    },
    "expected_supplier_nett": {
        "label": "Traveltek expected supplier cost",
        "candidates": ("nett", "nettcost", "suppliernett", "suppliercost", "totaldue", "total_due"),
        "parser": "money",
    },
}
TRAVELTEK_OVERVIEW_MONEY_KEYS = {
    "totalcost",
    "holidayprice",
    "totalamountpaid",
    "outstanding",
    "totaldue",
    "duetosuppliers",
    "duetosupplier",
    "paidtosupplier",
    "paidtosuppliers",
    "profit",
    "vat",
    "refund",
    "currencylossgain",
}
TRAVELTEK_EXACT_MONEY_KEYS = {
    "gross_booking_value": ("totalcost", "holidayprice"),
    "non_trusted_total_received": ("totalamountpaid",),
    "imported_customer_outstanding": ("outstanding",),
    "non_trusted_total_due": ("totaldue",),
    "imported_supplier_outstanding": ("duetosuppliers", "duetosupplier"),
    "non_trusted_paid_supplier": ("paidtosupplier", "paidtosuppliers"),
}
TRAVELTEK_TEXT_MONEY_LABELS = {
    "gross_booking_value": ("Total Cost", "Holiday Price"),
    "non_trusted_total_received": ("Total Amount Paid",),
    "imported_customer_outstanding": ("Outstanding",),
    "non_trusted_total_due": ("Total Due",),
    "imported_supplier_outstanding": ("Due to Suppliers", "Due to Supplier"),
    "non_trusted_paid_supplier": ("Paid To Supplier", "Paid To Suppliers"),
    "non_trusted_projected_profit": ("Profit",),
}
TRAVELTEK_SUPPLIER_PAID_LINE_KEYS = (
    "paidtosupplier",
    "paidtosuppliers",
    "paidsupplier",
    "paidsuppliers",
    "supplierpaid",
    "supplierspaid",
    "supplierpayment",
    "supplierpayments",
    "supplierpaymentsmade",
)
TRAVELTEK_SUPPLIER_PAYMENT_ROW_NAMES = {
    "supplierpayment",
    "supplierpayments",
    "supplierpaymentrow",
    "suppliertransaction",
    "suppliertransactions",
    "payment",
    "paymentrow",
    "transaction",
    "item",
    "detail",
    "record",
    "entry",
    "row",
}
TRAVELTEK_SUPPLIER_PAYMENT_AMOUNT_KEYS = {
    "amount",
    "value",
    "paymentamount",
    "paymentvalue",
    "paidamount",
    "paidvalue",
    "collected",
    "total",
}
TRAVELTEK_SUPPLIER_PAYMENT_AMOUNT_EXCLUDES = {
    "balance",
    "charge",
    "date",
    "due",
    "fee",
    "id",
    "outstanding",
    "ref",
    "reference",
    "tax",
    "vat",
}
TRAVELTEK_SUPPLIER_PAYMENT_FAILED_WORDS = {
    "cancelled",
    "canceled",
    "failed",
    "notpaid",
    "not paid",
    "rejected",
    "void",
}
AUTO_APPLY_FIELD_NAMES = {
    "return_date",
    "passenger_count",
    "imported_customer_outstanding",
    "imported_supplier_outstanding",
    "non_trusted_total_due",
    "non_trusted_total_received",
    "non_trusted_paid_supplier",
}
REVIEW_FIELD_NAMES = set(FIELD_DEFINITIONS) - AUTO_APPLY_FIELD_NAMES - {"non_trusted_projected_profit"}
BOOKING_REFERENCE_CANDIDATES = (
    "bookingreference",
    "bookingref",
    "booking_ref",
    "reference",
)
EXTERNAL_REFERENCE_CANDIDATES = ("externalreference", "externalref")
BOOKING_ID_CANDIDATES = ("bookingid", "booking_id")
BOOKING_REF_CANDIDATES = BOOKING_REFERENCE_CANDIDATES + EXTERNAL_REFERENCE_CANDIDATES
BOOKING_ELEMENT_NAMES = {"booking", "portfolio", "enquiry", "item", "row", "result"}
FULL_CATCHUP_CURSOR_KEY = "traveltek_full_catchup_cursor_date"
FULL_CATCHUP_END_KEY = "traveltek_full_catchup_end_date"
UPDATE_EVERYTHING_CURSOR_KEY = "traveltek_update_everything_cursor_ref"
SUPPLIER_REFERENCE_KEYS = {
    "supplierreference",
    "supplierref",
    "supplierbookingreference",
    "supplierbookingref",
    "supplierbookingid",
    "supplierlocator",
    "supplierconfirmation",
    "supplierconfirmationreference",
    "providerreference",
    "providerref",
}
RETURN_DATE_KEY_HINTS = {
    "returndate",
    "returneddate",
    "retdate",
    "returningdate",
    "dateback",
    "dateofreturn",
    "holidayenddate",
    "enddate",
    "todate",
    "arrivaldate",
    "checkoutdate",
    "checkout",
}
RETURN_DATE_EXCLUDED_KEY_HINTS = {
    "birth",
    "booked",
    "booking",
    "created",
    "customerbalance",
    "deposit",
    "due",
    "method",
    "payment",
    "request",
    "startdate",
    "supplier",
}
PASSENGER_TOTAL_KEYS = {
    "pax",
    "paxcount",
    "passengercount",
    "passengers",
    "totalpax",
    "totalpassengers",
    "passengertotal",
    "numberofpassengers",
    "noofpassengers",
    "numberofpax",
    "noofpax",
}
PASSENGER_PART_KEYS = {
    "adult",
    "adults",
    "adultcount",
    "numberofadults",
    "noofadults",
    "children",
    "child",
    "childcount",
    "numberofchildren",
    "noofchildren",
    "infant",
    "infants",
    "infantcount",
    "numberofinfants",
    "noofinfants",
}
PASSENGER_ROW_NAMES = {"passenger", "passengerrow", "passengerdetail", "pax", "paxrow"}
PASSENGER_CONTAINER_NAMES = {"passengers", "passengerlist", "passengerdetails", "paxlist"}
PASSENGER_PERSON_KEYS = {
    "firstname",
    "forename",
    "lastname",
    "surname",
    "passengername",
    "name",
    "title",
    "dob",
    "dateofbirth",
    "lead",
    "passengertype",
    "type",
}


@dataclass
class TraveltekBookingData:
    values: dict[str, Any]
    source: dict[str, Any]


class TraveltekConfigurationError(RuntimeError):
    pass


class TraveltekApiError(RuntimeError):
    pass


def redact_sensitive_text(value: str) -> str:
    redacted = re.sub(r"(password\s*[=:]\s*)[^,\s|<>]+", r"\1[redacted]", value, flags=re.IGNORECASE)
    redacted = re.sub(r"(username\s*[=:]\s*)[^,\s|<>]+", r"\1[redacted]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(<auth\b[^>]*\bpassword=\")[^\"]+", r"\1[redacted]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(<auth\b[^>]*\busername=\")[^\"]+", r"\1[redacted]", redacted, flags=re.IGNORECASE)
    return redacted


def format_date_for_traveltek(value: date, style: str) -> str:
    if style == "uk":
        return value.strftime("%d/%m/%Y")
    return value.isoformat()


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


def direct_text(element: ElementTree.Element) -> str | None:
    text = "".join(element.itertext()).strip()
    return re.sub(r"\s+", " ", text) if text else None


def first_present(values: dict[str, str], candidate_keys: tuple[str, ...]) -> str | None:
    for key in candidate_keys:
        value = values.get(key)
        if value not in {None, ""}:
            return value
    return None


def collect_label_value_pairs(element: ElementTree.Element, output: dict[str, str] | None = None) -> dict[str, str]:
    if output is None:
        output = {}

    label_keys = ("label", "name", "field", "key", "title", "caption", "description")
    value_keys = ("value", "amount", "total", "cost", "price", "balance", "paid", "due", "text")

    attributes = {normalise_key(key): str(value).strip() for key, value in element.attrib.items() if str(value).strip()}
    label = first_present(attributes, label_keys)
    value = first_present(attributes, value_keys)
    if label and not value:
        value = direct_text(element)
    if label and value and len(label) <= 120 and len(value) <= 160 and normalise_key(label) != normalise_key(value):
        set_label_value(output, label, value)

    child_values = {
        normalise_key(local_name(child.tag)): direct_text(child) or ""
        for child in element
        if direct_text(child)
    }
    child_label = first_present(child_values, label_keys)
    child_value = first_present(child_values, value_keys)
    if (
        child_label
        and child_value
        and len(child_label) <= 120
        and len(child_value) <= 160
        and normalise_key(child_label) != normalise_key(child_value)
    ):
        set_label_value(output, child_label, child_value)

    row_texts = [direct_text(child) for child in element if direct_text(child)]
    row_texts = [text for text in row_texts if text]
    for index in range(0, len(row_texts) - 1, 2):
        possible_label = row_texts[index]
        possible_value = row_texts[index + 1]
        if (
            possible_label
            and possible_value
            and len(possible_label) <= 120
            and len(possible_value) <= 160
            and not re.search(r"\d{2,}[/.-]\d{1,2}[/.-]\d{2,4}", possible_label)
        ):
            set_label_value(output, possible_label, possible_value)

    for child in element:
        collect_label_value_pairs(child, output)

    return output


def set_label_value(output: dict[str, str], label: str, value: str) -> None:
    key = normalise_key(label)
    if key in TRAVELTEK_OVERVIEW_MONEY_KEYS and key in output:
        try:
            current_amount = parse_money(output[key])
            next_amount = parse_money(value)
        except ValueError:
            current_amount = None
            next_amount = None
        if current_amount is not None and next_amount is not None:
            if abs(next_amount) > abs(current_amount):
                output[key] = value
            return
    output.setdefault(key, value)


def looks_like_supplier_reference_key(key: str) -> bool:
    normalised = normalise_key(key)
    if normalised in SUPPLIER_REFERENCE_KEYS:
        return True
    return "supplier" in normalised and (
        "ref" in normalised
        or "reference" in normalised
        or "locator" in normalised
        or "confirmation" in normalised
        or "bookingid" in normalised
    )


def looks_like_supplier_reference_value(value: str | None) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 120:
        return False
    if text.lower() in {"yes", "no", "true", "false", "supplier", "reference", "n/a", "none"}:
        return False
    return bool(re.search(r"[A-Za-z0-9]", text))


def collect_supplier_references(element: ElementTree.Element, flattened: dict[str, str] | None = None) -> list[str]:
    references: list[str] = []

    def add_reference(value: str | None) -> None:
        text = (value or "").strip()
        if looks_like_supplier_reference_value(text) and text not in references:
            references.append(text)

    flattened_values = flattened or flatten_xml(element, {})
    for key, value in flattened_values.items():
        if looks_like_supplier_reference_key(key):
            add_reference(value)

    for next_element in element.iter():
        element_name = local_name(next_element.tag)
        if looks_like_supplier_reference_key(element_name):
            add_reference(direct_text(next_element))
        for attr_name, attr_value in next_element.attrib.items():
            if looks_like_supplier_reference_key(attr_name):
                add_reference(attr_value)

    return references[:20]


def flatten_xml(element: ElementTree.Element, output: dict[str, str] | None = None) -> dict[str, str]:
    top_level = output is None
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

    if top_level:
        for key, value in collect_label_value_pairs(element).items():
            if key in TRAVELTEK_OVERVIEW_MONEY_KEYS:
                set_label_value(output, key, value)
            else:
                output.setdefault(key, value)

    return output


def value_from_candidates(flattened: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    normalised = {normalise_key(key): value for key, value in flattened.items() if value not in {None, ""}}
    for candidate in candidates:
        value = normalised.get(normalise_key(candidate))
        if value not in {None, ""}:
            return value
    return None


FINANCIAL_KEY_EXCLUDES = {
    "bookingid",
    "bookingref",
    "confirmation",
    "date",
    "method",
    "name",
    "reference",
    "ref",
    "status",
}


def derive_money_from_key_hints(
    flattened: dict[str, str],
    required_terms: tuple[str, ...],
    any_terms: tuple[str, ...] = (),
) -> Decimal | None:
    for key, value in flattened.items():
        normalised_key = normalise_key(key)
        if any(excluded in normalised_key for excluded in FINANCIAL_KEY_EXCLUDES):
            continue
        if not all(term in normalised_key for term in required_terms):
            continue
        if any_terms and not any(term in normalised_key for term in any_terms):
            continue
        try:
            amount = parse_money(value)
        except ValueError:
            continue
        if amount is not None:
            return amount
    return None


def money_from_exact_keys(flattened: dict[str, str], candidate_keys: tuple[str, ...]) -> Decimal | None:
    normalised = {normalise_key(key): value for key, value in flattened.items() if value not in {None, ""}}
    for candidate in candidate_keys:
        value = normalised.get(normalise_key(candidate))
        if value in {None, ""}:
            continue
        try:
            amount = parse_money(value)
        except ValueError:
            continue
        if amount is not None:
            return amount
    return None


def money_from_text_labels(root: ElementTree.Element | None, labels: tuple[str, ...]) -> Decimal | None:
    if root is None:
        return None
    text = direct_text(root) or ""
    if not text:
        return None
    for label in labels:
        pattern = re.compile(
            rf"{re.escape(label)}[^\d£?()-]{{0,80}}(?:£|\?)?\s*(\(?-?\d[\d,]*(?:\.\d{{2}})?\)?)",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            continue
        try:
            amount = parse_money(match.group(1))
        except ValueError:
            continue
        if amount is not None:
            return amount
    return None


def largest_money_value(values: list[Decimal | None]) -> Decimal | None:
    valid_values = [value for value in values if value is not None]
    if not valid_values:
        return None
    return max(valid_values, key=lambda amount: abs(amount)).quantize(Decimal("0.01"))


def money_values_from_text_labels(root: ElementTree.Element | None, labels: tuple[str, ...]) -> list[Decimal]:
    if root is None:
        return []
    text = direct_text(root) or ""
    if not text:
        return []
    values: list[Decimal] = []
    for label in labels:
        pattern = re.compile(
            rf"{re.escape(label)}[^\dÂ£?()-]{{0,80}}(?:Â£|\?)?\s*(\(?-?\d[\d,]*(?:\.\d{{2}})?\)?)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            try:
                amount = parse_money(match.group(1))
            except ValueError:
                continue
            if amount is not None:
                values.append(amount)
    return values


def money_values_from_xml_keys(root: ElementTree.Element | None, candidate_keys: tuple[str, ...]) -> list[Decimal]:
    if root is None:
        return []
    normalised_candidates = {normalise_key(key) for key in candidate_keys}
    values: list[Decimal] = []

    def add_money(value: str | None) -> None:
        if value in {None, ""}:
            return
        try:
            amount = parse_money(value)
        except ValueError:
            return
        if amount is not None:
            values.append(amount)

    for element in root.iter():
        element_key = normalise_key(local_name(element.tag))
        if element_key in normalised_candidates:
            add_money((element.text or "").strip())
        for attr_name, attr_value in element.attrib.items():
            if normalise_key(attr_name) in normalised_candidates:
                add_money(str(attr_value).strip())

    return values


def direct_child_values(element: ElementTree.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for attr_name, attr_value in element.attrib.items():
        text = str(attr_value).strip()
        if text:
            values.setdefault(normalise_key(attr_name), text)
    for child in element:
        text = direct_text(child)
        if text:
            values.setdefault(normalise_key(local_name(child.tag)), text)
        for attr_name, attr_value in child.attrib.items():
            attr_text = str(attr_value).strip()
            if attr_text:
                values.setdefault(normalise_key(attr_name), attr_text)
    return values


def has_nested_payment_rows(element: ElementTree.Element) -> bool:
    for child in element:
        child_name = normalise_key(local_name(child.tag))
        if child_name in TRAVELTEK_SUPPLIER_PAYMENT_ROW_NAMES:
            return True
    return False


def row_text_blob(element_name: str, child_values: dict[str, str]) -> str:
    return " ".join([element_name, *child_values.keys(), *child_values.values()]).lower()


def row_is_failed_payment(text_blob: str) -> bool:
    normalised_blob = normalise_key(text_blob)
    return any(word in text_blob or normalise_key(word) in normalised_blob for word in TRAVELTEK_SUPPLIER_PAYMENT_FAILED_WORDS)


def row_looks_like_supplier_payment(element_name: str, child_values: dict[str, str]) -> bool:
    text_blob = row_text_blob(element_name, child_values)
    if row_is_failed_payment(text_blob):
        return False
    normalised_blob = normalise_key(text_blob)
    if element_name in {
        "supplierpayment",
        "supplierpayments",
        "supplierpaymentrow",
        "suppliertransaction",
        "suppliertransactions",
    }:
        return True
    return "supplier" in normalised_blob and ("payment" in normalised_blob or "paid" in normalised_blob)


def money_values_from_supplier_payment_rows(root: ElementTree.Element | None) -> list[Decimal]:
    if root is None:
        return []

    values: list[Decimal] = []
    for element in root.iter():
        element_name = normalise_key(local_name(element.tag))
        if element_name not in TRAVELTEK_SUPPLIER_PAYMENT_ROW_NAMES:
            continue
        if has_nested_payment_rows(element):
            continue

        child_values = direct_child_values(element)
        if not row_looks_like_supplier_payment(element_name, child_values):
            continue

        amount_options: list[Decimal] = []
        for key, value in child_values.items():
            if any(excluded in key for excluded in TRAVELTEK_SUPPLIER_PAYMENT_AMOUNT_EXCLUDES):
                continue
            if key not in TRAVELTEK_SUPPLIER_PAYMENT_AMOUNT_KEYS and not (
                "amount" in key or "value" in key or "paid" in key or "collected" in key
            ):
                continue
            try:
                amount = parse_money(value)
            except ValueError:
                continue
            if amount is not None and amount > Decimal("0.00"):
                amount_options.append(amount)

        if not amount_options and element_name in TRAVELTEK_SUPPLIER_PAID_LINE_KEYS:
            try:
                amount = parse_money(direct_text(element))
            except ValueError:
                amount = None
            if amount is not None and amount > Decimal("0.00"):
                amount_options.append(amount)

        if amount_options:
            values.append(max(amount_options, key=lambda amount: abs(amount)).quantize(Decimal("0.01")))

    return values


def supplier_paid_total_from_lines(flattened: dict[str, str], root: ElementTree.Element | None) -> Decimal | None:
    row_values = money_values_from_supplier_payment_rows(root)
    exact_values = money_values_from_xml_keys(root, TRAVELTEK_SUPPLIER_PAID_LINE_KEYS)
    line_values = row_values if row_values else exact_values
    if not line_values:
        return None
    total = sum(line_values, Decimal("0.00")).quantize(Decimal("0.01"))
    total_due = money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS["non_trusted_total_due"])
    if total_due is not None and total > total_due + Decimal("0.01"):
        under_total_due = [value for value in line_values if value <= total_due]
        return max(under_total_due).quantize(Decimal("0.01")) if under_total_due else None
    return total


def serialise_money(value: Decimal | None) -> str | None:
    return str(value.quantize(Decimal("0.01"))) if value is not None else None


def serialise_money_values(values: list[Decimal]) -> list[str]:
    return [serialise_money(value) or "" for value in values]


def traveltek_finance_diagnostics(flattened: dict[str, str], root: ElementTree.Element | None) -> dict[str, Any]:
    overview_pairs = collect_label_value_pairs(root) if root is not None else {}
    exact_paid_values = money_values_from_xml_keys(root, TRAVELTEK_SUPPLIER_PAID_LINE_KEYS)
    supplier_payment_row_values = money_values_from_supplier_payment_rows(root)
    supplier_payment_row_total = (
        sum(supplier_payment_row_values, Decimal("0.00")).quantize(Decimal("0.01"))
        if supplier_payment_row_values
        else None
    )

    return {
        "financial_details_paid_to_supplier": serialise_money(
            money_from_exact_keys(overview_pairs, TRAVELTEK_EXACT_MONEY_KEYS["non_trusted_paid_supplier"])
        ),
        "financial_details_due_to_suppliers": serialise_money(
            money_from_exact_keys(overview_pairs, TRAVELTEK_EXACT_MONEY_KEYS["imported_supplier_outstanding"])
        ),
        "traveltek_total_due": serialise_money(
            money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS["non_trusted_total_due"])
        ),
        "exact_paid_to_supplier_values": serialise_money_values(exact_paid_values),
        "text_paid_to_supplier_values": serialise_money_values(
            money_values_from_text_labels(root, TRAVELTEK_TEXT_MONEY_LABELS["non_trusted_paid_supplier"])
        ),
        "supplier_payment_row_values": serialise_money_values(supplier_payment_row_values),
        "supplier_payment_row_count": len(supplier_payment_row_values),
        "supplier_payment_row_total": serialise_money(supplier_payment_row_total),
        "derived_paid_to_supplier": serialise_money(derive_paid_supplier_from_traveltek_totals(flattened)),
    }


def derive_paid_supplier_from_traveltek_totals(flattened: dict[str, str]) -> Decimal | None:
    total_due = money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS["non_trusted_total_due"])
    due_to_suppliers = money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS["imported_supplier_outstanding"])
    if total_due is None or due_to_suppliers is None:
        return None
    paid_to_supplier = (total_due - due_to_suppliers).quantize(Decimal("0.01"))
    return paid_to_supplier if paid_to_supplier >= Decimal("0.00") else None


def derive_traveltek_money_value(
    field_name: str,
    flattened: dict[str, str],
    root: ElementTree.Element | None = None,
) -> Decimal | None:
    exact_amount = money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS.get(field_name, ()))
    if field_name == "non_trusted_paid_supplier":
        paid_from_lines = supplier_paid_total_from_lines(flattened, root)
        derived_from_totals = derive_paid_supplier_from_traveltek_totals(flattened)
        hinted_amount = derive_money_from_key_hints(flattened, ("supplier", "paid", "total"))
        best_paid_amount = largest_money_value([exact_amount, paid_from_lines, hinted_amount])
        if best_paid_amount is not None:
            return best_paid_amount
        if derived_from_totals is not None:
            return derived_from_totals
    if field_name == "imported_supplier_outstanding":
        total_due = money_from_exact_keys(flattened, TRAVELTEK_EXACT_MONEY_KEYS["non_trusted_total_due"])
        paid_to_supplier = derive_traveltek_money_value("non_trusted_paid_supplier", flattened, root)
        derived_due = None
        if total_due is not None and paid_to_supplier is not None and total_due >= paid_to_supplier:
            derived_due = (total_due - paid_to_supplier).quantize(Decimal("0.01"))
        hinted_due = derive_money_from_key_hints(flattened, ("supplier", "due"))
        best_due_amount = largest_money_value([exact_amount, derived_due, hinted_due])
        if best_due_amount is not None:
            return best_due_amount

    labelled_amount = money_from_text_labels(root, TRAVELTEK_TEXT_MONEY_LABELS.get(field_name, ()))
    if labelled_amount is not None:
        return labelled_amount

    if exact_amount is not None:
        return exact_amount
    return None


def parse_traveltek_value(value: str | None, parser: str) -> Any:
    if value is None:
        return None
    if parser == "money":
        return parse_money(value)
    if parser == "date":
        try:
            return parse_date(value)
        except ValueError:
            text = str(value).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(text).date()
    if parser == "datetime":
        try:
            return parse_datetime(value)
        except ValueError:
            text = str(value).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(text)
    if parser == "int":
        return parse_int(value)
    if parser == "status":
        return value.strip()
    return value.strip() or None


def parse_optional_traveltek_date(value: str | None) -> date | None:
    try:
        parsed = parse_traveltek_value(value, "date")
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, date) else None


def parse_optional_traveltek_int(value: str | None) -> int | None:
    try:
        parsed = parse_traveltek_value(value, "int")
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, int) else None


def derive_return_date(flattened: dict[str, str], departure_date: date | None) -> date | None:
    candidates: list[date] = []
    for key, value in flattened.items():
        normalised_key = normalise_key(key)
        if not any(hint in normalised_key for hint in RETURN_DATE_KEY_HINTS):
            continue
        if any(hint in normalised_key for hint in RETURN_DATE_EXCLUDED_KEY_HINTS):
            continue

        parsed_date = parse_optional_traveltek_date(value)
        if parsed_date is None:
            continue
        if departure_date and parsed_date < departure_date:
            continue
        candidates.append(parsed_date)

    if not candidates:
        return None
    return max(candidates)


def derive_passenger_count_from_values(flattened: dict[str, str]) -> int | None:
    normalised_values = {
        normalise_key(key): value
        for key, value in flattened.items()
        if value not in {None, ""}
    }

    for key in PASSENGER_TOTAL_KEYS:
        parsed_value = parse_optional_traveltek_int(normalised_values.get(key))
        if is_plausible_traveltek_value("passenger_count", parsed_value):
            return parsed_value

    passenger_parts: list[int] = []
    for key, value in normalised_values.items():
        if key not in PASSENGER_PART_KEYS:
            continue
        parsed_value = parse_optional_traveltek_int(value)
        if parsed_value is not None and 0 <= parsed_value <= 99:
            passenger_parts.append(parsed_value)

    total = sum(passenger_parts)
    if passenger_parts and is_plausible_traveltek_value("passenger_count", total):
        return total
    return None


def element_has_nested_passenger_rows(element: ElementTree.Element) -> bool:
    for child in element.iter():
        if child is element:
            continue
        child_name = normalise_key(local_name(child.tag))
        if child_name in PASSENGER_ROW_NAMES:
            return True
    return False


def element_looks_like_passenger_row(element: ElementTree.Element) -> bool:
    element_name = normalise_key(local_name(element.tag))
    if element_name in PASSENGER_CONTAINER_NAMES:
        return False
    if element_name not in PASSENGER_ROW_NAMES and "passenger" not in element_name:
        return False
    if element_has_nested_passenger_rows(element):
        return False

    flattened = flatten_xml(element, {})
    element_keys = {normalise_key(key) for key in element.attrib}
    element_keys.update(normalise_key(key) for key in flattened)
    element_keys.update(normalise_key(local_name(child.tag)) for child in element)
    if element_keys.intersection(PASSENGER_PERSON_KEYS):
        return True

    text = direct_text(element)
    return element_name in {"passenger", "pax"} and bool(text and any(character.isalpha() for character in text))


def derive_passenger_count_from_xml(root: ElementTree.Element | None) -> int | None:
    if root is None:
        return None

    count = sum(1 for element in root.iter() if element_looks_like_passenger_row(element))
    if is_plausible_traveltek_value("passenger_count", count):
        return count
    return None


def derive_passenger_count(flattened: dict[str, str], root: ElementTree.Element | None) -> int | None:
    return derive_passenger_count_from_values(flattened) or derive_passenger_count_from_xml(root)


def is_plausible_traveltek_value(field_name: str, value: Any) -> bool:
    if value is None:
        return False

    if field_name == "passenger_count":
        return isinstance(value, int) and 0 < value <= 99

    if field_name == "customer_last_name":
        return str(value).strip().upper() not in {"Y", "N", "YES", "NO", "TRUE", "FALSE", "0", "1"}

    if field_name == "supplier_references_raw":
        return bool(str(value).strip()) and len(str(value).strip()) <= 1000

    return True


def is_valid_traveltek_update_value(field_name: str, raw_value: str | None) -> bool:
    if field_name not in REVIEW_FIELD_NAMES:
        return False

    definition = FIELD_DEFINITIONS[field_name]
    try:
        parsed_value = parse_traveltek_value(raw_value, definition["parser"])
    except ValueError:
        return False
    return is_plausible_traveltek_value(field_name, parsed_value)


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


def traveltek_field_label(field_name: str) -> str:
    if field_name == "normalised_status":
        return "Normalised booking status"
    return FIELD_DEFINITIONS.get(field_name, {}).get("label") or field_name.replace("_", " ").title()


def classify_traveltek_booking_change(changes: list[dict[str, str | None]], created: bool = False) -> str:
    if created:
        return "created"
    for change in changes:
        field_name = change.get("field_name")
        next_value = str(change.get("new_value") or "").strip().lower()
        if field_name in {"normalised_status", "imported_booking_status"} and "cancel" in next_value:
            return "cancelled"
    changed_fields = {str(change.get("field_name") or "") for change in changes}
    if "non_trusted_total_received" in changed_fields:
        return "customer_payment_changed"
    if "gross_booking_value" in changed_fields:
        return "gross_value_changed"
    if "non_trusted_paid_supplier" in changed_fields:
        return "supplier_payment_changed"
    if "imported_customer_outstanding" in changed_fields or "non_trusted_total_due" in changed_fields:
        return "customer_balance_changed"
    if "imported_supplier_outstanding" in changed_fields or "expected_supplier_nett" in changed_fields:
        return "supplier_balance_changed"
    return "changed"


def change_type_label(change_type: str) -> str:
    labels = {
        "created": "New booking created from Traveltek",
        "cancelled": "Booking cancelled in Traveltek",
        "customer_payment_changed": "Customer payment changed in Traveltek",
        "gross_value_changed": "Gross booking value changed in Traveltek",
        "supplier_payment_changed": "Supplier payment changed in Traveltek",
        "customer_balance_changed": "Customer balance changed in Traveltek",
        "supplier_balance_changed": "Supplier balance changed in Traveltek",
        "changed": "Booking changed in Traveltek",
    }
    return labels.get(change_type, "Booking changed in Traveltek")


def add_traveltek_booking_change_log(
    db: Session,
    booking_ref: str,
    booking_id: int | None,
    sync_run_id: int | None,
    changes: list[dict[str, str | None]],
    created: bool,
    actor_user_id: int | None,
) -> None:
    if not changes and not created:
        return

    change_type = classify_traveltek_booking_change(changes, created)
    changed_fields = [str(change.get("field_label") or change.get("field_name")) for change in changes]
    description = f"{booking_ref}: {change_type_label(change_type)}."
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=f"traveltek_booking_{change_type if change_type in {'created', 'cancelled'} else 'changed'}",
            table_name="bookings",
            record_id=booking_id,
            description=description,
            before_data={
                "booking_ref": booking_ref,
                "changes": [
                    {
                        "field_name": change.get("field_name"),
                        "field_label": change.get("field_label"),
                        "previous_value": change.get("previous_value"),
                    }
                    for change in changes
                ],
            },
            after_data={
                "booking_ref": booking_ref,
                "change_type": change_type,
                "changed_fields": changed_fields,
                "sync_run_id": sync_run_id,
                "changes": changes,
            },
        )
    )


def traveltek_error_message(root: ElementTree.Element) -> str:
    messages: list[str] = []
    for element in root.iter():
        element_name = local_name(element.tag)
        if element_name in {"request", "auth", "method"}:
            continue

        text = (element.text or "").strip()
        interesting_attributes = [
            f"{key}={value}"
            for key, value in element.attrib.items()
            if normalise_key(key) in {"error", "errors", "message", "reason", "code", "description", "status", "success"}
            and str(value).strip()
        ]
        if text and len(text) <= 300 and element_name in {"error", "errors", "message", "fault", "exception"}:
            messages.append(f"{element_name}: {text}")
        if element_name in {"error", "errors", "message", "fault", "exception"} and text:
            messages.append(text)
        if interesting_attributes:
            messages.append(f"{element_name}: {', '.join(interesting_attributes)}")

    deduped = []
    for message in messages:
        if message not in deduped:
            deduped.append(message)

    if deduped:
        return redact_sensitive_text(" | ".join(deduped[:8]))

    root_text = ElementTree.tostring(root, encoding="unicode")
    return redact_sensitive_text(root_text[:700])


def encode_multipart_form_data(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"----HeadOfficeTraveltek{uuid4().hex}"
    body_parts: list[str] = []
    for key, value in fields.items():
        body_parts.append(f"--{boundary}")
        body_parts.append(f'Content-Disposition: form-data; name="{key}"')
        body_parts.append("")
        body_parts.append(value)
    body_parts.append(f"--{boundary}--")
    body_parts.append("")
    return "\r\n".join(body_parts).encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def build_request_xml(action: str, attributes: dict[str, str]) -> str:
    request = ElementTree.Element("request")
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
    return '<?xml version="1.0"?>\n' + ElementTree.tostring(request, encoding="unicode")


def call_traveltek(action: str, attributes: dict[str, str], *, secure_endpoint: bool = False) -> ElementTree.Element:
    if not settings.traveltek_api_configured:
        raise TraveltekConfigurationError("Traveltek API is not configured in Render yet.")

    request_xml = build_request_xml(action, attributes)
    encoded, content_type = encode_multipart_form_data({"xml": request_xml})
    endpoint_url = settings.traveltek_secure_api_base_url if secure_endpoint else settings.traveltek_api_base_url
    request = urllib.request.Request(
        endpoint_url,
        data=encoded,
        headers={"Content-Type": content_type},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise TraveltekApiError(f"Traveltek API returned HTTP {exc.code}: {redact_sensitive_text(response_text[:500])}") from exc
    except urllib.error.URLError as exc:
        raise TraveltekApiError(f"Traveltek API request failed: {exc}") from exc

    try:
        root = ElementTree.fromstring(response_text)
    except ElementTree.ParseError as exc:
        raise TraveltekApiError("Traveltek API returned a response that was not valid XML.") from exc

    if root.attrib.get("success", "Y").upper() == "N":
        raise TraveltekApiError(traveltek_error_message(root) or "Traveltek API returned an error.")

    return root


def fetch_booking_detail(attributes: dict[str, str]) -> TraveltekBookingData:
    root = call_traveltek("getportfolio", attributes, secure_endpoint=True)
    flattened = flatten_xml(root)
    values = extract_booking_values(flattened, root)
    diagnostics = traveltek_finance_diagnostics(flattened, root)
    diagnostics["chosen_paid_to_supplier"] = display_value(values.get("non_trusted_paid_supplier"))
    diagnostics["chosen_due_to_suppliers"] = display_value(values.get("imported_supplier_outstanding"))
    supplier_references = collect_supplier_references(root, flattened)
    if supplier_references:
        values["supplier_references_raw"] = " | ".join(supplier_references)
    return TraveltekBookingData(
        values=values,
        source={
            "action": "getportfolio",
            "endpoint": "secure",
            "lookup": attributes,
            "extracted": {key: display_value(value) for key, value in values.items()},
            "diagnostics": diagnostics,
            "supplier_references": supplier_references,
            "sample": element_to_source(root),
            "api_calls": 1,
        },
    )


def fetch_booking_by_reference(booking_ref: str) -> TraveltekBookingData:
    return fetch_booking_detail({"bookingreference": booking_ref})


def money_value(values: dict[str, Any], key: str) -> Decimal | None:
    value = values.get(key)
    if value is None:
        return None
    try:
        return Decimal(value).quantize(Decimal("0.01"))
    except Exception:
        return None


def traveltek_detail_looks_incomplete(data: TraveltekBookingData) -> bool:
    values = data.values
    total_due = money_value(values, "non_trusted_total_due")
    paid_to_supplier = money_value(values, "non_trusted_paid_supplier")
    due_to_suppliers = money_value(values, "imported_supplier_outstanding")

    if total_due is None or total_due <= Decimal("0.00"):
        return paid_to_supplier is None

    if paid_to_supplier is None:
        return True

    if due_to_suppliers is None:
        return paid_to_supplier < total_due

    expected_total = (paid_to_supplier + due_to_suppliers).quantize(Decimal("0.01"))
    return abs(expected_total - total_due) > Decimal("1.00") and paid_to_supplier < total_due


def merge_traveltek_booking_data(primary: TraveltekBookingData, secondary: TraveltekBookingData) -> TraveltekBookingData:
    values = dict(primary.values)
    source_values = [primary.values, secondary.values]

    for key, value in secondary.values.items():
        if values.get(key) in {None, ""} and value not in {None, ""}:
            values[key] = value

    for key in (
        "non_trusted_paid_supplier",
        "imported_supplier_outstanding",
        "non_trusted_total_due",
        "non_trusted_total_received",
        "gross_booking_value",
        "expected_supplier_nett",
    ):
        money_options = [money_value(next_values, key) for next_values in source_values]
        best_value = largest_money_value(money_options)
        if best_value is not None:
            values[key] = best_value

    primary_total_due = money_value(values, "non_trusted_total_due")
    primary_due_to_suppliers = money_value(values, "imported_supplier_outstanding")
    primary_paid_to_supplier = money_value(values, "non_trusted_paid_supplier")
    if (
        primary_total_due is not None
        and primary_due_to_suppliers is not None
        and primary_due_to_suppliers > Decimal("0.00")
        and (primary_paid_to_supplier is None or primary_paid_to_supplier + primary_due_to_suppliers < primary_total_due)
    ):
        values["non_trusted_paid_supplier"] = (primary_total_due - primary_due_to_suppliers).quantize(Decimal("0.01"))

    primary_source = primary.source
    secondary_source = secondary.source
    diagnostics = {
        "primary": primary_source.get("diagnostics"),
        "secondary": secondary_source.get("diagnostics"),
        "chosen_paid_to_supplier": display_value(values.get("non_trusted_paid_supplier")),
        "chosen_due_to_suppliers": display_value(values.get("imported_supplier_outstanding")),
    }
    return TraveltekBookingData(
        values=values,
        source={
            **primary_source,
            "lookup": {
                "primary": primary_source.get("lookup"),
                "secondary": secondary_source.get("lookup"),
            },
            "extracted": {key: display_value(value) for key, value in values.items()},
            "diagnostics": diagnostics,
            "lookup_notes": "Merged Traveltek booking ID lookup with booking reference lookup.",
            "api_calls": int(primary_source.get("api_calls") or 1) + int(secondary_source.get("api_calls") or 1),
        },
    )


def format_otc_booking_ref(number_value: int) -> str:
    return f"OTC-{number_value:05d}"


def booking_ref_number(booking_ref: str | None) -> int | None:
    if not booking_ref:
        return None
    match = re.fullmatch(r"OTC-(\d+)", str(booking_ref).strip().upper())
    return int(match.group(1)) if match else None


def highest_existing_otc_booking_ref(db: Session) -> tuple[str | None, int]:
    highest_number = 0
    highest_ref = None
    booking_refs = db.scalars(select(Booking.booking_ref).where(Booking.booking_ref.like("OTC-%"))).all()
    for booking_ref in booking_refs:
        number_value = booking_ref_number(booking_ref)
        if number_value is not None and number_value > highest_number:
            highest_number = number_value
            highest_ref = format_otc_booking_ref(number_value)
    return highest_ref, highest_number


def fetch_booking_for_existing_booking(booking: Booking) -> TraveltekBookingData:
    if booking.traveltek_booking_id:
        try:
            booking_id_data = fetch_booking_detail({"bookingid": booking.traveltek_booking_id})
            if not traveltek_detail_looks_incomplete(booking_id_data):
                return booking_id_data
            reference_data = fetch_booking_by_reference(booking.booking_ref)
            return merge_traveltek_booking_data(booking_id_data, reference_data)
        except TraveltekApiError as booking_id_error:
            try:
                return fetch_booking_by_reference(booking.booking_ref)
            except TraveltekApiError as reference_error:
                raise TraveltekApiError(
                    f"Traveltek ID lookup failed: {booking_id_error} "
                    f"Reference lookup failed: {reference_error}"
                ) from reference_error
    return fetch_booking_by_reference(booking.booking_ref)


def extract_booking_values(flattened: dict[str, str], root: ElementTree.Element | None = None) -> dict[str, Any]:
    booking_ref = normalise_booking_ref(value_from_candidates(flattened, BOOKING_REF_CANDIDATES))
    booking_id = value_from_candidates(flattened, BOOKING_ID_CANDIDATES)
    values: dict[str, Any] = {}
    if booking_id:
        values["traveltek_booking_id"] = str(booking_id).strip()
    if booking_ref:
        values["booking_ref"] = booking_ref
        values["booking_company"] = determine_booking_company(booking_ref)

    for field_name, definition in FIELD_DEFINITIONS.items():
        parsed_value = None
        if definition["parser"] == "money":
            parsed_value = derive_traveltek_money_value(field_name, flattened, root)
        if parsed_value is None:
            raw_value = value_from_candidates(flattened, definition["candidates"])
            try:
                parsed_value = parse_traveltek_value(raw_value, definition["parser"])
            except ValueError:
                parsed_value = None
        if is_plausible_traveltek_value(field_name, parsed_value):
            values[field_name] = parsed_value

    if "return_date" not in values:
        derived_return_date = derive_return_date(flattened, values.get("departure_date"))
        if is_plausible_traveltek_value("return_date", derived_return_date):
            values["return_date"] = derived_return_date

    if "passenger_count" not in values:
        derived_passenger_count = derive_passenger_count(flattened, root)
        if is_plausible_traveltek_value("passenger_count", derived_passenger_count):
            values["passenger_count"] = derived_passenger_count

    imported_status = values.get("imported_booking_status")
    if imported_status is not None:
        values["normalised_status"] = normalise_booking_status(str(imported_status))

    if values.get("travel_elements_raw"):
        element_flags = parse_elements(values.get("travel_elements_raw"))
        values.update(element_flags)
        values["atol_review_status"] = determine_atol_review_status(element_flags)
    return values


def booking_detail_lookup_attributes(flattened: dict[str, str]) -> dict[str, str]:
    booking_id = value_from_candidates(flattened, BOOKING_ID_CANDIDATES)
    if booking_id:
        return {"bookingid": booking_id}

    booking_reference = value_from_candidates(flattened, BOOKING_REFERENCE_CANDIDATES)
    if booking_reference:
        return {"bookingreference": booking_reference}

    external_reference = value_from_candidates(flattened, EXTERNAL_REFERENCE_CANDIDATES)
    if external_reference:
        return {"externalreference": external_reference}

    return {}


def booking_elements_from_response(root: ElementTree.Element) -> list[ElementTree.Element]:
    matches_by_reference: dict[str, ElementTree.Element] = {}
    for element in root.iter():
        if element is root:
            continue

        element_name = local_name(element.tag)
        flattened = flatten_xml(element, {})
        booking_ref = normalise_booking_ref(value_from_candidates(flattened, BOOKING_REF_CANDIDATES))
        booking_id = value_from_candidates(flattened, BOOKING_ID_CANDIDATES)
        booking_key = booking_ref or booking_id
        if booking_key and element_name in BOOKING_ELEMENT_NAMES:
            matches_by_reference.setdefault(str(booking_key), element)

    if matches_by_reference:
        return list(matches_by_reference.values())

    flattened_root = flatten_xml(root, {})
    if value_from_candidates(flattened_root, BOOKING_REF_CANDIDATES) or value_from_candidates(
        flattened_root, BOOKING_ID_CANDIDATES
    ):
        return [root]
    return []


def getbookings_attribute_attempts(start_date: date, end_date: date, date_type: str) -> list[tuple[str, dict[str, str]]]:
    iso_from = format_date_for_traveltek(start_date, "iso")
    iso_to = format_date_for_traveltek(end_date, "iso")
    uk_from = format_date_for_traveltek(start_date, "uk")
    uk_to = format_date_for_traveltek(end_date, "uk")

    # Traveltek's getbookings document says startdate/enddate are the booking date range.
    # Departure-date working is handled after import by sorting/filtering stored bookings.
    return [
        ("Traveltek booking date range", {"startdate": iso_from, "enddate": iso_to}),
        ("Traveltek UK booking date range", {"startdate": uk_from, "enddate": uk_to}),
    ]


def sort_booking_elements(elements: list[ElementTree.Element], date_type: str) -> list[ElementTree.Element]:
    sort_field = "departure_date" if date_type == "departure_date" else "booking_date"

    def sort_key(element: ElementTree.Element) -> tuple[date, str]:
        values = extract_booking_values(flatten_xml(element, {}), element)
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
) -> tuple[str, bool, bool, list[dict[str, str | None]], int | None]:
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
        booking = Booking(booking_ref=booking_ref, **writable_values)
        db.add(booking)
        db.flush()
        changes = [
            {
                "field_name": field_name,
                "field_label": traveltek_field_label(field_name),
                "previous_value": None,
                "new_value": display_value(value),
            }
            for field_name, value in writable_values.items()
        ]
        return booking_ref, True, False, changes, booking.id

    changed = False
    changes = []
    for field_name, value in writable_values.items():
        current_value = getattr(booking, field_name)
        if not values_are_equal(current_value, value):
            changes.append(
                {
                    "field_name": field_name,
                    "field_label": traveltek_field_label(field_name),
                    "previous_value": display_value(current_value),
                    "new_value": display_value(value),
                }
            )
            setattr(booking, field_name, value)
            changed = True
    return booking_ref, False, changed, changes, booking.id


def get_setting_value(db: Session, key: str) -> str | None:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    return setting.value if setting else None


def set_setting_value(
    db: Session,
    key: str,
    value: str | None,
    description: str,
    actor_user_id: int | None,
) -> None:
    setting = db.scalar(select(Setting).where(Setting.key == key))
    if setting is None:
        setting = Setting(key=key, description=description)
        db.add(setting)
    setting.value = value
    setting.description = description
    setting.updated_by_user_id = actor_user_id


def parse_setting_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def import_traveltek_bookings_by_date_range(
    db: Session,
    start_date: date,
    end_date: date,
    date_type: str,
    limit: int,
    actor_user_id: int | None,
) -> TraveltekSyncRun:
    normalised_date_type = "booking_date"
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

    max_api_calls = max(1, settings.traveltek_max_calls_per_run)
    max_limit = min(limit, max(1, max_api_calls - 1))
    errors: list[str] = []
    created_count = 0
    updated_count = 0

    booking_elements: list[ElementTree.Element] = []
    attempt_errors: list[str] = []
    successful_attempt = None
    for attempt_name, attributes in getbookings_attribute_attempts(start_date, end_date, normalised_date_type):
        run.api_call_count += 1
        try:
            root = call_traveltek("getbookings", attributes)
            next_booking_elements = booking_elements_from_response(root)
            if next_booking_elements:
                booking_elements = sort_booking_elements(next_booking_elements, normalised_date_type)[:max_limit]
                successful_attempt = attempt_name
                break
            attempt_errors.append(f"{attempt_name}: Traveltek returned no booking rows.")
        except TraveltekApiError:
            attempt_errors.append(f"{attempt_name}: {exc}")

    if not booking_elements:
        no_rows_message = (
            "Traveltek accepted the request but returned no booking rows. "
            "This search uses Traveltek booking date. Try a wider booking-date range if you expected results."
        )
        if any("returned no booking rows" in error for error in attempt_errors):
            run.status = "completed"
            run.error_summary = no_rows_message
        else:
            run.status = "failed"
            run.error_summary = "Traveltek could not import bookings with the documented booking-date filters. " + " ".join(
                attempt_errors[:5]
            )
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    if successful_attempt is None:
        run.status = "failed"
        run.error_summary = "Traveltek could not import bookings with the available date filters. " + " ".join(
            attempt_errors[:5]
        )
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return run

    for booking_element in booking_elements:
        flattened = flatten_xml(booking_element, {})
        values = extract_booking_values(flattened, booking_element)
        lookup_attributes = booking_detail_lookup_attributes(flattened)
        lookup_label = values.get("booking_ref") or lookup_attributes.get("bookingreference") or lookup_attributes.get("bookingid")
        if lookup_attributes and run.api_call_count < max_api_calls:
            try:
                run.api_call_count += 1
                detail = fetch_booking_detail(lookup_attributes)
                values.update(detail.values)
            except TraveltekApiError as exc:
                errors.append(f"{lookup_label}: detail lookup failed, imported list data only. {exc}")
        elif lookup_attributes and "booking_ref" not in values:
            errors.append(f"{lookup_label}: detail lookup was skipped because the Traveltek call limit was reached.")

        try:
            imported_ref, created, changed, changes, booking_id = apply_booking_values_from_traveltek(db, values)
            run.checked_bookings += 1
            if created:
                created_count += 1
            elif changed:
                updated_count += 1
            add_traveltek_booking_change_log(
                db,
                booking_ref=imported_ref,
                booking_id=booking_id,
                sync_run_id=run.id,
                changes=changes,
                created=created,
                actor_user_id=actor_user_id,
            )
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
                        "changed_fields": [change["field_label"] for change in changes],
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
                "traveltek_api_date_basis": "booking_date",
                "successful_attempt": successful_attempt,
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


def run_full_catchup_batch(
    db: Session,
    start_date: date,
    end_date: date,
    batch_days: int,
    limit: int,
    reset_progress: bool,
    actor_user_id: int | None,
) -> dict[str, Any]:
    if end_date < start_date:
        raise ValueError("End date must be after start date.")

    stored_cursor = parse_setting_date(get_setting_value(db, FULL_CATCHUP_CURSOR_KEY))
    cursor = start_date if reset_progress or stored_cursor is None else stored_cursor
    if cursor < start_date or cursor > end_date:
        cursor = start_date if reset_progress else end_date + timedelta(days=1)

    if cursor > end_date:
        return {
            "run": None,
            "batch_start_date": None,
            "batch_end_date": None,
            "next_start_date": None,
            "complete": True,
            "estimated_calls_this_batch": 0,
            "message": "Full Traveltek catch-up is already complete for this date range.",
        }

    batch_end_date = min(cursor + timedelta(days=batch_days - 1), end_date)
    estimated_calls = min(limit, max(1, settings.traveltek_max_calls_per_run - 1)) + 1
    run = import_traveltek_bookings_by_date_range(
        db=db,
        start_date=cursor,
        end_date=batch_end_date,
        date_type="booking_date",
        limit=limit,
        actor_user_id=actor_user_id,
    )

    next_start_date = batch_end_date + timedelta(days=1)
    complete = next_start_date > end_date
    set_setting_value(
        db,
        FULL_CATCHUP_CURSOR_KEY,
        None if complete else next_start_date.isoformat(),
        "Next Traveltek full catch-up booking date to import.",
        actor_user_id,
    )
    set_setting_value(
        db,
        FULL_CATCHUP_END_KEY,
        end_date.isoformat(),
        "Current Traveltek full catch-up end date.",
        actor_user_id,
    )
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="traveltek_full_catchup_batch",
            table_name="traveltek_sync_runs",
            record_id=run.id,
            description=(
                f"Traveltek full catch-up imported booking dates "
                f"{cursor.isoformat()} to {batch_end_date.isoformat()}."
            ),
            after_data={
                "batch_start_date": cursor.isoformat(),
                "batch_end_date": batch_end_date.isoformat(),
                "next_start_date": None if complete else next_start_date.isoformat(),
                "complete": complete,
            },
        )
    )
    db.commit()
    db.refresh(run)
    return {
        "run": run,
        "batch_start_date": cursor,
        "batch_end_date": batch_end_date,
        "next_start_date": None if complete else next_start_date,
        "complete": complete,
        "estimated_calls_this_batch": estimated_calls,
        "message": "Full Traveltek catch-up batch finished.",
    }


def candidate_active_bookings(db: Session, limit: int, active_window_days: int = 0) -> list[Booking]:
    today = date.today()
    statement = select(Booking).where(Booking.is_archived.is_(False))
    if active_window_days > 0:
        active_cutoff_date = today - timedelta(days=active_window_days)
        statement = statement.where(or_(Booking.normalised_status.is_(None), Booking.normalised_status != "cancelled"))
        statement = statement.where((Booking.departure_date.is_(None)) | (Booking.departure_date >= active_cutoff_date))
    else:
        statement = statement.where(
            or_(Booking.normalised_status.is_(None), Booking.normalised_status.not_in(("cancelled", "completed")))
        )
        statement = statement.where((Booking.departure_date.is_(None)) | (Booking.departure_date >= today))
    statement = statement.order_by(Booking.departure_date.asc().nullslast(), Booking.updated_at.desc()).limit(limit)
    return list(db.scalars(statement))


def candidate_existing_bookings_for_update_everything(
    db: Session,
    limit: int,
    reset_progress: bool,
) -> tuple[list[Booking], str | None]:
    cursor = None if reset_progress else get_setting_value(db, UPDATE_EVERYTHING_CURSOR_KEY)
    statement = select(Booking).where(Booking.is_archived.is_(False)).order_by(Booking.booking_ref.desc()).limit(limit)
    if cursor:
        statement = statement.where(Booking.booking_ref < cursor)
    bookings = list(db.scalars(statement))
    return bookings, cursor


def run_update_everything_existing_booking_batch(
    db: Session,
    limit: int,
    reset_progress: bool,
    actor_user_id: int | None,
) -> dict[str, Any]:
    run = TraveltekSyncRun(sync_type="update_everything_existing_bookings", requested_by_user_id=actor_user_id)
    db.add(run)
    db.flush()

    if not settings.traveltek_api_configured:
        run.status = "failed"
        run.error_summary = "Traveltek API is not configured in Render yet."
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return {
            "run": run,
            "complete": False,
            "next_booking_ref": None,
            "estimated_calls_this_batch": 0,
            "message": "Traveltek API is not configured in Render yet.",
        }

    max_limit = min(limit, settings.traveltek_max_calls_per_run)
    bookings, previous_cursor = candidate_existing_bookings_for_update_everything(db, max_limit, reset_progress)
    if not bookings:
        set_setting_value(
            db,
            UPDATE_EVERYTHING_CURSOR_KEY,
            None,
            "Next booking reference for Traveltek update everything.",
            actor_user_id,
        )
        run.status = "completed"
        run.finished_at = datetime.now(UTC)
        run.error_summary = None if previous_cursor else "No bookings are available to update."
        db.commit()
        db.refresh(run)
        return {
            "run": run,
            "complete": True,
            "next_booking_ref": None,
            "estimated_calls_this_batch": 0,
            "message": "All existing bookings have been checked against Traveltek.",
        }

    errors: list[str] = []
    changed_count = 0
    for booking in bookings:
        try:
            traveltek_booking = fetch_booking_for_existing_booking(booking)
            run.api_call_count += int(traveltek_booking.source.get("api_calls") or 1)
            values = dict(traveltek_booking.values)
            # This refresh is for a booking we already hold; keep our booking key to avoid
            # creating a duplicate if Traveltek also returns an external reference.
            values["booking_ref"] = booking.booking_ref
            imported_ref, created, changed, changes, booking_id = apply_booking_values_from_traveltek(db, values)
            run.checked_bookings += 1
            changed_count += 1 if changed else 0
            add_traveltek_booking_change_log(
                db,
                booking_ref=imported_ref,
                booking_id=booking_id,
                sync_run_id=run.id,
                changes=changes,
                created=created,
                actor_user_id=actor_user_id,
            )
        except TraveltekApiError as exc:
            errors.append(f"{booking.booking_ref}: {exc}")
        except Exception as exc:
            errors.append(f"{booking.booking_ref}: {exc}")

    last_booking_ref = bookings[-1].booking_ref
    more_bookings = db.scalar(
        select(Booking.id)
        .where(Booking.is_archived.is_(False))
        .where(Booking.booking_ref < last_booking_ref)
        .order_by(Booking.booking_ref.desc())
        .limit(1)
    )
    complete = more_bookings is None
    set_setting_value(
        db,
        UPDATE_EVERYTHING_CURSOR_KEY,
        None if complete else last_booking_ref,
        "Next booking reference for Traveltek update everything.",
        actor_user_id,
    )

    run.proposals_created = changed_count
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
            action="traveltek_update_everything_existing_bookings",
            table_name="traveltek_sync_runs",
            record_id=run.id,
            description=(
                f"Traveltek update everything refreshed {run.checked_bookings} existing booking(s), "
                f"changed {changed_count}, and used {run.api_call_count} API call(s)."
            ),
            after_data={
                "last_booking_ref": last_booking_ref,
                "complete": complete,
                "changed": changed_count,
                "api_calls": run.api_call_count,
            },
        )
    )
    db.commit()
    db.refresh(run)
    return {
        "run": run,
        "complete": complete,
        "next_booking_ref": None if complete else last_booking_ref,
        "estimated_calls_this_batch": max_limit,
        "message": "Existing booking batch refreshed from Traveltek.",
    }


def scan_new_otc_booking_references(
    db: Session,
    max_references: int,
    stop_after_missing: int,
    actor_user_id: int | None,
) -> dict[str, Any]:
    run = TraveltekSyncRun(sync_type="new_otc_reference_scan", requested_by_user_id=actor_user_id)
    db.add(run)
    db.flush()

    if not settings.traveltek_api_configured:
        run.status = "failed"
        run.error_summary = "Traveltek API is not configured in Render yet."
        run.finished_at = datetime.now(UTC)
        db.commit()
        db.refresh(run)
        return {
            "run": run,
            "started_after_booking_ref": None,
            "first_checked_booking_ref": None,
            "last_checked_booking_ref": None,
            "created_count": 0,
            "updated_count": 0,
            "missing_count": 0,
            "message": "Traveltek API is not configured in Render yet.",
        }

    highest_ref, highest_number = highest_existing_otc_booking_ref(db)
    max_calls = min(max_references, settings.traveltek_max_calls_per_run)
    consecutive_missing = 0
    missing_count = 0
    created_count = 0
    updated_count = 0
    first_checked_ref = None
    last_checked_ref = None

    for number_value in range(highest_number + 1, highest_number + max_calls + 1):
        booking_ref = format_otc_booking_ref(number_value)
        first_checked_ref = first_checked_ref or booking_ref
        last_checked_ref = booking_ref
        run.api_call_count += 1
        try:
            traveltek_booking = fetch_booking_by_reference(booking_ref)
            values = dict(traveltek_booking.values)
            values["booking_ref"] = booking_ref
            imported_ref, created, changed, changes, booking_id = apply_booking_values_from_traveltek(db, values)
            run.checked_bookings += 1
            consecutive_missing = 0
            if created:
                created_count += 1
            elif changed:
                updated_count += 1
            add_traveltek_booking_change_log(
                db,
                booking_ref=imported_ref,
                booking_id=booking_id,
                sync_run_id=run.id,
                changes=changes,
                created=created,
                actor_user_id=actor_user_id,
            )
        except TraveltekApiError as exc:
            missing_count += 1
            consecutive_missing += 1
            if consecutive_missing >= stop_after_missing:
                break

    run.proposals_created = created_count + updated_count
    run.status = "completed"
    run.error_summary = None
    run.finished_at = datetime.now(UTC)
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action="traveltek_new_otc_reference_scan",
            table_name="traveltek_sync_runs",
            record_id=run.id,
            description=(
                f"Traveltek new reference scan checked {run.api_call_count} OTC reference(s), "
                f"created {created_count} booking(s), and updated {updated_count} booking(s)."
            ),
            after_data={
                "started_after_booking_ref": highest_ref,
                "first_checked_booking_ref": first_checked_ref,
                "last_checked_booking_ref": last_checked_ref,
                "created": created_count,
                "updated": updated_count,
                "missing": missing_count,
                "api_calls": run.api_call_count,
            },
        )
    )
    db.commit()
    db.refresh(run)
    message = (
        f"Checked new OTC references after {highest_ref or 'none'}. "
        f"Created {created_count}, updated {updated_count}, missing/not found {missing_count}."
    )
    return {
        "run": run,
        "started_after_booking_ref": highest_ref,
        "first_checked_booking_ref": first_checked_ref,
        "last_checked_booking_ref": last_checked_ref,
        "created_count": created_count,
        "updated_count": updated_count,
        "missing_count": missing_count,
        "message": message,
    }


def create_update_proposal(
    db: Session,
    run: TraveltekSyncRun,
    booking: Booking,
    field_name: str,
    current_value: Any,
    traveltek_value: Any,
    source: dict[str, Any],
) -> bool:
    if not is_valid_traveltek_update_value(field_name, display_value(traveltek_value)):
        return False

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


def apply_traveltek_update_to_booking(db: Session, update: TraveltekBookingUpdate) -> dict[str, Any] | None:
    if update.field_name not in REVIEW_FIELD_NAMES and update.field_name not in AUTO_APPLY_FIELD_NAMES:
        return None

    definition = FIELD_DEFINITIONS[update.field_name]
    try:
        parsed_value = parse_traveltek_value(update.traveltek_value, definition["parser"])
    except ValueError:
        return None

    if not is_plausible_traveltek_value(update.field_name, parsed_value):
        return None

    booking = db.get(Booking, update.booking_id) if update.booking_id else None
    if booking is None:
        booking = db.scalar(select(Booking).where(Booking.booking_ref == update.booking_ref))
    if booking is None:
        return None

    before_data: dict[str, Any] = {"booking_ref": booking.booking_ref}
    after_data: dict[str, Any] = {"booking_ref": booking.booking_ref}

    if update.field_name == "imported_booking_status":
        before_data["imported_booking_status"] = display_value(booking.imported_booking_status)
        before_data["normalised_status"] = display_value(booking.normalised_status)
        booking.imported_booking_status = display_value(parsed_value)
        booking.normalised_status = normalise_booking_status(display_value(parsed_value))
        after_data["imported_booking_status"] = display_value(booking.imported_booking_status)
        after_data["normalised_status"] = display_value(booking.normalised_status)
        return {"before": before_data, "after": after_data}

    if not hasattr(booking, update.field_name):
        return None

    before_data[update.field_name] = display_value(getattr(booking, update.field_name))
    setattr(booking, update.field_name, parsed_value)
    after_data[update.field_name] = display_value(parsed_value)
    return {"before": before_data, "after": after_data}


def apply_traveltek_value_to_booking(
    booking: Booking,
    field_name: str,
    traveltek_value: Any,
) -> dict[str, Any] | None:
    if field_name not in AUTO_APPLY_FIELD_NAMES or not hasattr(booking, field_name):
        return None
    if values_are_equal(getattr(booking, field_name), traveltek_value):
        return None

    before_data = {
        "booking_ref": booking.booking_ref,
        field_name: display_value(getattr(booking, field_name)),
    }
    setattr(booking, field_name, traveltek_value)
    after_data = {
        "booking_ref": booking.booking_ref,
        field_name: display_value(traveltek_value),
    }
    return {"before": before_data, "after": after_data}


def scan_active_bookings_for_traveltek_updates(
    db: Session,
    limit: int,
    actor_user_id: int | None,
    active_window_days: int = 0,
    sync_type: str = "active_booking_check",
) -> TraveltekSyncRun:
    run = TraveltekSyncRun(sync_type=sync_type, requested_by_user_id=actor_user_id)
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
    bookings = candidate_active_bookings(db, max_limit, active_window_days=active_window_days)

    for booking in bookings:
        try:
            traveltek_booking = fetch_booking_for_existing_booking(booking)
            run.api_call_count += int(traveltek_booking.source.get("api_calls") or 1)
            run.checked_bookings += 1
            auto_changes: list[dict[str, str | None]] = []

            for field_name, traveltek_value in traveltek_booking.values.items():
                if field_name in AUTO_APPLY_FIELD_NAMES:
                    applied_data = apply_traveltek_value_to_booking(booking, field_name, traveltek_value)
                    if applied_data:
                        auto_changes.append(
                            {
                                "field_name": field_name,
                                "field_label": traveltek_field_label(field_name),
                                "previous_value": applied_data["before"].get(field_name),
                                "new_value": applied_data["after"].get(field_name),
                            }
                        )
                        db.add(
                            AuditLog(
                                actor_user_id=actor_user_id,
                                action="traveltek_auto_booking_update",
                                table_name="bookings",
                                record_id=booking.id,
                                description=f"Traveltek automatically updated {field_name} for {booking.booking_ref}.",
                                before_data=applied_data["before"],
                                after_data=applied_data["after"],
                            )
                        )
                    continue

                if field_name not in REVIEW_FIELD_NAMES:
                    continue

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

            if auto_changes:
                add_traveltek_booking_change_log(
                    db,
                    booking_ref=booking.booking_ref,
                    booking_id=booking.id,
                    sync_run_id=run.id,
                    changes=auto_changes,
                    created=False,
                    actor_user_id=actor_user_id,
                )
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
            after_data={"active_window_days": active_window_days},
        )
    )
    db.commit()
    db.refresh(run)
    return run


def run_active_maintenance_update(
    db: Session,
    new_booking_start_date: date,
    new_booking_end_date: date,
    new_booking_limit: int,
    refresh_limit: int,
    active_window_days: int,
    actor_user_id: int | None,
) -> dict[str, Any]:
    if new_booking_end_date < new_booking_start_date:
        raise ValueError("New booking end date must be after start date.")

    new_booking_run = import_traveltek_bookings_by_date_range(
        db=db,
        start_date=new_booking_start_date,
        end_date=new_booking_end_date,
        date_type="booking_date",
        limit=new_booking_limit,
        actor_user_id=actor_user_id,
    )
    refresh_run = scan_active_bookings_for_traveltek_updates(
        db=db,
        limit=refresh_limit,
        actor_user_id=actor_user_id,
        active_window_days=active_window_days,
        sync_type="active_recent_booking_check",
    )
    active_window_start_date = date.today() - timedelta(days=active_window_days)
    estimated_calls = min(new_booking_limit, max(1, settings.traveltek_max_calls_per_run - 1)) + 1
    estimated_calls += min(refresh_limit, settings.traveltek_max_calls_per_run)
    return {
        "new_booking_run": new_booking_run,
        "refresh_run": refresh_run,
        "active_window_start_date": active_window_start_date,
        "estimated_calls_this_run": estimated_calls,
        "message": "Active Traveltek update finished.",
    }
