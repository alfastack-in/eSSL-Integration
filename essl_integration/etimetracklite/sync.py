import json
import re
import traceback

import frappe

from essl_integration.etimetracklite.soap_client import (
    ESSLRequestError,
    ESSLTimeoutError,
    build_get_transactions_log_xml,
    post_soap,
)

from essl_integration.etimetracklite.parser import (
    extract_strdatalist_text,
    parse_punch_lines,
)

from essl_integration.essl_integration.utils.datetime_utils import (
    now_datetime,
    subtract_minutes,
    to_soap_format,
)


def run_scheduled_sync():
    """
    Scheduler entry point.
    - reads eTimeTrackLite Setting
    - loops active Biometric Devices
    - sync punches
    """
    settings = frappe.get_single("eTimeTrackLite Setting")

    if not settings:
        return

    if not int(settings.enabled or 0):
        return

    devices = frappe.get_all(
        "Biometric Device",
        filters={"is_active": 1},
        fields=["name", "serial_no", "device_name", "last_sync_at"]
    )

    for d in devices:
        try:
            sync_one_device(d, settings)
        except Exception:
            # Do not stop other devices
            frappe.log_error(
                title="ESSL Sync Error (Device Loop)",
                message=traceback.format_exc()
            )


def _get_request_settings(settings):
    return {
        "window_minutes": int(settings.sync_window_minutes or 10),
        "timeout_seconds": int(settings.request_timeout_seconds or 60),
        "max_days": int(settings.max_days_per_call or 7),
    }


def sync_one_device(device_row, settings):
    device_name = device_row.get("name")
    serial_no = device_row.get("serial_no")

    if not serial_no:
        _update_device_sync_status(
            device_name=device_name,
            status="Failed",
            message="Missing Serial No in Biometric Device",
            log_count=0,
            synced_at=None
        )
        return

    request_settings = _get_request_settings(settings)
    window_minutes = request_settings["window_minutes"]
    timeout_seconds = request_settings["timeout_seconds"]
    max_days = request_settings["max_days"]

    now_dt = now_datetime()
    last_sync_at = device_row.get("last_sync_at")

    # If first time, fetch only last max_days (or 1 day if you prefer)
    if not last_sync_at:
        # Use max_days window as initial backfill, safe for open-source usage
        # start_dt = now_dt - max_days days
        start_dt = frappe.utils.add_days(now_dt, -1 * max_days)
    else:
        start_dt = last_sync_at

    start_dt = subtract_minutes(start_dt, window_minutes)

    # Also cap start_dt so we don't request extremely old data accidentally
    # max_days_per_call already controls window size indirectly, but this is additional safety.
    min_dt = frappe.utils.add_days(now_dt, -1 * max_days)
    if start_dt < min_dt:
        start_dt = min_dt

    from_str = to_soap_format(start_dt)
    to_str = to_soap_format(now_dt)

    xml_body = build_get_transactions_log_xml(
        from_datetime_str=from_str,
        to_datetime_str=to_str,
        serial_number=serial_no,
        username=settings.username,
        password=settings.get_password("password"),
    )

    integration_request_name = _create_integration_request(
        service="eTimeTrackLite",
        url=settings.url,
        request_data={
            "device": device_name,
            "serial_no": serial_no,
            "from": from_str,
            "to": to_str
        },
        raw_request_xml=xml_body,
        reference_doctype="Biometric Device",
        reference_docname=device_name
    )

    created = 0
    duplicates = 0
    unmapped = 0
    parsed_count = 0

    try:
        res = post_soap(settings.url, xml_body, timeout_seconds)

        # store response
        soap_xml = res.text or ""

        _mark_integration_request_completed(
            integration_request_name,
            soap_xml
        )

        # parse punches
        strdatalist_text = extract_strdatalist_text(soap_xml)
        punch_rows = parse_punch_lines(strdatalist_text)

        parsed_count = len(punch_rows)

        # process each punch
        for row in punch_rows:
            device_user_id = row.get("device_user_id")
            punch_dt = row.get("punch_dt")

            emp = _get_employee_by_device_user_id(device_user_id)
            if not emp:
                unmapped = unmapped + 1
                continue

            exists = _checkin_exists(emp, punch_dt, device_name)
            if exists:
                duplicates = duplicates + 1
                continue

            _create_employee_checkin(emp, punch_dt, device_name)
            created = created + 1

        # Update device last_sync_at ONLY after full success
        _update_device_sync_status(
            device_name=device_name,
            status="Success",
            message=_build_sync_message(created, duplicates, unmapped, parsed_count),
            log_count=parsed_count,
            synced_at=now_dt
        )

    except ESSLTimeoutError as e:
        _handle_sync_failure(
            integration_request_name=integration_request_name,
            device_name=device_name,
            error=e,
            parsed_count=parsed_count,
            log_error=False,
        )
    except ESSLRequestError as e:
        _handle_sync_failure(
            integration_request_name=integration_request_name,
            device_name=device_name,
            error=e,
            parsed_count=parsed_count,
            log_error=False,
        )
    except Exception as e:
        _handle_sync_failure(
            integration_request_name=integration_request_name,
            device_name=device_name,
            error=e,
            parsed_count=parsed_count,
            log_error=True,
        )


def _handle_sync_failure(integration_request_name, device_name, error, parsed_count, log_error):
    error_message = str(error)

    if not error_message:
        error_message = error.__class__.__name__

    if isinstance(error, ESSLRequestError):
        error_payload = {
            "error": error_message,
            "error_type": error.__class__.__name__,
        }
    else:
        error_payload = {
            "error": error_message,
            "error_type": error.__class__.__name__,
            "traceback": traceback.format_exc()
        }

    _mark_integration_request_failed(integration_request_name, error_payload)

    _update_device_sync_status(
        device_name=device_name,
        status="Failed",
        message=error_message,
        log_count=parsed_count,
        synced_at=None
    )

    if log_error:
        frappe.log_error(
            title="ESSL Sync Failed (Device: {0})".format(device_name),
            message=traceback.format_exc()
        )
    else:
        frappe.logger("essl_integration").warning(
            "ESSL sync failed for device {0}: {1}".format(device_name, error_message)
        )


def _build_sync_message(created, duplicates, unmapped, parsed_count):
    msg = "Parsed: {0}, Created: {1}, Duplicates: {2}, Unmapped: {3}".format(
        parsed_count, created, duplicates, unmapped
    )
    return msg


def _get_employee_by_device_user_id(device_user_id):
    if not device_user_id:
        return None

    emp = frappe.get_value(
        "Employee",
        {"attendance_device_id": device_user_id},
        "name"
    )
    return emp


def _checkin_exists(employee, punch_dt, device_name):
    """
    Option B: check existing Employee Checkin by (employee, time, device)
    """
    if not employee:
        return True
    if not punch_dt:
        return True

    filters = {
        "employee": employee,
        "time": punch_dt
    }

    # optional: include device id if you want stricter uniqueness
    if device_name:
        filters["device_id"] = device_name

    name = frappe.get_value("Employee Checkin", filters, "name")
    if name:
        return True

    return False


def _create_employee_checkin(employee, punch_dt, device_name):
    doc = frappe.new_doc("Employee Checkin")
    doc.employee = employee
    doc.time = punch_dt
    doc.device_id = device_name
    doc.log_type = ""  # blank as per your decision
    doc.skip_auto_attendance = 0
    doc.insert(ignore_permissions=True)
    frappe.db.commit()


def _update_device_sync_status(device_name, status, message, log_count, synced_at):
    if not device_name:
        return

    values = {
        "last_sync_status": status,
        "last_sync_message": message,
        "last_sync_log_count": log_count
    }

    if synced_at:
        values["last_sync_at"] = synced_at

    frappe.db.set_value("Biometric Device", device_name, values)
    frappe.db.commit()


def _create_integration_request(service, url, request_data, raw_request_xml, reference_doctype, reference_docname):
    # Create Integration Request and store raw SOAP body in data as well for audit
    ir = frappe.new_doc("Integration Request")
    ir.integration_request_service = service
    ir.is_remote_request = 1
    ir.status = "Queued"
    ir.url = url

    # data: store high-level json + raw xml
    payload = {
        "request": request_data,
        "raw_request_xml": _mask_soap_secrets(raw_request_xml)
    }
    ir.data = json.dumps(payload, indent=2)

    ir.request_description = "Fetch Transactions Log"

    ir.reference_doctype = reference_doctype
    ir.reference_docname = reference_docname

    ir.insert(ignore_permissions=True)
    frappe.db.commit()
    return ir.name


def _mask_soap_secrets(raw_request_xml):
    if not raw_request_xml:
        return raw_request_xml

    return re.sub(
        r"(<UserPassword>)(.*?)(</UserPassword>)",
        r"\1********\3",
        raw_request_xml,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _mark_integration_request_completed(integration_request_name, raw_response_xml):
    if not integration_request_name:
        return

    # Store raw SOAP XML
    frappe.db.set_value(
        "Integration Request",
        integration_request_name,
        {
            "status": "Completed",
            "output": raw_response_xml
        }
    )
    frappe.db.commit()


def _mark_integration_request_failed(integration_request_name, error_obj):
    if not integration_request_name:
        return

    frappe.db.set_value(
        "Integration Request",
        integration_request_name,
        {
            "status": "Failed",
            "error": json.dumps(error_obj, indent=2)
        }
    )
    frappe.db.commit()
