# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from ..models.fleet_api import FleetAPIClient


class FleetDatabaseSafetyWizard(models.TransientModel):
    _name = 'fleet.database.safety.wizard'
    _description = 'Wizard to Adjust Database Safety & Neutralization'

    project_name = fields.Char(string='Project Slug', required=True)
    branch_name = fields.Char(string='Branch / Environment', default='main', required=True)
    action_type = fields.Selection(
        selection=[
            ('preset_sandbox', 'Sandbox Neutralization (Safe: Disable Mail, Payments Test Mode, Staging Flag ON)'),
            ('preset_production', 'Live Production Setup (Enable Live Mail & Live Payments)'),
            ('outgoing_mail_disable', 'Disable Outgoing Mail Servers'),
            ('outgoing_mail_enable', 'Enable Outgoing Mail Servers'),
            ('payment_mode_test', 'Force Payment Providers to Test Mode'),
            ('payment_mode_live', 'Switch Payment Providers to Live Mode'),
        ],
        string='Safety Action',
        default='preset_sandbox',
        required=True,
    )

    def action_apply_safety(self):
        self.ensure_one()
        client = FleetAPIClient.from_env(self.env)
        act = self.action_type

        if act in ('preset_sandbox', 'preset_production'):
            client.set_database_safety(self.project_name, self.branch_name, action=act)
        elif act == 'outgoing_mail_disable':
            client.set_database_safety(self.project_name, self.branch_name, action='outgoing_mail', mode='disable')
        elif act == 'outgoing_mail_enable':
            client.set_database_safety(self.project_name, self.branch_name, action='outgoing_mail', mode='enable')
        elif act == 'payment_mode_test':
            client.set_database_safety(self.project_name, self.branch_name, action='payment_mode', mode='test')
        elif act == 'payment_mode_live':
            client.set_database_safety(self.project_name, self.branch_name, action='payment_mode', mode='live')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Safety Control Applied"),
                'message': _("Database safety parameters updated for '%s / %s'.") % (self.project_name, self.branch_name),
                'type': 'success',
                'sticky': False,
            }
        }
