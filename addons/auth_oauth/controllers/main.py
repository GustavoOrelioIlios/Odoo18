# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import functools
import json
import logging

import werkzeug.urls # type: ignore
from werkzeug.exceptions import BadRequest # type: ignore

from odoo import api, http, SUPERUSER_ID, _
from odoo.exceptions import AccessDenied
from odoo.http import request, Response
from odoo import registry as registry_get
from odoo.tools.misc import clean_context

from odoo.addons.auth_signup.controllers.main import AuthSignupHome as Home # type: ignore
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url # type: ignore

import requests # type: ignore
import jwt # type: ignore


_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# helpers
#----------------------------------------------------------
def fragment_to_query_string(func):
    @functools.wraps(func)
    def wrapper(self, *a, **kw):
        kw.pop('debug', False)
        if not kw:
            return Response("""<html><head><script>
                var l = window.location;
                var q = l.hash.substring(1);
                var r = l.pathname + l.search;
                if(q.length !== 0) {
                    var s = l.search ? (l.search === '?' ? '' : '&') : '?';
                    r = l.pathname + l.search + s + q;
                }
                if (r == l.pathname) {
                    r = '/';
                }
                window.location = r;
            </script></head><body></body></html>""")
        return func(self, *a, **kw)
    return wrapper


#----------------------------------------------------------
# Controller
#----------------------------------------------------------
class OAuthLogin(Home):
    def list_providers(self):
        try:
            providers = request.env['auth.oauth.provider'].sudo().search_read([('enabled', '=', True)])
        except Exception:
            providers = []
        for provider in providers:
            return_url = request.httprequest.url_root + 'callback'
            state = self.get_state(provider)
            params = dict(
                url=return_url,
                clientId=provider['client_id']
            )
            provider['auth_link'] = "%s?%s" % (provider['auth_endpoint'], werkzeug.urls.url_encode(params))
        return providers

    def get_state(self, provider):
        redirect = request.params.get('redirect') or 'web'
        if not redirect.startswith(('//', 'http://', 'https://')):
            redirect = '%s%s' % (request.httprequest.url_root, redirect[1:] if redirect[0] == '/' else redirect)
        state = dict(
            d=request.session.db,
            p=provider['id'],
            r=werkzeug.urls.url_quote_plus(redirect),
        )
        token = request.params.get('token')
        if token:
            state['t'] = token
        return state

    @http.route()
    def web_login(self, *args, **kw):
        ensure_db()
        if request.httprequest.method == 'GET' and request.session.uid and request.params.get('redirect'):
            # Redirect if already logged in and redirect param is present
            return request.redirect(request.params.get('redirect'))
        providers = self.list_providers()

        response = super(OAuthLogin, self).web_login(*args, **kw)
        if response.is_qweb:
            error = request.params.get('oauth_error')
            if error == '1':
                error = _("Não é permitido se cadastrar neste banco de dados.")
            elif error == '2':
                error = _("Acesso negado")
            elif error == '3':
                error = _("Você não tem acesso a esse sistema.")
            else:
                error = None

            response.qcontext['providers'] = providers
            if error:
                response.qcontext['error'] = error

        return response

    def get_auth_signup_qcontext(self):
        result = super(OAuthLogin, self).get_auth_signup_qcontext()
        result["providers"] = self.list_providers()
        return result


class OAuthController(http.Controller):

    @http.route('/auth_oauth/signin', type='http', auth='none', readonly=False)
    @fragment_to_query_string
    def signin(self, **kw):
        state = json.loads(kw['state'])

        # make sure request.session.db and state['d'] are the same,
        # update the session and retry the request otherwise
        dbname = state['d']
        if not http.db_filter([dbname]):
            return BadRequest()
        ensure_db(db=dbname)

        provider = state['p']
        request.update_context(**clean_context(state.get('c', {})))
        try:
            # auth_oauth may create a new user, the commit makes it
            # visible to authenticate()'s own transaction below
            _, login, key = request.env['res.users'].with_user(SUPERUSER_ID).auth_oauth(provider, kw)
            request.env.cr.commit()

            action = state.get('a')
            menu = state.get('m')
            redirect = werkzeug.urls.url_unquote_plus(state['r']) if state.get('r') else False
            url = '/odoo'
            if redirect:
                url = redirect
            elif action:
                url = '/odoo/action-%s' % action
            elif menu:
                url = '/odoo?menu_id=%s' % menu

            credential = {'login': login, 'token': key, 'type': 'oauth_token'}
            auth_info = request.session.authenticate(dbname, credential)
            resp = request.redirect(_get_login_redirect_url(auth_info['uid'], url), 303)
            resp.autocorrect_location_header = False

            # Since /web is hardcoded, verify user has right to land on it
            if werkzeug.urls.url_parse(resp.location).path == '/web' and not request.env.user._is_internal():
                resp.location = '/'
            return resp
        except AttributeError:  # TODO juc master: useless since ensure_db()
            # auth_signup is not installed
            _logger.error("auth_signup not installed on database %s: oauth sign up cancelled.", dbname)
            url = "/web/login?oauth_error=1"
        except AccessDenied:
            # oauth credentials not valid, user could be on a temporary session
            _logger.info('OAuth2: access denied, redirect to main page in case a valid session exists, without setting cookies')
            url = "/web/login?oauth_error=3"
        except Exception:
            # signup error
            _logger.exception("Exception during request handling")
            url = "/web/login?oauth_error=2"

        redirect = request.redirect(url, 303)
        redirect.autocorrect_location_header = False
        return redirect

    @http.route('/auth_oauth/oea', type='http', auth='none', readonly=False)
    def oea(self, **kw):
        """login user via Odoo Account provider"""
        dbname = kw.pop('db', None)
        if not dbname:
            dbname = request.db
        if not dbname:
            raise BadRequest()
        if not http.db_filter([dbname]):
            raise BadRequest()

        registry = registry_get(dbname)
        with registry.cursor() as cr:
            try:
                env = api.Environment(cr, SUPERUSER_ID, {})
                provider = env.ref('auth_oauth.provider_openerp')
            except ValueError:
                redirect = request.redirect(f'/web?db={dbname}', 303)
                redirect.autocorrect_location_header = False
                return redirect
            assert provider._name == 'auth.oauth.provider'

        state = {
            'd': dbname,
            'p': provider.id,
            'c': {'no_user_creation': True},
        }

        kw['state'] = json.dumps(state)
        return self.signin(**kw)

    @http.route('/callback', type='http', auth='none', readonly=False)
    def callback(self, **kw):
        """
        Processa o callback do G10 SSO após autenticação bem-sucedida.
        """
        # Validação inicial do token
        token = kw.get('token')
        if not token:
            _logger.error("G10 SSO: Token não encontrado na requisição")
            return request.redirect('/web/login?oauth_error=2')
            
        try:
            # Configuração inicial
            ensure_db()
            dbname = request.session.db
            
            if not http.db_filter([dbname]):
                return BadRequest()
            
            # Busca o provedor OAuth do G10
            provider = request.env['auth.oauth.provider'].sudo().search([
                ('enabled', '=', True),
                ('auth_endpoint', 'ilike', '%g10%')  
            ], limit=1)
            
            if not provider:
                _logger.error("G10 SSO: Provedor OAuth do G10 não encontrado ou desativado")
                return request.redirect('/web/login?oauth_error=2')

            if not provider.data_endpoint:
                _logger.error("G10 SSO: Endpoint de dados não configurado no provedor OAuth")
                return request.redirect('/web/login?oauth_error=2')

            # Remove trailing slash if exists
            base_url = provider.data_endpoint.rstrip('/')
            
            # Decodifica o token JWT para obter o ID do usuário
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            
            user_id = decoded_token.get('sub')
            if not user_id:
                _logger.error("G10 SSO: ID do usuário não encontrado no token")
                return request.redirect('/web/login?oauth_error=2')
            
            # Busca informações do usuário na API do G10
            headers = {'Authorization': f'Bearer {token}'}
            
            # Primeiro busca informações básicas do usuário
            user_info_response = requests.get(
                f'{base_url}/users/{user_id}',
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if not user_info_response.ok:
                _logger.error("G10 SSO: Erro ao buscar informações do usuário. Status: %s, Resposta: %s", 
                            user_info_response.status_code, user_info_response.text)
                return request.redirect('/web/login?oauth_error=2')
            
            user_info = user_info_response.json()
            
            # Extrai informações básicas do usuário
            login = user_info.get('username')
            name = user_info.get('name')
            
            if not login or not name:
                _logger.error("G10 SSO: Informações básicas do usuário não encontradas")
                return request.redirect('/web/login?oauth_error=2')
            
            # Busca os sistemas e roles do usuário
            user_systems_response = requests.get(
                f'{base_url}/user-system/user/{user_id}',
                headers=headers,
                timeout=10,
                verify=False
            )
            
            if not user_systems_response.ok:
                _logger.error("G10 SSO: Erro ao buscar sistemas do usuário. Status: %s, Resposta: %s", 
                            user_systems_response.status_code, user_systems_response.text)
                return request.redirect('/web/login?oauth_error=2')
            
            user_systems_info = user_systems_response.json()
            
            # Procura o sistema atual nos sistemas do usuário
            current_system = None
            has_active_role = False
            for system in user_systems_info.get('data', []):
                if system.get('id') == provider.system_id:
                    current_system = system
                    # Verifica se tem pelo menos um role ativo
                    for role in system.get('roles', []):
                        if role.get('active'):
                            has_active_role = True
                            break
                    break
            
            if not current_system:
                _logger.warning("G10 SSO: Usuário %s não tem acesso ao sistema %s", login, provider.system_id)
                return request.redirect('/web/login?oauth_error=3&error_message=Você não tem acesso a este sistema. Por favor, entre em contato com o administrador.')
            
            if not has_active_role:
                _logger.warning("G10 SSO: Usuário %s não tem roles ativos no sistema %s", login, provider.system_id)
                return request.redirect('/web/login?oauth_error=3&error_message=Você não tem permissões ativas neste sistema. Por favor, entre em contato com o administrador.')

            # Verifica os roles ativos do usuário no sistema atual
            user_roles = []
            for role in current_system.get('roles', []):
                if role.get('active'):
                    user_roles.append(role.get('name'))

            registry = registry_get(dbname)
            with registry.cursor() as new_cr:
                env = api.Environment(new_cr, SUPERUSER_ID, {})
                
                try:
                    # Busca usuário existente ou cria um novo
                    user = env['res.users'].sudo().search([
                        ('oauth_uid', '=', str(user_id)),
                        ('oauth_provider_id', '=', provider.id)
                    ], limit=1)
                    
                    # Se não encontrou por oauth_uid, tenta encontrar por email
                    if not user:
                        existing_user = env['res.users'].sudo().search([
                            ('login', '=', login)
                        ], limit=1)

                        if existing_user:
                            user = existing_user
                    
                    if user:
                        # Atualiza as informações do usuário existente
                        user.sudo().write({
                            'oauth_uid': str(user_id),
                            'oauth_provider_id': provider.id,
                            'oauth_access_token': token,
                            'name': name,
                            'email': login,
                            'active': True,
                        })
                    else:
                        # Configuração de grupos e empresa
                        company = env['res.company'].sudo().search([], limit=1)
                        default_group = env.ref('base.group_user', raise_if_not_found=False)
                        
                        group_ids = []
                        if default_group:
                            group_ids.append(default_group.id)
                        
                        # Cria parceiro (res.partner)
                        partner = env['res.partner'].sudo().create({
                            'name': name,
                            'email': login,
                            'company_id': company.id,
                        })
                        
                        # Cria usuário com todos os valores necessários
                        user = env['res.users'].sudo().create({
                            'name': name,
                            'login': login,
                            'email': login,
                            'partner_id': partner.id,
                            'company_id': company.id,
                            'company_ids': [(6, 0, [company.id])],
                            'groups_id': [(6, 0, group_ids)],
                            'oauth_uid': str(user_id),
                            'oauth_provider_id': provider.id,
                            'oauth_access_token': token,
                            'active': True,
                        })
                    
                    # Mapeia os grupos do pátio baseado nos roles do SSO
                    parking_admin_group = env.ref('parking_management.group_parking_admin', raise_if_not_found=False)
                    parking_manager_group = env.ref('parking_management.group_parking_manager', raise_if_not_found=False)
                    parking_user_group = env.ref('parking_management.group_parking_user', raise_if_not_found=False)
                    
                    if parking_admin_group and parking_manager_group and parking_user_group:
                        # Remove usuário de todos os grupos do pátio existentes
                        user.sudo().write({
                            'groups_id': [
                                (3, parking_admin_group.id),
                                (3, parking_manager_group.id),
                                (3, parking_user_group.id)
                            ]
                        })
                        
                        # Adiciona aos grupos apropriados baseado nos roles
                        for role in user_roles:
                            if role == 'Admin':
                                user.sudo().write({
                                    'groups_id': [(4, parking_admin_group.id)]
                                })
                            elif role == 'Operador':
                                user.sudo().write({
                                    'groups_id': [(4, parking_manager_group.id)]
                                })
                            elif role == 'Visualização':
                                user.sudo().write({
                                    'groups_id': [(4, parking_user_group.id)]
                                })
                    else:
                        _logger.error("G10 SSO: Grupos do módulo de pátio não encontrados")
                        return request.redirect('/web/login?oauth_error=2')
                    
                    # Commit as alterações antes da autenticação
                    new_cr.commit()
                    
                    # Limpa a sessão atual
                    request.session.logout()
                    
                    # Prepara as credenciais para autenticação
                    credential = {
                        'login': user.login,
                        'token': token,
                        'type': 'oauth_token'
                    }
                    
                    # Autentica o usuário
                    auth_info = request.session.authenticate(dbname, credential)
                    if auth_info:
                        return request.redirect('/web')
                    else:
                        _logger.error("G10 SSO: Falha na autenticação após criação/atualização do usuário")
                        return request.redirect('/web/login?oauth_error=2')
                    
                except Exception as e:
                    _logger.exception("G10 SSO: Erro ao processar autenticação: %s", str(e))
                    return request.redirect('/web/login?oauth_error=2')
            
        except Exception as e:
            _logger.exception("G10 SSO: Erro ao processar callback: %s", str(e))
            return request.redirect('/web/login?oauth_error=2')
