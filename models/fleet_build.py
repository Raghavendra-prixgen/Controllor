# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from .fleet_api import FleetAPIClient


class FleetBuild(models.Model):
    _name = 'fleet.build'
    _description = 'Fleet Build & Deployment Log'
    _order = 'timestamp desc, id desc'

    project_id = fields.Many2one('fleet.project', string='Project', ondelete='cascade', index=True)
    project_name = fields.Char(string='Project Slug', required=True, index=True)
    branch_name = fields.Char(string='Branch / Target', default='main', index=True)
    build_id_str = fields.Char(string='Build Identifier', index=True)
    commit_sha = fields.Char(string='Commit SHA')
    short_sha = fields.Char(string='Short SHA')
    commit_message = fields.Char(string='Commit Message')
    author = fields.Char(string='Author')
    exit_code = fields.Integer(string='Exit Code', default=0)
    status = fields.Selection(
        selection=[
            ('success', 'Build Successful'),
            ('failed', 'Build Failed'),
            ('running', 'In Progress'),
        ],
        string='Status',
        default='success',
    )
    trigger_source = fields.Char(string='Trigger Source', default='manual')
    log_file = fields.Char(string='Log File Name')
    log_content = fields.Text(string='Build Console Log Output')
    timestamp = fields.Datetime(string='Build Time')

    @api.model
    def action_sync_builds_for_project(self, project_name):
        """Pulls build history entries from platform for a project."""
        if not project_name:
            return
        client = FleetAPIClient.from_env(self.env)
        Project = self.env['fleet.project']
        proj = Project.search([('name', '=', project_name)], limit=1)

        try:
            builds_list = client.get_builds(project=project_name)
        except Exception:
            return

        for b in builds_list:
            b_id = b.get("id", "")
            if not b_id:
                continue

            existing = self.search([('project_name', '=', project_name), ('build_id_str', '=', b_id)], limit=1)
            vals = {
                'project_id': proj.id if proj else False,
                'project_name': project_name,
                'branch_name': b.get("branch", "main"),
                'build_id_str': b_id,
                'commit_sha': b.get("commit_sha", ""),
                'short_sha': b.get("short_sha", ""),
                'commit_message': b.get("commit_message", ""),
                'author': b.get("author", ""),
                'exit_code': b.get("exit_code", 0),
                'status': b.get("status", "success"),
                'trigger_source': b.get("trigger_source", "manual"),
                'log_file': b.get("log_file", ""),
            }
            if b.get("timestamp"):
                vals['timestamp'] = fields.Datetime.to_datetime(b["timestamp"][:19].replace('T', ' '))

            if existing:
                existing.write(vals)
            else:
                self.create(vals)

    def action_fetch_log(self):
        """Fetches complete console log content from platform for this build."""
        self.ensure_one()
        if not self.log_file:
            return
        client = FleetAPIClient.from_env(self.env)
        log_txt = client.get_build_log(self.project_name, self.log_file)
        self.write({'log_content': log_txt})

    def action_analyze_build_errors(self):
        """Runs the error resolver on this build log."""
        self.ensure_one()
        if not self.log_content and self.log_file:
            self.action_fetch_log()

        return {
            'name': _("Error Resolver Diagnostics"),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.error.resolver',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_name': self.project_name,
                'default_branch_name': self.branch_name,
                'default_raw_log': self.log_content or '',
            },
        }
