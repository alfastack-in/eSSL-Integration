import frappe


class ESSLEmployeeCheckinMixin:
    def validate_distance_from_shift_location(self):
        if self._is_essl_biometric_checkin():
            return

        return super().validate_distance_from_shift_location()

    def _is_essl_biometric_checkin(self):
        if getattr(self.flags, "from_essl_integration", False):
            return True

        if not self.device_id:
            return False

        try:
            return bool(frappe.db.exists("Biometric Device", self.device_id))
        except Exception:
            return False
