# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .fleet_api import FleetAPIClient


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fleet_platform_url = fields.Char(
        string='Fleet Platform URL',
        config_parameter='fleet.platform_url',
        default='http://127.0.0.1:8000',
        help='Base HTTP/HTTPS URL of the Fleet Platform Control Room.',
    )
    fleet_default_api_key = fields.Char(
        string='Default System API Token',
        config_parameter='fleet.default_api_key',
        help='Optional master/service API key used as fallback when users have not set personal tokens.',
    )
    fleet_default_odoo_version = fields.Char(
        string='Default Odoo Target Version',
        config_parameter='fleet.default_odoo_version',
        default='18.0',
        help='Default version used when initializing new projects.',
    )

    def action_test_fleet_connection(self):
        """Tests connectivity and displays platform status."""
        self.ensure_one()
        base_url = (self.fleet_platform_url or "").strip()
        token = (self.fleet_default_api_key or self.env.user.get_fleet_token() or "").strip()

        client = FleetAPIClient(base_url=base_url, token=token)
        try:
            status = client.get_auth_status()
            sys_info = {}
            try:
                sys_info = client.get_system_info()
            except Exception:
                pass

            msg = _("Successfully connected to Fleet Platform!\nPlatform Status: Online\nAuth Enforced: %s\nCurrent Role: %s") % (
                "Yes" if status.get("auth_required") else "No",
                status.get("role", "anonymous").upper(),
            )
            if sys_info:
                msg += _("\nHost: %s | Odoo Default: %s") % (
                    sys_info.get("base_domain", ""),
                    sys_info.get("odoo_version", "18.0"),
                )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Fleet Platform Online"),
                    'message': msg,
                    'type': 'success',
                    'sticky': True,
                }
            }
        except Exception as e:
            raise UserError(_("Connection test failed:\n%s") % str(e))
