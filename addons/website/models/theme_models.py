# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import api, fields, models
from odoo.tools.translate import xml_translate
from odoo.modules.module import get_resource_from_path

_logger = logging.getLogger(__name__)


class ThemeView(models.Model):
    _name = 'theme.ir.ui.view'
    _description = 'Theme UI View'

    def compute_arch_fs(self):
        if 'install_filename' not in self._context:
            return ''
        path_info = get_resource_from_path(self._context['install_filename'])
        if path_info:
            return '/'.join(path_info[0:2])

    name = fields.Char(required=True)
    key = fields.Char()
    type = fields.Char()
    priority = fields.Integer(default=16, required=True)
    mode = fields.Selection([('primary', "Base view"), ('extension', "Extension View")])
    active = fields.Boolean(default=True)
    arch = fields.Text(translate=xml_translate)
    arch_fs = fields.Char(default=compute_arch_fs)
    inherit_id = fields.Reference(selection=[('ir.ui.view', 'ir.ui.view'), ('theme.ir.ui.view', 'theme.ir.ui.view')])
    copy_ids = fields.One2many('ir.ui.view', 'theme_template_id', 'Views using a copy of me', copy=False, readonly=True)
    customize_show = fields.Boolean()

    def _convert_to_base_model(self, website, **kwargs):
        self.ensure_one()
        inherit = self.inherit_id
        if self.inherit_id and self.inherit_id._name == 'theme.ir.ui.view':
            inherit = self.inherit_id.with_context(active_test=False).copy_ids.filtered(lambda x: x.website_id == website)
            if not inherit:
                # inherit_id not yet created, add to the queue
                return False

        if inherit and inherit.website_id != website:
            website_specific_inherit = self.env['ir.ui.view'].with_context(active_test=False).search([
                ('key', '=', inherit.key),
                ('website_id', '=', website.id)
            ], limit=1)
            if website_specific_inherit:
                inherit = website_specific_inherit

        new_view = {
            'type': self.type or 'qweb',
            'name': self.name,
            'arch': self.arch,
            'key': self.key,
            'inherit_id': inherit and inherit.id,
            'arch_fs': self.arch_fs,
            'priority': self.priority,
            'active': self.active,
            'theme_template_id': self.id,
            'website_id': website.id,
            'customize_show': self.customize_show,
        }

        if self.mode:  # if not provided, it will be computed automatically (if inherit_id or not)
            new_view['mode'] = self.mode

        return new_view


class ThemeAttachment(models.Model):
    _name = 'theme.ir.attachment'
    _description = 'Theme Attachments'

    name = fields.Char(required=True)
    key = fields.Char(required=True)
    url = fields.Char()
    copy_ids = fields.One2many('ir.attachment', 'theme_template_id', 'Attachment using a copy of me', copy=False, readonly=True)


    def _convert_to_base_model(self, website, **kwargs):
        self.ensure_one()
        new_attach = {
            'key': self.key,
            'public': True,
            'res_model': 'ir.ui.view',
            'type': 'url',
            'name': self.name,
            'url': self.url,
            'website_id': website.id,
            'theme_template_id': self.id,
        }
        return new_attach


class ThemeMenu(models.Model):
    _name = 'theme.website.menu'
    _description = 'Website Theme Menu'

    name = fields.Char(required=True, translate=True)
    url = fields.Char(default='')
    page_id = fields.Many2one('theme.website.page', ondelete='cascade')
    new_window = fields.Boolean('New Window')
    sequence = fields.Integer()
    parent_id = fields.Many2one('theme.website.menu', index=True, ondelete="cascade")
    copy_ids = fields.One2many('website.menu', 'theme_template_id', 'Menu using a copy of me', copy=False, readonly=True)

    def _convert_to_base_model(self, website, **kwargs):
        self.ensure_one()
        page_id = self.page_id.copy_ids.filtered(lambda x: x.website_id == website)
        parent_id = self.copy_ids.filtered(lambda x: x.website_id == website)
        new_menu = {
            'name': self.name,
            'url': self.url,
            'page_id': page_id and page_id.id or False,
            'new_window': self.new_window,
            'sequence': self.sequence,
            'parent_id': parent_id and parent_id.id or False,
            'theme_template_id': self.id,
        }
        return new_menu


class ThemePage(models.Model):
    _name = 'theme.website.page'
    _description = 'Website Theme Page'

    url = fields.Char()
    view_id = fields.Many2one('theme.ir.ui.view', required=True, ondelete="cascade")
    website_indexed = fields.Boolean('Page Indexed', default=True)
    copy_ids = fields.One2many('website.page', 'theme_template_id', 'Page using a copy of me', copy=False, readonly=True)

    def _convert_to_base_model(self, website, **kwargs):
        self.ensure_one()
        view_id = self.view_id.copy_ids.filtered(lambda x: x.website_id == website)
        if not view_id:
            # inherit_id not yet created, add to the queue
            return False

        new_page = {
            'url': self.url,
            'view_id': view_id.id,
            'website_indexed': self.website_indexed,
            'theme_template_id': self.id,
        }
        return new_page


class Theme(models.AbstractModel):
    _name = 'theme.utils'
    _description = 'Theme Utils'
    _auto = False

    def _post_copy(self, mod):
        # Call specific theme post copy
        theme_post_copy = '_%s_post_copy' % mod.name
        if hasattr(self, theme_post_copy):
            _logger.info('Executing method %s' % theme_post_copy)
            method = getattr(self, theme_post_copy)
            return method(mod)
        return False

    @api.model
    def _reset_default_config(self):
        # Reinitialize some css customizations
        self.env['web_editor.assets'].make_scss_customization(
            '/website/static/src/scss/options/user_values.scss',
            {
                'font': 'null',
                'headings-font': 'null',
                'navbar-font': 'null',
                'buttons-font': 'null',
                'color-palettes-number': 'null',
                'header-template': 'null',
                'footer-template': 'null',
            }
        )

        # Reinitialize header templates
        self.disable_view('website.template_header_hamburger')
        self.disable_view('website.template_header_hamburger_left')
        self.disable_view('website.template_header_navbar_text_center')

        # Reinitialize footer templates
        self.enable_view('website.footer_custom')
        self.disable_view('website.template_footer_logo_about_us_below')
        self.disable_view('website.template_footer_links_address_logo')
        self.disable_view('website.template_footer_name_logo_links_about_us')
        self.disable_view('website.template_footer_logo_only')
        self.disable_view('website.template_footer_address_logo')

    @api.model
    def _toggle_view(self, xml_id, active):
        obj = self.env.ref(xml_id)
        website = self.env['website'].get_current_website()
        if obj._name == 'theme.ir.ui.view':
            obj = obj.with_context(active_test=False)
            obj = obj.copy_ids.filtered(lambda x: x.website_id == website)
        else:
            # If a theme post copy wants to enable/disable a view, this is to
            # enable/disable a given functionality which is disabled/enabled
            # by default. So if a post copy asks to enable/disable a view which
            # is already enabled/disabled, we would not consider it otherwise it
            # would COW the view for nothing.
            View = self.env['ir.ui.view'].with_context(active_test=False)
            has_specific = obj.key and View.search_count([
                ('key', '=', obj.key),
                ('website_id', '=', website.id)
            ]) >= 1
            if not has_specific and active == obj.active:
                return
        obj.write({'active': active})

    @api.model
    def enable_view(self, xml_id):
        self._toggle_view(xml_id, True)

    @api.model
    def disable_view(self, xml_id):
        self._toggle_view(xml_id, False)


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    theme_template_id = fields.Many2one('theme.ir.ui.view')

    def write(self, vals):
        no_arch_updated_views = other_views = self.env['ir.ui.view']
        for record in self:
            # Do not mark the view as user updated if original view arch is similar
            arch = vals.get('arch', vals.get('arch_base'))
            if record.theme_template_id and record.theme_template_id.arch == arch:
                no_arch_updated_views += record
            else:
                other_views += record
        res = super(IrUiView, other_views).write(vals)
        if no_arch_updated_views:
            vals['arch_updated'] = False
            res &= super(IrUiView, no_arch_updated_views).write(vals)
        return res

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    key = fields.Char()
    theme_template_id = fields.Many2one('theme.ir.attachment')


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    theme_template_id = fields.Many2one('theme.website.menu')


class WebsitePage(models.Model):
    _inherit = 'website.page'

    theme_template_id = fields.Many2one('theme.website.page')
