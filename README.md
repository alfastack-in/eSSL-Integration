# eSSL eTimeTrackLite Integration for ERPNext / Frappe

A robust, production-ready **eSSL eTimeTrackLite biometric integration** for ERPNext / Frappe.
This app fetches punch logs from ESSL biometric devices using SOAP APIs and creates **Employee Checkin** records, fully compatible with ERPNext’s **Auto Attendance** and Shift system.

---

## ✨ Features

* ✅ Supports **eSSL eTimeTrackLite** SOAP API
* ✅ Works with **multiple biometric devices**
* ✅ Uses **ERPNext Employee Checkin**
* ✅ Compatible with **Auto Attendance & Shifts**
* ✅ Incremental sync using configurable time windows
* ✅ Duplicate-safe (idempotent checkin creation)
* ✅ Uses Frappe’s built-in **Integration Request** logging
* ✅ Scheduler-based automatic sync
* ✅ Open-source friendly & extensible

---

## 🧱 Architecture Overview

```
eSSL Device(s)
     ↓
eSSL eTimeTrackLite SOAP API
     ↓
essl_integration (this app)
     ↓
Integration Request (logging)
     ↓
Employee Checkin
     ↓
ERPNext Auto Attendance
```

---



## ⚙️ Installation

```bash
bench get-app essl_integration <repo-url>
bench --site <your-site> install-app essl_integration
```

Restart bench after installation.

---

## 🧩 Configuration

### 1️⃣ eTimeTrackLite Setting (Single DocType)

Navigate to:

```
eTimeTrackLite Setting
```

| Field                   | Description                             |
| ----------------------- | --------------------------------------- |
| URL                     | SOAP endpoint (example below)           |
| Username                | API username                            |
| Password                | API password (stored securely)          |
| Enabled                 | Enable / Disable sync                   |
| Request Timeout Seconds | SOAP request timeout                    |
| Sync Window Minutes     | Sliding window for incremental sync     |
| Max Days Per Call       | Safety limit for large historical pulls |

**Example URL**

```
http://<server-ip>:8195/iclock/WebAPIService.asmx
```

---

### 2️⃣ Biometric Device

Create one record per device.

| Field               | Description                |
| ------------------- | -------------------------- |
| Serial No           | Device Serial Number       |
| Device Name         | Friendly name              |
| Is Active           | Enable sync                |
| Last Sync At        | Auto-updated               |
| Last Sync Status    | Success / Failed / Partial |
| Last Sync Message   | Error / info               |
| Last Sync Log Count | Punches fetched            |

---

### 3️⃣ Employee Mapping (IMPORTANT)

In **Employee** master:

```
attendance_device_id = <ESSL User ID>
```

This value must match the **first column** in ESSL punch logs.

Example punch row:

```
103    2026-01-30 18:04:44
```

Employee must have:

```
attendance_device_id = 103
```

---

## 🔄 Sync Logic

* Sync runs using a **sliding time window**
* Default window: last **10 minutes**
* Each run:

  * Fetches logs per active device
  * Parses tab-separated punch data
  * Creates Employee Checkin records
  * Skips duplicates safely
  * Logs full request & response

---

## ⏱ Scheduler

Scheduler is configured in `hooks.py`:

```python
scheduler_events = {
    "cron": {
        "*/10 * * * *": [
            "essl_integration.etimetracklite.sync.run_scheduled_sync"
        ]
    }
}
```

Runs **every 10 minutes** by default.

---

## ▶️ Manual Sync (Bench Command)

For testing or debugging:

```bash
bench --site <your-site> execute essl_integration.etimetracklite.sync.run_scheduled_sync
```

---

## 🧲 Manual Backfill / Missed Punch Recovery

Open **eTimeTrackLite Setting** and click **Sync Backlog** to fetch punch logs for a specific period without changing the scheduled sync cursor (`Last Sync At`).
The dialog accepts Device, From Datetime, To Datetime, and Chunk Hours.

You can also use `sync_backlog` from bench.
The command splits the range into smaller chunks, which helps avoid ESSL server timeouts.

```bash
bench --site <your-site> execute essl_integration.etimetracklite.sync.sync_backlog --kwargs "{'device_name':'ADZV213260658','from_datetime':'2026-05-14 00:00:00','to_datetime':'2026-05-16 23:59:59','chunk_hours':6}"
```

Notes:

* `device_name` can be the Biometric Device name, serial number, or friendly device name.
* Leave `device_name` empty to backfill all active devices.
* Smaller `chunk_hours` values are safer for slow ESSL servers.
* Existing Employee Checkins are skipped, so rerunning a backfill is duplicate-safe.

---

## 🧾 Logging & Debugging

All API calls are logged in **Integration Request**:

```
Integrations → Integration Request
```

Logged details:

* SOAP request XML (password masked)
* SOAP response XML
* Status (Completed / Failed)
* Reference device
* Error stack trace (if any)

This avoids the need for custom log doctypes.

---

## 🧠 ESSL SOAP Response Format

ESSL returns punch logs as **tab-separated values**:

```
<device_user_id>\t<YYYY-MM-DD HH:MM:SS>\t
```

Example:

```
103	2026-01-30 18:04:44
```

Parser is built specifically for this format.

---

## 🧪 Duplicate Handling

A checkin is **not created** if a record already exists with:

* Same Employee
* Same Punch Time

This makes the sync **idempotent** and safe to run frequently.

---

## 🕒 Auto Attendance Compatibility

* Checkins are created with blank `log_type`
* ERPNext Shift + Auto Attendance handles IN / OUT logic
* HR can define shifts independently
* No device-side punch type assumptions

---

## 🔐 Security Notes

* Passwords are stored using Frappe’s **Password field**
* Actual password is fetched using `get_password()`
* Password is masked in logs
* No credentials are stored in plain text

---

## 🚨 Known ESSL Limitations (Handled)

* SOAP server is **HTTP/1.1 only**
* Redirects must be disabled
* SOAPAction header must be exact
* Response format is non-standard

All of the above are already handled in this app.

---

## 🛠 Extensibility

Future extensions supported by design:

* Other ESSL products (cloud, push APIs)
* Multiple credential profiles
* Device-wise punch tagging
* Manual re-sync UI
* Device health monitoring

---

## 📄 License

MIT License
Free to use, modify, and distribute.

---

## 🤝 Credits

Built with ❤️ on **Frappe Framework**
Designed for real-world FrappeHR deployments.
