# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .fleet_api import FleetAPIClient


class FleetBackup(models.Model):
    _name = 'fleet.backup'
    _description = 'Fleet Database Backup Snapshot'
    _order = 'created_at desc, id desc'

    project_id = fields.Many2one('fleet.project', string='Project', ondelete='cascade', index=True)
    project_name = fields.Char(string='Project Slug', required=True, index=True)
    branch_name = fields.Char(string='Branch / Environment', default='main', index=True)
    filename = fields.Char(string='Backup Filename', required=True, index=True)
    file_size_formatted = fields.Char(string='Size')
    file_size_bytes = fields.Integer(string='Size (Bytes)')
    backup_format = fields.Selection(
        selection=[
            ('dump', 'Postgres Binary Dump (.dump)'),
            ('zip', 'Odoo Full Zip Archive (.zip)'),
            ('sql', 'Plain SQL (.sql)'),
        ],
        string='Format',
        default='dump',
    )
    reason = fields.Char(string='Backup Reason / Trigger', default='manual')
    created_at = fields.Datetime(string='Created Timestamp')
    download_url = fields.Char(string='Download URL', compute='_compute_download_url')

    def _compute_download_url(self):
        base_url = self.env.user.fleet_api_url or self.env['ir.config_parameter'].sudo().get_param(
            'fleet.platform_url', 'http://127.0.0.1:8000'
        ).rstrip('/')
        for rec in self:
            rec.download_url = f"{base_url}/api/backups/download?file={rec.filename}&project={rec.project_name}"

    @api.model
    def action_sync_project_backups(self, project_name=None):
        """Fetches backups from platform for a project or all projects."""
        client = FleetAPIClient.from_env(self.env)
        Project = self.env['fleet.project']

        projects_to_sync = [Project.search([('name', '=', project_name)], limit=1)] if project_name else Project.search([])

        for proj in projects_to_sync:
            p_name = proj.name if proj else project_name
            if not p_name:
                continue
            try:
                backups_list = client.get_backups(project=p_name)
            except Exception:
                continue

            for b in backups_list:
                fname = b.get("filename", "")
                if not fname:
                    continue

                fmt = 'dump'
                if fname.endswith('.zip'):
                    fmt = 'zip'
                elif fname.endswith('.sql'):
                    fmt = 'sql'

                existing = self.search([('project_name', '=', p_name), ('filename', '=', fname)], limit=1)
                vals = {
                    'project_id': proj.id if proj else False,
                    'project_name': p_name,
                    'branch_name': b.get("branch", "main"),
                    'filename': fname,
                    'file_size_formatted': b.get("size_formatted", ""),
                    'file_size_bytes': b.get("size_bytes", 0),
                    'backup_format': fmt,
                    'reason': b.get("reason", "manual"),
                }
                if b.get("created_at"):
                    vals['created_at'] = fields.Datetime.to_datetime(b["created_at"])

                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)

        return True

    def action_download_backup(self):
        """Opens download stream URL in browser."""
        self.ensure_one()
        url = self.download_url
        if not url:
            raise UserError(_("Download URL could not be generated."))
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'self',
        }

    def action_open_restore_wizard(self):
        """Opens the restore confirmation wizard."""
        self.ensure_one()
        return {
            'name': _("Restore Backup Database"),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.restore.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_backup_id': self.id,
                'default_project_name': self.project_name,
                'default_backup_filename': self.filename,
                'default_target_branch': self.branch_name or 'main',
            },
        }
