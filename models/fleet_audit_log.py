# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from .fleet_api import FleetAPIClient


class FleetAuditLog(models.Model):
    _name = 'fleet.audit.log'
    _description = 'Fleet Platform Audit Trail'
    _order = 'timestamp desc, id desc'

    timestamp = fields.Datetime(string='Timestamp', index=True)
    operator = fields.Char(string='Operator / User', index=True)
    client_ip = fields.Char(string='Client IP Address')
    action = fields.Char(string='Executed Action', required=True, index=True)
    project_name = fields.Char(string='Target Project', index=True)
    branch_name = fields.Char(string='Branch / Environment')
    status = fields.Selection(
        selection=[
            ('success', 'Success (200 OK)'),
            ('failed', 'Denied / Failed'),
        ],
        string='Status',
        default='success',
    )
    details = fields.Text(string='Execution Details')

    @api.model
    def action_sync_audit_logs(self, limit=100):
        """Pulls audit records from platform."""
        client = FleetAPIClient.from_env(self.env)
        try:
            logs = client.get_audit_logs(limit=limit)
        except Exception:
            return

        for entry in logs:
            action_name = entry.get("action", "")
            ts_str = entry.get("timestamp", "")
            if not ts_str or not action_name:
                continue

            # Check if duplicate exists
            dt = fields.Datetime.to_datetime(ts_str[:19].replace('T', ' '))
            existing = self.search([
                ('timestamp', '=', dt),
                ('action', '=', action_name),
                ('operator', '=', entry.get("user", "")),
            ], limit=1)

            if not existing:
                self.create({
                    'timestamp': dt,
                    'operator': entry.get("user", "system"),
                    'client_ip': entry.get("ip", ""),
                    'action': action_name,
                    'project_name': entry.get("project", ""),
                    'branch_name': entry.get("branch", ""),
                    'status': 'success' if entry.get("ok", True) else 'failed',
                    'details': entry.get("details", "") or str(entry.get("payload", "")),
                })
