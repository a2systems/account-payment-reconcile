from odoo import tools,fields, models, api, _
from datetime import date,datetime
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        for rec in self:
            if rec.reconcile_ids:
                aml_obj = self.env['account.move.line']
                payment_line = None
                for line in rec.move_id.line_ids:
                    if line.account_id.id == rec.partner_id.property_account_receivable_id.id:
                        payment_line = line
                if payment_line:
                    aml_obj += payment_line
                    amount_uyu = 0
                    for reconcile_id in rec.reconcile_ids:
                        aml_obj += reconcile_id.move_line_id
                        amount_uyu = reconcile_id.amount_residual
                    aml_obj.reconcile()
                    recon_ids = self.env['account.partial.reconcile'].search([('credit_move_id','=',payment_line.id)])

    def btn_add_invoices(self):
        self.ensure_one()
        if self.state not in ['draft']:
            raise ValidationError('El estado del documento es incorrecto 1')
        if self.payment_type not in ['inbound']:
            return
        domain = [
                ('move_id.partner_id.id','=',self.partner_id.id),
                ('move_id.state','=','posted'),
                ('account_id','=',self.partner_id.property_account_receivable_id.id),
                ('move_id.move_type','in',['out_invoice','entry']),
                ('account_id.reconcile','=',True),
                ('amount_residual','!=',0),
                ]
        for reconcile_id in self.reconcile_ids:
            reconcile_id.unlink()
        if self.payment_type == 'inbound':
            domain.append(('debit','>',0))
        amls = self.env['account.move.line'].search(domain)
        for aml in amls:
            vals_reconcile = {
                    'payment_id': self.id,
                    'move_line_id': aml.id,
                    }
            reconcile_id = self.env['account.payment.reconcile'].create(vals_reconcile)

    def btn_payment_reconcile(self):
        self.ensure_one()
        if self.state not in ['posted']:
            raise ValidationError('El estado del documento es incorrecto 3')
        if self.payment_type not in ['inbound']:
            raise ValidationError('El tipo del documento es incorrecto 4')
        domain = [
                ('move_id.partner_id.id','=',self.partner_id.id),
                ('move_id.state','=','posted'),
                ('move_id.move_type','in',['out_invoice','entry']),
                ('account_id','=',self.partner_id.property_account_receivable_id.id),
                ('account_id.reconcile','=',True),
                ('amount_residual','!=',0),
                ]
        if self.payment_type == 'inbound':
            domain.append(('debit','>',0))
        amls = self.env['account.move.line'].search(domain)
        payment_move_line_id = None
        for line in self.move_id.line_ids:
            if line.amount_residual < 0 and line.account_id.reconcile \
                    and line.account_id.id == self.partner_id.property_account_receivable_id.id:
                payment_move_line_id = line
        if not payment_move_line_id:
            raise ValidationError('No hay linea a conciliar')
        wizard_id = self.env['payment.reconcile.wizard'].create({
            'payment_id': self.id,
            'payment_move_line_id': payment_move_line_id.id,
            })
        for aml in amls:
            vals_line = {
                    'wizard_id': wizard_id.id,
                    'move_line_id': aml.id,
                    'selected': None,
                    }
            line_id = self.env['payment.reconcile.line.wizard'].create(vals_line)
        return {
               'name': _('Conciliar pago'),
               'res_model': 'payment.reconcile.wizard',
               'res_id': wizard_id.id,
               'view_mode': 'form',
               'type': 'ir.actions.act_window',
               'target': 'new',
               }

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.btn_add_invoices()

    reconcile_ids = fields.One2many(comodel_name='account.payment.reconcile',inverse_name='payment_id',string='Facturas')
    exchange_move_id = fields.Many2one('account.move',string='Asiento diferencia tipo de cambio')

class AccountPaymentReconcile(models.Model):
    _name = 'account.payment.reconcile'
    _description = 'account.payment.reconcile'

    def _compute_amounts(self):
        for rec in self:
            rec.amount = rec.move_line_id.debit
            rec.amount_residual = rec.move_line_id.amount_residual
            rec.amount_currency = rec.move_line_id.amount_currency
            rec.amount_residual_currency = rec.move_line_id.amount_residual_currency
            rec.currency_id = rec.move_line_id.currency_id.id

    payment_id = fields.Many2one('account.payment','Pago')
    move_line_id = fields.Many2one('account.move.line','Apunte contable')
    move_id = fields.Many2one(comodel_name='account.move',string='Factura',related='move_line_id.move_id')
    account_id = fields.Many2one('account.account','Cuenta contable')
    amount = fields.Float('Monto',compute=_compute_amounts)
    amount_residual = fields.Float('Monto pendiente',compute=_compute_amounts)
    amount_currency = fields.Float('Monto moneda',compute=_compute_amounts)
    amount_residual_currency = fields.Float('Monto pendiente moneda',compute=_compute_amounts)
    currency_id = fields.Many2one('res.currency','Moneda',compute=_compute_amounts)
