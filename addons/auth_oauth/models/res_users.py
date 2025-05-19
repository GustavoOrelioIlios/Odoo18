# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests # type: ignore
import jwt # type: ignore

from odoo import api, fields, models
from odoo.exceptions import AccessDenied, UserError
from odoo.addons.auth_signup.models.res_users import SignupError # type: ignore

from odoo.addons import base
base.models.res_users.USER_PRIVATE_FIELDS.append('oauth_access_token')

_logger = logging.getLogger(__name__)

class ResUsers(models.Model):
    _inherit = 'res.users'

    oauth_provider_id = fields.Many2one('auth.oauth.provider', string='OAuth Provider')
    oauth_uid = fields.Char(string='OAuth User ID', help="Oauth Provider user_id", copy=False)
    oauth_access_token = fields.Char(string='OAuth Access Token', readonly=True, copy=False, prefetch=False)

    _sql_constraints = [
        ('uniq_users_oauth_provider_oauth_uid', 'unique(oauth_provider_id, oauth_uid)', 'OAuth UID must be unique per provider'),
    ]

    @api.model
    def _auth_oauth_validate(self, provider, access_token):
        """ return the validation data corresponding to the access token """
        oauth_provider = self.env['auth.oauth.provider'].browse(provider)
        validation = {}
        
        # For G10 SSO provider, handle token validation differently
        if oauth_provider.data_endpoint and 'g10transportes.com.br' in oauth_provider.data_endpoint:
            try:
                _logger.info("G10 SSO: Starting token validation process")
                
                # Clean up token if it comes with 'token=' prefix
                if access_token and access_token.startswith('token='):
                    access_token = access_token[6:]  # Remove 'token=' prefix
                
                _logger.info("G10 SSO: Token received (cleaned): %s", access_token[:10] + "..." if access_token else None)
                
                # Parse JWT token to get user ID
                try:
                    decoded_token = jwt.decode(access_token, options={"verify_signature": False})
                    _logger.info("G10 SSO: Decoded token contents: %s", decoded_token)
                except jwt.InvalidTokenError as e:
                    _logger.error("G10 SSO: Invalid token format: %s", str(e))
                    raise AccessDenied('Invalid token format')
                
                # Check token expiration
                exp = decoded_token.get('exp')
                if exp:
                    import time
                    current_time = int(time.time())
                    _logger.info("G10 SSO: Token expiration: %s, Current time: %s", exp, current_time)
                    if current_time > exp:
                        _logger.error("G10 SSO: Token has expired")
                        raise AccessDenied('Token has expired')
                
                # Get user info from G10 SSO
                user_id = decoded_token.get('sub')
                if not user_id:
                    _logger.error("G10 SSO: Missing subject identity in token")
                    raise AccessDenied('Missing subject identity in token')
                    
                _logger.info("G10 SSO: Making API request for user_id: %s", user_id)
                    
                # Get user info from G10 API
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Cookie': f'token={access_token}'  # Add token as cookie as well
                }
                _logger.info("G10 SSO: Request headers: %s", headers)
                
                api_url = f'https://sso-api.v2.homolog.g10transportes.com.br/users/{user_id}'
                _logger.info("G10 SSO: Making request to: %s", api_url)
                
                response = requests.get(
                    api_url,
                    headers=headers,
                    timeout=10,
                    verify=False
                )
                
                _logger.info("G10 SSO: API Response status: %s", response.status_code)
                _logger.info("G10 SSO: API Response headers: %s", response.headers)
                _logger.info("G10 SSO: API Response body: %s", response.text)
                
                if not response.ok:
                    _logger.error("G10 SSO: Failed to get user info. Status: %s, Response: %s", 
                                response.status_code, response.text)
                    raise AccessDenied()
                    
                validation = response.json()
                validation['user_id'] = str(user_id)  # Ensure user_id is string
                
            except Exception as e:
                _logger.error("G10 SSO: Error getting user info: %s", str(e))
                raise AccessDenied()
                
        return validation

    @api.model
    def _generate_signup_values(self, provider, validation, params):
        oauth_uid = validation['user_id']
        email = validation.get('username', 'provider_%s_user_%s' % (provider, oauth_uid))
        name = validation.get('name', email)
        return {
            'name': name,
            'login': email,
            'email': email,
            'oauth_provider_id': provider,
            'oauth_uid': oauth_uid,
            'oauth_access_token': params['access_token'],
            'active': True,
        }

    @api.model
    def _auth_oauth_signin(self, provider, validation, params):
        """ retrieve and sign in the user corresponding to provider and validated access token
            :param provider: oauth provider id (int)
            :param validation: result of validation of access token (dict)
            :param params: oauth parameters (dict)
            :return: user login (str)
            :raise: AccessDenied if signin failed

            This method can be overridden to add alternative signin methods.
        """
        oauth_uid = validation['user_id']
        try:
            oauth_user = self.search([("oauth_uid", "=", oauth_uid), ('oauth_provider_id', '=', provider)])
            if not oauth_user:
                raise AccessDenied()
            assert len(oauth_user) == 1
            oauth_user.write({'oauth_access_token': params['access_token']})
            return oauth_user.login
        except AccessDenied as access_denied_exception:
            if self.env.context.get('no_user_creation'):
                return None
            state = json.loads(params['state'])
            token = state.get('t')
            values = self._generate_signup_values(provider, validation, params)
            try:
                login, _ = self.signup(values, token)
                return login
            except (SignupError, UserError):
                raise access_denied_exception

    @api.model
    def auth_oauth(self, provider, params):
        # Advice by Google (to avoid Confused Deputy Problem)
        # if validation.audience != OUR_CLIENT_ID:
        #   abort()
        # else:
        #   continue with the process
        access_token = params.get('access_token')
        validation = self._auth_oauth_validate(provider, access_token)

        # retrieve and sign in user
        login = self._auth_oauth_signin(provider, validation, params)
        if not login:
            raise AccessDenied()
        # return user credentials
        return (self.env.cr.dbname, login, access_token)

    def _check_credentials(self, credential, env):
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if not (credential['type'] == 'oauth_token' and credential['token']):
                raise
            passwd_allowed = env['interactive'] or not self.env.user._rpc_api_keys_only()
            if passwd_allowed and self.env.user.active:
                res = self.sudo().search([('id', '=', self.env.uid), ('oauth_access_token', '=', credential['token'])])
                if res:
                    return {
                        'uid': self.env.user.id,
                        'auth_method': 'oauth',
                        'mfa': 'default',
                    }
            raise

    def _get_session_token_fields(self):
        return super(ResUsers, self)._get_session_token_fields() | {'oauth_access_token'}
