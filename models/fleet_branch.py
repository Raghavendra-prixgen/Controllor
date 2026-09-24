# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .fleet_api import FleetAPIClient


class FleetBranch(models.Model):
    _name = 'fleet.branch'
    _description = 'Fleet Environment / Branch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'branch_type desc, name asc'

    project_id = fields.Many2one('fleet.project', string='Project', required=True, ondelete='cascade', index=True)
    project_name = fields.Char(related='project_id.name', string='Project Name', store=True)
    name = fields.Char(string='Environment Label', required=True, tracking=True)
    branch_name = fields.Char(string='Branch Name', required=True, tracking=True)
    slug = fields.Char(string='Slug / Subdomain', tracking=True)
    branch_type = fields.Selection(
        selection=[
            ('main', 'Production (Main)'),
            ('staging', 'Ephemeral Staging'),
            ('dev', 'Development / Sandbox'),
        ],
        string='Type',
        default='staging',
        required=True,
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('running', 'Running / Active'),
            ('stopped', 'Stopped / Inactive'),
            ('building', 'Building / Deploying'),
            ('error', 'Error / Degraded'),
        ],
        string='Container Status',
        default='stopped',
        tracking=True,
    )
    domain_url = fields.Char(string='Domain / Hostname', tracking=True)
    db_name = fields.Char(string='Postgres Database')
    last_commit_sha = fields.Char(string='Last Commit SHA')
    last_commit_msg = fields.Char(string='Commit Message')
    last_commit_author = fields.Char(string='Author')
    last_synced = fields.Datetime(string='Last Synced', readonly=True)

    def _get_api_client(self):
        return FleetAPIClient.from_env(self.env)

    def action_open_env_url(self):
        """Opens branch domain in browser."""
        self.ensure_one()
        url = self.domain_url
        if not url:
            raise UserError(_("No domain URL is mapped to this environment."))
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"http://{url}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_rebuild_branch(self):
        """Triggers a container rebuild / deployment for this branch."""
        self.ensure_one()
        client = self._get_api_client()
        if self.branch_type == 'main':
            client.deploy_main(self.project_name)
        else:
            client.create_staging(self.project_name, self.branch_name, source='main')

        self.project_id.action_sync()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Rebuild Triggered"),
                'message': _("Branch '%s' rebuild initiated on Fleet Platform.") % self.branch_name,
                'type': 'info',
                'sticky': False,
            }
        }

    def action_destroy_branch(self):
        """Destroys this staging environment and drops its database."""
        self.ensure_one()
        if self.branch_type == 'main':
            raise UserError(_("Production 'main' environment cannot be destroyed via this action."))

        client = self._get_api_client()
        client.destroy_staging(self.project_name, self.branch_name)

        proj = self.project_id
        self.unlink()
        proj.action_sync()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Staging Destroyed"),
                'message': _("Staging environment '%s' torn down successfully.") % self.branch_name,
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_backup_branch(self):
        """Takes a database snapshot of this branch."""
        self.ensure_one()
        client = self._get_api_client()
        client.trigger_backup(project=self.project_name, branch=self.branch_name, reason='manual', fmt='dump')
        self.env['fleet.backup'].action_sync_project_backups(self.project_name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Backup Created"),
                'message': _("Database backup initiated for branch '%s'.") % self.branch_name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_optimize_branch_db(self):
        """Runs VACUUM on branch database."""
        self.ensure_one()
        client = self._get_api_client()
        client.optimize_db(project=self.project_name, branch=self.branch_name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Optimization Done"),
                'message': _("Database optimized for '%s'.") % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
