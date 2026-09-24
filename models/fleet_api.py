# -*- coding: utf-8 -*-
import json
import logging
import urllib.parse
import requests
from odoo import _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class FleetAPIClient:
    """
    Fleet Platform REST API Client
    Handles Bearer token authentication, RBAC rights resolution, and API communication.
    """

    def __init__(self, base_url: str, token: str = "", timeout: int = 15):
        self.base_url = (base_url or "").strip().rstrip("/")
        self.token = (token or "").strip()
        self.timeout = timeout

    @classmethod
    def from_env(cls, env):
        """
        Instantiates FleetAPIClient using current user credentials or system fallback.
        """
        user = env.user
        base_url = user.fleet_api_url or env['ir.config_parameter'].sudo().get_param(
            'fleet.platform_url', 'http://127.0.0.1:8000'
        )
        token = user.get_fleet_token()
        return cls(base_url=base_url, token=token)

    def _headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Odoo-Fleet-Connector/18.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-API-Key"] = self.token
            headers["X-Platform-Key"] = self.token
        return headers

    def _request(self, method: str, endpoint: str, params: dict = None, data: dict = None, timeout: int = None) -> dict:
        if not self.base_url:
            raise UserError(_("Fleet Platform Base URL is not configured. Please configure it in Settings or your User Profile."))

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_timeout = timeout or self.timeout

        try:
            resp = requests.request(
                method=method.upper(),
                url=url,
                headers=self._headers(),
                params=params,
                json=data if data is not None else None,
                timeout=req_timeout,
            )
        except requests.exceptions.ConnectionError as e:
            _logger.error("Fleet connection failed to %s: %s", url, e)
            raise UserError(_("Could not connect to Fleet Platform at %s. Please check if the service is running and accessible.") % self.base_url)
        except requests.exceptions.Timeout:
            _logger.error("Fleet connection timeout to %s", url)
            raise UserError(_("Connection to Fleet Platform at %s timed out after %s seconds.") % (self.base_url, req_timeout))
        except Exception as e:
            _logger.error("Fleet unexpected request error: %s", e)
            raise UserError(_("Error communicating with Fleet Platform: %s") % str(e))

        try:
            result = resp.json()
        except Exception:
            result = {"ok": resp.status_code in (200, 201), "raw_body": resp.text}

        if resp.status_code == 401:
            err_msg = result.get("error") or _("Authentication failed. Please verify your Personal API Token in your User Profile.")
            raise UserError(_("Fleet Authentication Error (401):\n%s") % err_msg)
        elif resp.status_code == 403:
            err_msg = result.get("error") or _("Access Denied. Your personal token does not have sufficient role permissions for this action.")
            raise UserError(_("Fleet Authorization Error (403):\n%s") % err_msg)
        elif resp.status_code >= 400:
            err_msg = result.get("error") or result.get("output") or result.get("message") or resp.text
            raise UserError(_("Fleet Platform Error (%s):\n%s") % (resp.status_code, err_msg))

        return result

    # --- Core API Endpoints ---

    def verify_token(self, token: str = None) -> dict:
        """Verifies API token validity and resolves role and user identity."""
        target_token = token or self.token
        if not target_token:
            raise ValidationError(_("Please provide a Personal API Token to verify."))
        url = f"{self.base_url}/api/auth/verify"
        try:
            resp = requests.post(url, json={"key": target_token}, headers={"Content-Type": "application/json"}, timeout=8)
            return resp.json()
        except Exception as e:
            raise UserError(_("Failed to verify token with Fleet Platform: %s") % str(e))

    def get_auth_status(self) -> dict:
        return self._request("GET", "/api/auth/status")

    def get_projects(self) -> list:
        res = self._request("GET", "/api/projects")
        return res.get("projects", [])

    def get_status(self) -> dict:
        return self._request("GET", "/api/status")

    def get_system_info(self) -> dict:
        return self._request("GET", "/api/system/info")

    def get_branches(self, project: str) -> list:
        res = self._request("GET", "/api/github/branches", params={"project": project})
        return res.get("branches", [])

    def get_builds(self, project: str, branch: str = "") -> list:
        params = {"project": project}
        if branch:
            params["branch"] = branch
        res = self._request("GET", "/api/builds", params=params)
        return res.get("builds", [])

    def get_build_log(self, project: str, log_file: str) -> str:
        res = self._request("GET", "/api/builds/log", params={"project": project, "file": log_file})
        return res.get("log", "")

    def get_backups(self, project: str = "", branch: str = "") -> list:
        params = {}
        if project:
            params["project"] = project
        if branch:
            params["branch"] = branch
        res = self._request("GET", "/api/backups", params=params)
        return res.get("backups", [])

    def get_database_safety(self, project: str, branch: str = "main") -> dict:
        res = self._request("GET", "/api/database-safety/status", params={"project": project, "branch": branch})
        return res.get("safety", {})

    def set_database_safety(self, project: str, branch: str, action: str, mode: str = "") -> dict:
        payload = {
            "project": project,
            "branch": branch,
            "action": action,
            "mode": mode,
        }
        return self._request("POST", "/api/database-safety/action", data=payload)

    def execute_action(self, action: str, project: str = "", branch: str = "", **kwargs) -> dict:
        payload = {
            "action": action,
            "project": project,
            "branch": branch,
            **kwargs,
        }
        return self._request("POST", "/api/action", data=payload, timeout=90)

    def deploy_main(self, project: str) -> dict:
        return self.execute_action("deploy", project=project, branch="main")

    def create_staging(self, project: str, branch: str, source: str = "main") -> dict:
        return self.execute_action("create", project=project, branch=branch, source=source)

    def destroy_staging(self, project: str, branch: str) -> dict:
        return self.execute_action("destroy", project=project, branch=branch)

    def trigger_backup(self, project: str, branch: str = "main", reason: str = "manual", fmt: str = "dump") -> dict:
        return self.execute_action("backup", project=project, branch=branch, reason=reason, format=fmt)

    def trigger_restore(self, project: str, branch: str, backup_file: str) -> dict:
        return self.execute_action("restore", project=project, branch=branch, backup_file=backup_file)

    def optimize_db(self, project: str, branch: str = "main") -> dict:
        return self.execute_action("optimize", project=project, branch=branch)

    def init_project(self, name: str, repo: str, version: str = "18.0") -> dict:
        return self.execute_action("init", name=name, repo=repo, version=version)

    def delete_project(self, project: str) -> dict:
        return self.execute_action("delete_project", project=project)

    def cleanup_stale(self) -> dict:
        return self.execute_action("cleanup")

    def analyze_error_log(self, project: str = "", branch: str = "main", raw_log: str = "") -> dict:
        payload = {"project": project, "branch": branch, "raw_log": raw_log}
        res = self._request("POST", "/api/error-resolver/analyze", data=payload)
        return res.get("analysis", {})

    def execute_quick_fix(self, project: str, branch: str, action: str, params: dict = None) -> dict:
        payload = {
            "project": project,
            "branch": branch,
            "action": action,
            "params": params or {},
        }
        return self._request("POST", "/api/error-resolver/quick-fix", data=payload)

    def get_audit_logs(self, limit: int = 50) -> list:
        res = self._request("GET", "/api/audit/logs", params={"limit": limit})
        return res.get("logs", [])
