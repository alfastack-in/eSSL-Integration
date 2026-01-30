import datetime
import xml.etree.ElementTree as ET


def _safe_text(val):
    if val is None:
        return ""
    return str(val)


def extract_strdatalist_text(soap_xml):
    """
    Extracts the inner text of <strDataList> from SOAP response.
    Works even if response is wrapped with namespaces.
    """
    root = ET.fromstring(soap_xml)

    for el in root.iter():
        if el.tag and str(el.tag).lower().endswith("strdatalist"):
            return _safe_text(el.text)

    return ""


def parse_punch_lines(strdatalist_text):
    """
    ESSL format (tab-separated):
      <device_user_id>\t<YYYY-MM-DD HH:MM:SS>\t

    Returns:
      [
        {
          "device_user_id": "103",
          "punch_dt": datetime,
          "raw_line": "..."
        }
      ]
    """
    if not strdatalist_text:
        return []

    lines = strdatalist_text.splitlines()
    out = []

    for line in lines:
        if not line:
            continue

        clean = line.strip()
        if not clean:
            continue

        # ESSL uses TAB as delimiter
        parts = clean.split("\t")

        if len(parts) < 2:
            continue

        device_user_id = parts[0].strip()
        datetime_str = parts[1].strip()

        if not device_user_id or not datetime_str:
            continue

        # Parse datetime (ESSL always sends seconds)
        try:
            punch_dt = datetime.datetime.strptime(
                datetime_str,
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            # fallback (very rare)
            try:
                punch_dt = datetime.datetime.strptime(
                    datetime_str,
                    "%Y-%m-%d %H:%M"
                )
            except Exception:
                continue

        out.append({
            "device_user_id": device_user_id,
            "punch_dt": punch_dt,
            "raw_line": clean,
        })

    return out