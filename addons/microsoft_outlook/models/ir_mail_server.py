# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import smtplib
import threading


from odoo import api, models, tools, _
from odoo.exceptions import UserError

SMTP_TIMEOUT = 60


class IrMailServer(models.Model):
    """Add the Outlook OAuth authentication on the outgoing mail servers."""

    _name = 'ir.mail_server'
    _inherit = ['ir.mail_server', 'microsoft.outlook.mixin']

    _OUTLOOK_SCOPE = 'https://outlook.office.com/SMTP.Send'

    @api.constrains('use_microsoft_outlook_service', 'smtp_pass', 'smtp_encryption')
    def _check_use_microsoft_outlook_service(self):
        for server in self:
            if not server.use_microsoft_outlook_service:
                continue

            if server.smtp_pass:
                raise UserError(_(
                    'Please leave the password field empty for Outlook mail server %r. '
                    'The OAuth process does not require it')
                    % server.name)

            if server.smtp_encryption != 'starttls':
                raise UserError(_(
                    'Incorrect Connection Security for Outlook mail server %r. '
                    'Please set it to "TLS (STARTTLS)".')
                    % server.name)

    @api.onchange('smtp_encryption')
    def _onchange_encryption(self):
        """Do not change the SMTP configuration if it's a Outlook server

        (e.g. the port which is already set)"""
        if not self.use_microsoft_outlook_service:
            super()._onchange_encryption()

    @api.onchange('use_microsoft_outlook_service')
    def _onchange_use_microsoft_outlook_service(self):
        if self.use_microsoft_outlook_service:
            self.smtp_host = 'smtp.outlook.com'
            self.smtp_encryption = 'starttls'
            self.smtp_port = 587
        else:
            self.microsoft_outlook_refresh_token = False
            self.microsoft_outlook_access_token = False
            self.microsoft_outlook_access_token_expiration = False

    def connect(self, host=None, port=None, user=None, password=None,
                encryption=None, smtp_debug=False, mail_server_id=None):
        # Do not actually connect while running in test mode
        if getattr(threading.currentThread(), 'testing', False):
            return None
        if not (len(self) == 1 and self.use_microsoft_outlook_service):
            return super(IrMailServer, self).connect(
                host, port, user, password, encryption, smtp_debug,
                mail_server_id)
        mail_server = None
        if mail_server_id:
            mail_server = self.sudo().browse(mail_server_id)

        elif not host:
            mail_server = self.sudo().search([], order='sequence', limit=1)

        if mail_server:
            smtp_server = mail_server.smtp_host
            smtp_port = mail_server.smtp_port
            smtp_user = mail_server.smtp_user
            smtp_encryption = mail_server.smtp_encryption
            smtp_debug = smtp_debug or mail_server.smtp_debug
        else:
            smtp_server = host or tools.config.get('smtp_server')
            smtp_port = tools.config.get('smtp_port',
                                         25) if port is None else port
            smtp_user = user or tools.config.get('smtp_user')
            smtp_encryption = encryption
            if smtp_encryption is None and tools.config.get('smtp_ssl'):
                smtp_encryption = 'starttls'  # smtp_ssl => STARTTLS as of v7

        if not smtp_server:
            raise UserError(
                (_("Missing SMTP Server") + "\n" +
                 _("Please define at least one SMTP server, "
                   "or provide the SMTP parameters explicitly.")))

        if smtp_encryption == 'ssl':
            if 'SMTP_SSL' not in smtplib.__all__:
                raise UserError(
                    _("Your Odoo Server does not support SMTP-over-SSL. "
                      "You could use STARTTLS instead. "
                      "If SSL is needed, an upgrade to Python 2.6 on the server-side "
                      "should do the trick."))
            connection = smtplib.SMTP_SSL(smtp_server, smtp_port,
                                          timeout=SMTP_TIMEOUT)
        else:
            connection = smtplib.SMTP(smtp_server, smtp_port,
                                      timeout=SMTP_TIMEOUT)
        connection.set_debuglevel(smtp_debug)
        if smtp_encryption == 'starttls':
            connection.starttls()

        auth_string = self._generate_outlook_oauth2_string(smtp_user)
        oauth_param = base64.b64encode(auth_string.encode()).decode()
        connection.ehlo()
        connection.docmd('AUTH', 'XOAUTH2 %s' % oauth_param)
        return connection

