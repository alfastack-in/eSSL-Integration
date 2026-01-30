import requests

import frappe


SOAP_ACTION = "http://tempuri.org/GetTransactionsLog"
SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TEMPURI_NS = "http://tempuri.org/"


def build_get_transactions_log_xml(from_datetime_str, to_datetime_str, serial_number, username, password):
    # IMPORTANT: No augmented assignments used.
    xml = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="{soap_env}">
  <soap:Body>
    <GetTransactionsLog xmlns="{tempuri}">
      <FromDateTime>{from_dt}</FromDateTime>
      <ToDateTime>{to_dt}</ToDateTime>
      <SerialNumber>{serial}</SerialNumber>
      <UserName>{user}</UserName>
      <UserPassword>{pwd}</UserPassword>
      <strDataList></strDataList>
    </GetTransactionsLog>
  </soap:Body>
</soap:Envelope>""".format(
        soap_env=SOAP_ENV_NS,
        tempuri=TEMPURI_NS,
        from_dt=frappe.utils.escape_html(from_datetime_str),
        to_dt=frappe.utils.escape_html(to_datetime_str),
        serial=frappe.utils.escape_html(serial_number or ""),
        user=frappe.utils.escape_html(username or ""),
        pwd=frappe.utils.escape_html(password or ""),
    )
    return xml


def post_soap(url, xml_body, timeout_seconds):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"' + SOAP_ACTION + '"',
    }

    # Using requests (backend app code), not server script.
    res = requests.post(url, data=xml_body.encode("utf-8"), headers=headers, timeout=timeout_seconds)
    return res