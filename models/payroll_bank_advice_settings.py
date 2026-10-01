
from odoo import api, fields, models, _


class PayrollBankAdviceSettings(models.Model):

    _name = 'payroll.bank.advice.settings'
    _description = 'Payroll Bank Advice Settings'
    _rec_name = 'default_bank_name'

    # -------------------------------------------------------------------------
    # Fields
    # -------------------------------------------------------------------------

    default_bank_name = fields.Char(
        string='Bank Name',
        required=True,
        default='',
        help='Default bank name shown on the bank advice letter',
    )
    branch = fields.Char(
        string='Branch',
        required=True,
        default='',
        help='Bank branch name',
    )
    bank_city = fields.Char(
        string='City',
        required=True,
        default='',
        help='Bank city/location',
    )
    bank_country = fields.Char(
        string='Country',
        default='Ethiopia',
        required=True,
        help='Bank country',
    )
    company_account_name = fields.Char(
        string='Company Account Name',
        required=True,
        default='',
        help='Company account name shown on the bank advice letter',
    )
    company_account_number = fields.Char(
        string='Company Account Number',
        required=True,
        default='',
        help='Company bank account number to be debited',
    )
    reference_prefix = fields.Char(
        string='Reference Prefix',
        default='BA',
        required=True,
        help='Short prefix used when generating the reference number on the letter',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Only the active configuration is used by the bank advice report',
    )

    # -------------------------------------------------------------------------
    # CRUD overrides — keep only one active record at a time
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Deactivate all existing active configs before creating a new active one."""
        for vals in vals_list:
            if vals.get('active', True):
                # Use sudo to avoid access-right issues when deactivating others
                self.sudo().search([('active', '=', True)]).write({'active': False})
        return super().create(vals_list)

    def write(self, vals):
        """If this record is being activated, deactivate all others first."""
        if vals.get('active'):
            others = self.sudo().search([
                ('active', '=', True),
                ('id', 'not in', self.ids),
            ])
            # Bypass the overridden write to avoid recursion
            super(PayrollBankAdviceSettings, others).write({'active': False})
        return super().write(vals)

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    @api.model
    def get_active_settings(self):
       
        return self.sudo().search([('active', '=', True)], limit=1)
