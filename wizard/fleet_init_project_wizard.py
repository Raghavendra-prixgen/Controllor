# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..models.fleet_api import FleetAPIClient


class FleetInitProjectWizard(models.TransientModel):
    _name = 'fleet.init.project.wizard'
    _description = 'Scaffold New Fleet Project'

    name = fields.Char(
        string='Project Slug / Name',
        required=True,
        help='Unique DNS-safe project identifier (e.g., client-alpha, globex-corp).',
    )
    repo_url = fields.Char(
        string='GitHub / Git Repository URL',
        required=True,
        help='Full Git clone URL (e.g. https://github.com/org/client-repo.git).',
    )
    odoo_version = fields.Char(
        string='Odoo Version',
        default='18.0',
        required=True,
    )

    def action_confirm_init(self):
        self.ensure_one()
        p_name = (self.name or "").strip()
        p_repo = (self.repo_url or "").strip()
        p_ver = (self.odoo_version or "18.0").strip()

        if not p_name or not p_repo:
            raise ValidationError(_("Project Name and Repository URL are required."))

        client = FleetAPIClient.from_env(self.env)
        client.init_project(name=p_name, repo=p_repo, version=p_ver)

        # Trigger project sync
        self.env['fleet.project'].action_sync_all_projects()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Project Initialized"),
                'message': _("Project '%s' initialized and scaffolded successfully on Fleet Platform.") % p_name,
                'type': 'success',
                'sticky': False,
            }
        }
