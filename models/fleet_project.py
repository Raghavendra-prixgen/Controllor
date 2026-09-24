# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from .fleet_api import FleetAPIClient


class FleetProject(models.Model):
    _name = 'fleet.project'
    _description = 'Fleet Project / Client Repository'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Project Name / Slug', required=True, index=True, tracking=True)
    repo_url = fields.Char(string='Git Repository URL', tracking=True)
    odoo_version = fields.Char(string='Odoo Version', default='18.0', tracking=True)
    main_domain = fields.Char(string='Production Domain / URL', tracking=True)
    main_container_status = fields.Selection(
        selection=[
            ('running', 'Running / Healthy'),
            ('stopped', 'Stopped / Inactive'),
            ('building', 'Deploying / Building'),
            ('error', 'Error / Failed'),
            ('unknown', 'Unknown'),
        ],
        string='Production Container',
        default='unknown',
        tracking=True,
    )
    main_db_name = fields.Char(string='Production Database Name')
    last_synced = fields.Datetime(string='Last Synchronized', readonly=True)
    notes = fields.Text(string='Internal Notes')

    # Relations
    branch_ids = fields.One2many('fleet.branch', 'project_id', string='Branches / Environments')
    build_ids = fields.One2many('fleet.build', 'project_id', string='Build History')
    backup_ids = fields.One2many('fleet.backup', 'project_id', string='Backups')

    # Computed counts
    active_staging_count = fields.Integer(string='Active Staging Envs', compute='_compute_counts')
    total_build_count = fields.Integer(string='Total Builds', compute='_compute_counts')
    total_backup_count = fields.Integer(string='Total Backups', compute='_compute_counts')

    @api.depends('branch_ids', 'build_ids', 'backup_ids')
    def _compute_counts(self):
        for rec in self:
            rec.active_staging_count = len(rec.branch_ids.filtered(lambda b: b.branch_type == 'staging'))
            rec.total_build_count = len(rec.build_ids)
            rec.total_backup_count = len(rec.backup_ids)

    def _get_api_client(self):
        return FleetAPIClient.from_env(self.env)

    @api.model
    def action_sync_all_projects(self):
        """Pulls all fleet projects and branches from platform."""
        client = FleetAPIClient.from_env(self.env)
        projects_data = client.get_projects()

        Branch = self.env['fleet.branch']
        synced_project_ids = []

        for p in projects_data:
            p_name = p.get("name")
            if not p_name:
                continue

            # Determine main container status
            m_status_raw = (p.get("main_status") or "").lower()
            if "running" in m_status_raw or "up" in m_status_raw:
                m_status = 'running'
            elif "exited" in m_status_raw or "stop" in m_status_raw:
                m_status = 'stopped'
            elif "build" in m_status_raw:
                m_status = 'building'
            elif "error" in m_status_raw:
                m_status = 'error'
            else:
                m_status = 'unknown'

            proj = self.search([('name', '=', p_name)], limit=1)
            vals = {
                'name': p_name,
                'repo_url': p.get("repo", ""),
                'odoo_version': p.get("version", "18.0"),
                'main_domain': p.get("main_domain", ""),
                'main_container_status': m_status,
                'main_db_name': p.get("main_db", ""),
                'last_synced': fields.Datetime.now(),
            }
            if proj:
                proj.write(vals)
            else:
                proj = self.create(vals)

            synced_project_ids.append(proj.id)

            # Ensure Main branch record exists
            main_branch = Branch.search([('project_id', '=', proj.id), ('branch_name', '=', 'main')], limit=1)
            main_branch_vals = {
                'project_id': proj.id,
                'name': f"{p_name} / main",
                'branch_name': 'main',
                'slug': 'main',
                'branch_type': 'main',
                'status': m_status,
                'domain_url': p.get("main_domain", ""),
                'db_name': p.get("main_db", ""),
                'last_synced': fields.Datetime.now(),
            }
            if main_branch:
                main_branch.write(main_branch_vals)
            else:
                Branch.create(main_branch_vals)

            # Sync staging environments
            stg_list = p.get("staging_envs", [])
            existing_stg_branches = []
            for stg in stg_list:
                b_name = stg.get("branch", "")
                if not b_name:
                    continue
                b_slug = stg.get("slug", b_name)
                b_status_raw = (stg.get("status") or "").lower()
                b_status = 'running' if ("running" in b_status_raw or "up" in b_status_raw) else 'stopped'

                stg_branch = Branch.search([('project_id', '=', proj.id), ('branch_name', '=', b_name)], limit=1)
                stg_vals = {
                    'project_id': proj.id,
                    'name': f"{p_name} / {b_name}",
                    'branch_name': b_name,
                    'slug': b_slug,
                    'branch_type': 'staging',
                    'status': b_status,
                    'domain_url': stg.get("domain", ""),
                    'db_name': stg.get("db", ""),
                    'last_synced': fields.Datetime.now(),
                }
                if stg_branch:
                    stg_branch.write(stg_vals)
                else:
                    stg_branch = Branch.create(stg_vals)
                existing_stg_branches.append(stg_branch.id)

            # Clean up branches no longer present on platform
            stale_branches = Branch.search([
                ('project_id', '=', proj.id),
                ('branch_type', '=', 'staging'),
                ('id', 'not in', existing_stg_branches),
            ])
            if stale_branches:
                stale_branches.unlink()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Fleet Projects Synchronized"),
                'message': _("Successfully updated %d project(s) from Fleet Platform.") % len(synced_project_ids),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_sync(self):
        """Syncs this individual project."""
        self.action_sync_all_projects()
        return True

    def action_deploy_main(self):
        """Deploys or rebuilds the production environment."""
        self.ensure_one()
        client = self._get_api_client()
        res = client.deploy_main(self.name)
        self.action_sync()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Production Deployment Triggered"),
                'message': _("Deploy command dispatched for project '%s'. Check build logs for progress.") % self.name,
                'type': 'info',
                'sticky': False,
            }
        }

    def action_open_main_url(self):
        """Opens project main production domain in new browser tab."""
        self.ensure_one()
        domain = self.main_domain
        if not domain:
            raise UserError(_("No domain configured for this project."))
        if not domain.startswith("http://") and not domain.startswith("https://"):
            domain = f"http://{domain}"
        return {
            'type': 'ir.actions.act_url',
            'url': domain,
            'target': 'new',
        }

    def action_open_create_staging_wizard(self):
        """Opens wizard to branch out a new staging environment."""
        self.ensure_one()
        return {
            'name': _("Create Staging Environment (%s)") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.create.staging.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_source_branch': 'main',
            },
        }

    def action_backup_main(self):
        """Triggers a snapshot of the production database."""
        self.ensure_one()
        client = self._get_api_client()
        client.trigger_backup(project=self.name, branch='main', reason='manual_from_odoo', fmt='dump')
        self.env['fleet.backup'].action_sync_project_backups(self.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Backup Created"),
                'message': _("Production database backup initiated for '%s'.") % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_optimize_main_db(self):
        """Executes VACUUM ANALYZE optimization."""
        self.ensure_one()
        client = self._get_api_client()
        client.optimize_db(project=self.name, branch='main')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Optimization Completed"),
                'message': _("Database optimization executed successfully for '%s'.") % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_staging_branches(self):
        self.ensure_one()
        return {
            'name': _("Staging Environments - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.branch',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_project_builds(self):
        self.ensure_one()
        self.env['fleet.build'].action_sync_builds_for_project(self.name)
        return {
            'name': _("Build Logs - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.build',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_project_backups(self):
        self.ensure_one()
        self.env['fleet.backup'].action_sync_project_backups(self.name)
        return {
            'name': _("Database Backups - %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.backup',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
