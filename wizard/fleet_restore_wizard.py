# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..models.fleet_api import FleetAPIClient


class FleetRestoreWizard(models.TransientModel):
    _name = 'fleet.restore.wizard'
    _description = 'Wizard to Restore Database Backup'

    backup_id = fields.Many2one('fleet.backup', string='Source Backup')
    project_name = fields.Char(string='Project Slug', required=True, readonly=True)
    backup_filename = fields.Char(string='Backup File', required=True, readonly=True)
    target_branch = fields.Char(
        string='Target Environment / Branch',
        default='main',
        required=True,
        help='The target database to overwrite with this backup (e.g. main or staging branch).',
    )
    confirm_acknowledged = fields.Boolean(
        string='I understand this will completely overwrite the target database.',
        default=False,
    )

    def action_confirm_restore(self):
        self.ensure_one()
        if not self.confirm_acknowledged:
            raise ValidationError(_("You must check the confirmation checkbox to proceed with database restoration."))

        client = FleetAPIClient.from_env(self.env)
        client.trigger_restore(
            project=self.project_name,
            branch=self.target_branch,
            backup_file=self.backup_filename,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Restore Dispatched"),
                'message': _("Database restore for '%s' (%s) initiated successfully.") % (self.project_name, self.target_branch),
                'type': 'warning',
                'sticky': True,
            }
        }
