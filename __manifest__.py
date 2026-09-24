# -*- coding: utf-8 -*-
{
    'name': 'Odoo Fleet Control Connector',
    'version': '18.0.1.0.0',
    'category': 'Administration/DevOps',
    'summary': 'Control and interact with your multi-project Odoo fleet, staging branches, backups, and builds using Personal API Tokens.',
    'description': """
Odoo Fleet Control Room Connector
=================================
Seamlessly manage your Odoo.sh-style multi-project fleet platform directly from inside Odoo:

Key Features:
-------------
* **Personal Access Token Auth & RBAC**: Connect using your personal API key or role-based token (Admin, Developer, Viewer).
* **Multi-Project Management**: View production status, Traefik routes, database health, and container state.
* **Ephemeral Branch Staging**: Create on-demand staging environments from GitHub branches and destroy them when finished.
* **One-Click Deployments**: Trigger production and staging deployments directly from Odoo.
* **Automated Database Backups**: Take manual or pre-deploy database dumps, view backup size and timestamps, and trigger restores.
* **Database Safety Controls**: Neutralize staging environments, toggle test/live payment gateways, and enable/disable mail servers.
* **AI Error Diagnosis**: Analyze Odoo server logs, detect offending modules, and execute automated quick fixes.
* **Audit Trail**: Real-time logging of fleet actions and operator history.
    """,
    'author': 'Prixgen Tech Solutions',
    'website': 'https://www.prixgen.com',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/fleet_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/res_users_views.xml',
        'views/fleet_project_views.xml',
        'views/fleet_branch_views.xml',
        'views/fleet_backup_views.xml',
        'views/fleet_build_views.xml',
        'views/fleet_safety_views.xml',
        'views/fleet_error_resolver_views.xml',
        'views/fleet_audit_log_views.xml',
        'wizard/fleet_wizard_views.xml',
        'views/fleet_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'fleet_connector/static/src/scss/fleet_style.scss',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}
