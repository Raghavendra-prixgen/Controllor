# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..models.fleet_api import FleetAPIClient


class FleetCreateStagingWizard(models.TransientModel):
    _name = 'fleet.create.staging.wizard'
    _description = 'Wizard to Create Ephemeral Staging Environment'

    project_id = fields.Many2one('fleet.project', string='Target Project', required=True)
    project_name = fields.Char(related='project_id.name', string='Project Slug', readonly=True)
    target_branch = fields.Char(
        string='Staging Branch Name',
        required=True,
        help='Git branch name to deploy as an isolated staging environment (e.g. feat-accounting-fix, bugfix-123).',
    )
    source_branch = fields.Char(
        string='Database Base Source',
        default='main',
        required=True,
        help='Source branch/database to clone initial schema and data from (defaults to main).',
    )
    neutralize_database = fields.Boolean(
        string='Auto-Neutralize (Sandbox Safety)',
        default=True,
        help='Automatically disables live email servers and forces payment providers to Test Mode.',
    )

    def action_confirm_create(self):
        """Dispatches create-staging request to Fleet Platform."""
        self.ensure_one()
        p_name = self.project_name
        b_name = (self.target_branch or "").strip()
        s_name = (self.source_branch or "main").strip()

        if not b_name:
            raise ValidationError(_("Branch name cannot be empty."))
        if b_name == "main":
            raise ValidationError(_("Cannot use 'main' as a staging branch name."))

        client = FleetAPIClient.from_env(self.env)
        client.create_staging(project=p_name, branch=b_name, source=s_name)

        # If neutralize requested, trigger sandbox preset
        if self.neutralize_database:
            try:
                client.set_database_safety(project=p_name, branch=b_name, action='preset_sandbox')
            except Exception:
                pass

        self.project_id.action_sync()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Staging Creation Initiated"),
                'message': _("Staging environment '%s' is being spawned from '%s'. Container building in background.") % (b_name, s_name),
                'type': 'success',
                'sticky': False,
            }
        }
