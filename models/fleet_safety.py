# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .fleet_api import FleetAPIClient


class FleetSafety(models.Model):
    _name = 'fleet.safety'
    _description = 'Fleet Database Safety & Neutralizer'
    _rec_name = 'display_title'

    project_name = fields.Char(string='Project Slug', required=True, index=True)
    branch_name = fields.Char(string='Branch / Environment', default='main', required=True, index=True)
    display_title = fields.Char(string='Title', compute='_compute_display_title')

    outgoing_mail_active = fields.Boolean(string='Outgoing Mail Active', default=False)
    incoming_mail_active = fields.Boolean(string='Incoming Mail Active', default=False)
    payment_mode = fields.Selection(
        selection=[
            ('test', 'Test / Sandbox Mode'),
            ('live', 'Live / Production Mode'),
        ],
        string='Payment Providers Mode',
        default='test',
    )
    staging_flag = fields.Boolean(string='database.staging Flag', default=True)
    last_checked = fields.Datetime(string='Last Inspected', readonly=True)

    @api.depends('project_name', 'branch_name')
    def _compute_display_title(self):
        for rec in self:
            rec.display_title = f"{rec.project_name or ''} / {rec.branch_name or 'main'} (Safety Control)"

    def _get_api_client(self):
        return FleetAPIClient.from_env(self.env)

    def action_refresh_status(self):
        """Pulls current DB safety configuration from the environment."""
        self.ensure_one()
        client = self._get_api_client()
        safety = client.get_database_safety(project=self.project_name, branch=self.branch_name)

        self.write({
            'outgoing_mail_active': not safety.get("outgoing_mail_disabled", False),
            'incoming_mail_active': not safety.get("incoming_mail_disabled", False),
            'payment_mode': 'live' if not safety.get("payment_test_mode", True) else 'test',
            'staging_flag': safety.get("staging_flag", True),
            'last_checked': fields.Datetime.now(),
        })
        return True

    def action_preset_sandbox(self):
        """Applies full safety neutralization: disables emails, sets payments to test."""
        self.ensure_one()
        client = self._get_api_client()
        client.set_database_safety(self.project_name, self.branch_name, action='preset_sandbox')
        self.action_refresh_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Sandbox Neutralizer Applied"),
                'message': _("Environment '%s' has been neutralized: mail disabled and payments set to Test mode.") % self.branch_name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_preset_production(self):
        """Enables live mail and payment gateways."""
        self.ensure_one()
        client = self._get_api_client()
        client.set_database_safety(self.project_name, self.branch_name, action='preset_production')
        self.action_refresh_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Production Mode Activated"),
                'message': _("Environment '%s' configured for Live Operations: mail enabled, payments set to Live.") % self.branch_name,
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_toggle_outgoing_mail(self):
        self.ensure_one()
        client = self._get_api_client()
        new_mode = 'disable' if self.outgoing_mail_active else 'enable'
        client.set_database_safety(self.project_name, self.branch_name, action='outgoing_mail', mode=new_mode)
        self.action_refresh_status()

    def action_toggle_incoming_mail(self):
        self.ensure_one()
        client = self._get_api_client()
        new_mode = 'disable' if self.incoming_mail_active else 'enable'
        client.set_database_safety(self.project_name, self.branch_name, action='incoming_mail', mode=new_mode)
        self.action_refresh_status()

    def action_toggle_payment_mode(self):
        self.ensure_one()
        client = self._get_api_client()
        new_mode = 'test' if self.payment_mode == 'live' else 'live'
        client.set_database_safety(self.project_name, self.branch_name, action='payment_mode', mode=new_mode)
        self.action_refresh_status()
