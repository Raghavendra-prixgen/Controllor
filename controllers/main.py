# -*- coding: utf-8 -*-
import json
import logging
from odoo import http, _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class FleetController(http.Controller):

    @http.route('/fleet/ping', type='http', auth='none', methods=['GET'], csrf=False)
    def fleet_ping(self, **kwargs):
        """Simple liveness probe for the connector."""
        return Response(
            json.dumps({"status": "ok", "service": "Odoo Fleet Connector"}),
            content_type="application/json;charset=utf-8",
            status=200,
        )

    @http.route('/fleet/webhook/sync', type='json', auth='none', methods=['POST'], csrf=False)
    def fleet_webhook_sync(self, **kwargs):
        """Webhook listener to trigger project/build sync automatically when push occurs."""
        data = request.jsonrequest if hasattr(request, 'jsonrequest') else {}
        project_name = data.get('project')
        _logger.info("Fleet webhook sync triggered for project: %s", project_name)

        try:
            request.env['fleet.project'].sudo().action_sync_all_projects()
            if project_name:
                request.env['fleet.build'].sudo().action_sync_builds_for_project(project_name)
            return {"ok": True, "message": "Fleet synchronization completed."}
        except Exception as e:
            _logger.error("Fleet webhook sync error: %s", e)
            return {"ok": False, "error": str(e)}
