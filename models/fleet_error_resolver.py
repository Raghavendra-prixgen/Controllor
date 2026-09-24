# -*- coding: utf-8 -*-
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .fleet_api import FleetAPIClient


class FleetErrorResolver(models.TransientModel):
    _name = 'fleet.error.resolver'
    _description = 'Fleet Error Diagnostics & Automated Quick-Fix'

    project_name = fields.Char(string='Project Slug', required=True)
    branch_name = fields.Char(string='Branch Name', default='main', required=True)
    raw_log = fields.Text(string='Server Log / Traceback Input')

    error_detected = fields.Boolean(string='Error Detected', readonly=True, default=False)
    error_category = fields.Char(string='Error Category / Type', readonly=True)
    error_summary = fields.Text(string='Diagnostic Summary & Cause', readonly=True)
    offending_file = fields.Char(string='Offending File', readonly=True)
    offending_line = fields.Integer(string='Line Number', readonly=True)
    offending_module = fields.Char(string='Suspect Custom Addon / Module', readonly=True)
    suggested_fix = fields.Text(string='Recommended Solution', readonly=True)
    quick_fix_action = fields.Char(string='Available Quick Fix Action', readonly=True)
    has_quick_fix = fields.Boolean(string='Quick Fix Available', readonly=True, default=False)
    quick_fix_params = fields.Text(string='Quick Fix Parameters (JSON)', readonly=True)
    fix_status = fields.Text(string='Fix Execution Result', readonly=True)

    def _get_api_client(self):
        return FleetAPIClient.from_env(self.env)

    def action_run_analysis(self):
        """Dispatches log content or environment logs to AI error resolver engine."""
        self.ensure_one()
        client = self._get_api_client()
        analysis = client.analyze_error_log(
            project=self.project_name,
            branch=self.branch_name,
            raw_log=self.raw_log or "",
        )

        has_fix = bool(analysis.get("quick_fix_action"))
        self.write({
            'error_detected': bool(analysis.get("error_detected", True)),
            'error_category': analysis.get("category") or analysis.get("error_type") or "Generic Error",
            'error_summary': analysis.get("summary") or analysis.get("message") or "No distinct error signature matched.",
            'offending_file': analysis.get("file") or "",
            'offending_line': analysis.get("line") or 0,
            'offending_module': analysis.get("module") or "",
            'suggested_fix': analysis.get("solution") or analysis.get("recommendation") or "",
            'quick_fix_action': analysis.get("quick_fix_action") or "",
            'has_quick_fix': has_fix,
            'quick_fix_params': json.dumps(analysis.get("quick_fix_params", {})) if has_fix else "",
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.error.resolver',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_execute_quick_fix(self):
        """Runs the automated quick-fix on the fleet environment."""
        self.ensure_one()
        if not self.quick_fix_action:
            raise UserError(_("No automated quick-fix action available for this diagnostic report."))

        client = self._get_api_client()
        params = {}
        if self.quick_fix_params:
            try:
                params = json.loads(self.quick_fix_params)
            except Exception:
                params = {}

        result = client.execute_quick_fix(
            project=self.project_name,
            branch=self.branch_name,
            action=self.quick_fix_action,
            params=params,
        )

        out_msg = result.get("output") or result.get("message") or _("Quick fix executed successfully.")
        self.write({'fix_status': out_msg})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.error.resolver',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
