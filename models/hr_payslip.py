
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class HrPayslip(models.Model):

    _inherit = 'hr.payslip'

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _get_employee_bank_info(self, employee):
        bank_account_number = ''
        bank_name = ''

        if not employee:
            return {'bank_name': '', 'bank_account_number': ''}

        # 1. Check employee.bank_account_id (standard Odoo hr.employee field)
        bank_account = getattr(employee, 'bank_account_id', False)
        if bank_account:
            bank_account_number = getattr(bank_account, 'acc_number', '') or ''
            bank_id = getattr(bank_account, 'bank_id', False)
            bank_name = (
                getattr(bank_id, 'name', '')
                or getattr(bank_account, 'bank_name', '')
                or ''
            )

        # 2. Check employee.bank_account_ids (if multi-bank module installed)
        if not bank_account_number:
            bank_accounts = getattr(employee, 'bank_account_ids', False)
            if bank_accounts:
                primary = getattr(employee, 'primary_bank_account_id', False)
                bank_account = primary if primary else bank_accounts[0]
                bank_account_number = getattr(bank_account, 'acc_number', '') or ''
                bank_id = getattr(bank_account, 'bank_id', False)
                bank_name = (
                    getattr(bank_id, 'name', '')
                    or getattr(bank_account, 'bank_name', '')
                    or ''
                )

        # 3. Check employee.address_home_id or work_contact_id partner bank_ids
        if not bank_account_number:
            partner = (
                getattr(employee, 'address_home_id', False)
                or getattr(employee, 'work_contact_id', False)
            )
            if partner and getattr(partner, 'bank_ids', False):
                bank = partner.bank_ids[0]
                bank_account_number = getattr(bank, 'acc_number', '') or ''
                bank_id = getattr(bank, 'bank_id', False)
                bank_name = (
                    getattr(bank_id, 'name', '')
                    or getattr(bank, 'bank_name', '')
                    or ''
                )

        # 4. Check contracts if contract model has bank_account_id
        if not bank_account_number:
            contracts = getattr(employee, 'contract_ids', False)
            if contracts:
                for contract in contracts:
                    bank_account = getattr(contract, 'bank_account_id', False)
                    if bank_account:
                        bank_account_number = getattr(bank_account, 'acc_number', '') or ''
                        bank_id = getattr(bank_account, 'bank_id', False)
                        bank_name = (
                            getattr(bank_id, 'name', '')
                            or getattr(bank_account, 'bank_name', '')
                            or ''
                        )
                        break

        return {
            'bank_name': bank_name,
            'bank_account_number': bank_account_number,
        }

    def _get_payslip_data(self):
        self.ensure_one()
        employee = self.employee_id
        bank_info = self._get_employee_bank_info(employee)

        net_salary = 0.0
        if hasattr(self, 'net_wage') and self.net_wage:
            net_salary = self.net_wage
        elif hasattr(self, 'net') and self.net:
            net_salary = self.net
        elif hasattr(self, 'line_ids'):
            net_lines = self.line_ids.filtered(lambda l: l.code == 'NET')
            if net_lines:
                net_salary = net_lines[0].total

        payslip_number = (
            getattr(self, 'x_studio_slip_number', False)
            or getattr(self, 'number', False)
            or getattr(self, 'name', '')
            or ''
        )

        settings = self._get_bank_advice_settings()
        bank_name = (
            bank_info.get('bank_name')
            or settings.get('default_bank_name')
            or 'Commercial Bank of Ethiopia'
        )

        return {
            'payslip_number': payslip_number,
            'employee_name': employee.name or '',
            'bank_name': bank_name,
            'bank_account_number': bank_info.get('bank_account_number', ''),
            'net_salary': net_salary,
        }

    def _compute_totals(self, payslip_data_list):

        total_employees = len(payslip_data_list)
        total_amount = sum(p.get('net_salary', 0.0) for p in payslip_data_list)
        return {
            'total_employees': total_employees,
            'total_amount': total_amount,
        }

    def _amount_to_words(self, amount, currency='Birr'):

        if not amount:
            return 'zero'

      
        _ones = [
            '', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
            'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen',
            'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
        ]
        _tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty',
                 'sixty', 'seventy', 'eighty', 'ninety']

        def _nn(n):
            
            if n < 20:
                return _ones[n]
            t = _tens[n // 10]
            u = _ones[n % 10]
            return t + ('-' + u if u else '')

        def _nnn(n):
            
            if n < 100:
                return _nn(n)
            h = _ones[n // 100] + ' hundred'
            rem = n % 100
            return h + (' and ' + _nn(rem) if rem else '')

        def _to_words(n):
            """Recursively convert an integer up to 999 999 999 999."""
            if n < 1000:
                return _nnn(n)
            if n < 1_000_000:
                rem = n % 1000
                return _nnn(n // 1000) + ' thousand' + (
                    ', ' + _nnn(rem) if rem else '')
            if n < 1_000_000_000:
                rem = n % 1_000_000
                return _nnn(n // 1_000_000) + ' million' + (
                    ', ' + _to_words(rem) if rem else '')
            rem = n % 1_000_000_000
            return _nnn(n // 1_000_000_000) + ' billion' + (
                ', ' + _to_words(rem) if rem else '')

        amount_rounded = round(amount, 2)
        amount_int = int(amount_rounded)
        # Use round() on the fractional part to avoid floating-point drift
        cents = round((amount_rounded - amount_int) * 100)

        # Integer part
        words = _to_words(amount_int) if amount_int else 'zero'

        # Decimal part: spell each digit separately ("seven two"), matching reference
        if cents > 0:
            cent_str = '{:02d}'.format(cents)
            cent_words = ' '.join(_ones[int(d)] for d in cent_str if int(d) or True)
            words += ' point ' + cent_words

        return words

    def _get_company_info(self):
        company = (self.company_id or self.env.company).sudo()
        partner = company.partner_id.sudo() if company and company.partner_id else False

        address = ''
        if partner and partner.contact_address:
            address = partner.contact_address.replace('\n', ', ').strip()

        if not address:
            street = company.street or (partner.street if partner else '')
            street2 = company.street2 or (partner.street2 if partner else '')
            city = company.city or (partner.city if partner else '')
            state_name = company.state_id.name if company.state_id else (partner.state_id.name if partner and partner.state_id else '')
            zip_code = company.zip or (partner.zip if partner else '')
            country_name = company.country_id.name if company.country_id else (partner.country_id.name if partner and partner.country_id else '')

            address_parts = list(filter(None, [street, street2, city, state_name, zip_code, country_name]))
            address = ', '.join(address_parts)

        phone = company.phone or (partner.phone if partner else '')
        email = company.email or (partner.email if partner else '')
        website = company.website or (partner.website if partner else '')
        vat = company.vat or (partner.vat if partner else '')

        logo_src = ''
        logo_field = company.logo_web or company.logo
        if logo_field:
            import base64
            if isinstance(logo_field, bytes):
                logo_field = logo_field.decode('utf-8')

            try:
                decoded_once = base64.b64decode(logo_field)
                if decoded_once.startswith(b'PHN2Z') or decoded_once.startswith(b'<svg'):
                    if decoded_once.startswith(b'PHN2Z'):
                        actual_b64 = decoded_once.decode('utf-8')
                    else:
                        actual_b64 = base64.b64encode(decoded_once).decode('utf-8')
                else:
                    actual_b64 = logo_field
            except Exception:
                actual_b64 = logo_field

            try:
                img_bytes = base64.b64decode(actual_b64[:32])
            except Exception:
                img_bytes = b''

            if img_bytes[:4] == b'\x89PNG':
                mime = 'image/png'
            elif img_bytes[:3] == b'\xff\xd8\xff':
                mime = 'image/jpeg'
            elif img_bytes[:4] == b'GIF8':
                mime = 'image/gif'
            elif img_bytes[:5] == b'<?xml' or img_bytes[:4] == b'<svg':
                mime = 'image/svg+xml'
            else:
                mime = 'image/png'

            logo_src = 'data:{};base64,{}'.format(mime, actual_b64)

        company_name = company.name or ''
        if (not company_name or company_name == 'My Company') and partner and partner.name:
            company_name = partner.name

        return {
            'company_name':     company_name,
            'company_address':  address,
            'logo_src':         logo_src,
            'company_phone':    phone,
            'company_email':    email,
            'company_website':  website,
            'company_vat':      vat,
            'company_vat_number': '',
            'currency':         company.currency_id.name or 'Birr',
        }

    def _get_bank_advice_settings(self):

        settings = self.env['payroll.bank.advice.settings'].sudo().search(
            [('active', '=', True)], limit=1
        )
        if not settings:
            return {
                'default_bank_name': '',
                'branch': '',
                'bank_city': '',
                'bank_country': 'Ethiopia',
                'company_account_name': '',
                'company_account_number': '',
                'reference_prefix': 'BA',
            }
        return {
            'default_bank_name': settings.default_bank_name or '',
            'branch': settings.branch or '',
            'bank_city': settings.bank_city or '',
            'bank_country': settings.bank_country or 'Ethiopia',
            'company_account_name': settings.company_account_name or '',
            'company_account_number': settings.company_account_number or '',
            'reference_prefix': settings.reference_prefix or 'BA',
        }

    def _prepare_salary_rule_summary(self):
        """
        Dynamically build a salary-rule summary matrix for the selected payslips.

        Returns a dict:
          {
            'rule_columns': [{'code': ..., 'name': ...}, ...],   # ordered column list
            'rows':         [                                    # one dict per payslip
              {
                'employee_name': ...,
                'employee_id':   ...,
                'payslip_number': ...,
                'period': ...,
                'net_salary': ...,
                'amounts': {'RULE_CODE': amount, ...}
              }, ...
            ],
            'totals': {'RULE_CODE': total, ..., 'net_salary': total}
          }
        """
        valid_payslips = self.filtered(lambda p: p.state != 'cancel')

        # ---- Collect all rule codes that appear in any selected payslip ----
        rule_map = {}   # code -> name (first occurrence wins)
        for slip in valid_payslips:
            for line in slip.line_ids:
                code = line.code or ''
                if code and code not in rule_map:
                    rule_map[code] = line.name or code

        # Keep a stable order: sort by code
        ordered_codes = sorted(rule_map.keys())
        rule_columns = [{'code': c, 'name': rule_map[c]} for c in ordered_codes]

        # ---- Build one row per payslip ----
        rows = []
        totals = {c: 0.0 for c in ordered_codes}
        totals['net_salary'] = 0.0

        for slip in sorted(valid_payslips, key=lambda p: p.name or ''):
            # Net salary
            net_salary = 0.0
            if hasattr(slip, 'net_wage') and slip.net_wage:
                net_salary = slip.net_wage
            elif hasattr(slip, 'net') and slip.net:
                net_salary = slip.net
            elif hasattr(slip, 'line_ids'):
                net_lines = slip.line_ids.filtered(lambda l: l.code == 'NET')
                if net_lines:
                    net_salary = net_lines[0].total

            # Payslip number
            payslip_number = slip.name or ''
            if hasattr(slip, 'x_studio_slip_number') and slip.x_studio_slip_number:
                payslip_number = slip.x_studio_slip_number

            # Period
            period = ''
            if slip.date_from and slip.date_to:
                period = '{} - {}'.format(
                    slip.date_from.strftime('%d/%m/%Y'),
                    slip.date_to.strftime('%d/%m/%Y'),
                )
            elif slip.date_to:
                period = slip.date_to.strftime('%B %Y')

            # Build amounts dict for this slip
            amounts = {c: 0.0 for c in ordered_codes}
            for line in slip.line_ids:
                if line.code in amounts:
                    amounts[line.code] = line.total or 0.0

            # Accumulate totals
            for c in ordered_codes:
                totals[c] += amounts[c]
            totals['net_salary'] += net_salary

            rows.append({
                'employee_name':  slip.employee_id.name or '',
                'employee_id':    slip.employee_id.barcode or slip.employee_id.id or '',
                'payslip_number': payslip_number,
                'period':         period,
                'net_salary':     net_salary,
                'amounts':        amounts,
            })

        return {
            'rule_columns': rule_columns,
            'rows':         rows,
            'totals':       totals,
        }

    def _prepare_bank_advice_report_data(self):

       
        valid_payslips = self.filtered(lambda p: p.state != 'cancel')
        if not valid_payslips:
            raise UserError(_(
                'No valid payslips to print.  '
                'Please ensure the selected payslips are not cancelled.'
            ))

       
        payslip_rows = sorted(
            [slip._get_payslip_data() for slip in valid_payslips],
            key=lambda x: x.get('payslip_number', ''),
        )

        totals = valid_payslips[0]._compute_totals(payslip_rows)
        company_info = valid_payslips[0]._get_company_info()
        settings = self._get_bank_advice_settings()

        currency = company_info.get('currency', 'Birr')
        prefix = settings.get('reference_prefix', 'BA')
        if prefix and not prefix.endswith('-') and not prefix.endswith('/'):
            prefix_str = f"{prefix}-"
        else:
            prefix_str = prefix or 'BA-'
        reference_number = f"{prefix_str}____________"

 
        pay_period = ''
        first = valid_payslips[0]
        if first.date_to:
            pay_period = first.date_to.strftime('%B, %Y')

     
        today = fields.Date.today()
        report_date_formatted = today.strftime('%B %d/%Y')

        # Build the salary-rule summary for the second page
        salary_rule_summary = self._prepare_salary_rule_summary()

        return {
            'payslips': payslip_rows,
            'company': company_info,
            'settings': settings,
            'reference_number': reference_number,
            'pay_period': pay_period,
            'report_date': fields.Date.today().strftime('%d %B %Y'),
            'report_date_formatted': report_date_formatted,
            'print_date': fields.Datetime.now().strftime('%d/%m/%Y %H:%M'),
            'total_employees': totals['total_employees'],
            'total_amount': totals['total_amount'],
            'amount_in_words': valid_payslips[0]._amount_to_words(
                totals['total_amount'], currency
            ),
            'salary_rule_summary': salary_rule_summary,
        }

    # -------------------------------------------------------------------------
    # Public action
    # -------------------------------------------------------------------------

    def action_print_bank_advice(self):

        has_access = (
            self.env.user.has_group(
                'payroll_bank_advice.group_payroll_bank_advice_manager') or
            self.env.user.has_group(
                'payroll_bank_advice.group_payroll_bank_advice_user') or
            self.env.user.has_group('hr_payroll.group_hr_payroll_manager') or
            self.env.user.has_group('hr_payroll.group_hr_payroll_user')
        )
        if not has_access:
            raise AccessError(_('You do not have access to print Bank Advice.'))

        if not self:
            raise UserError(_(
                'Please select at least one payslip to print Bank Advice.'
            ))

        # ----------------------------------------------------------------
        # Generate Portrait Bank Advice PDF
        # ----------------------------------------------------------------
        bank_advice_report = self.env.ref(
            'payroll_bank_advice.action_report_payroll_bank_advice'
        )
        bank_advice_pdf, _ = bank_advice_report.sudo()._render_qweb_pdf(
            bank_advice_report, self.ids
        )

        # ----------------------------------------------------------------
        # Generate Landscape Salary Rule Summary PDF
        # ----------------------------------------------------------------
        summary_report = self.env.ref(
            'payroll_bank_advice.action_report_salary_rule_summary'
        )
        summary_pdf, _ = summary_report.sudo()._render_qweb_pdf(
            summary_report, self.ids
        )

        # ----------------------------------------------------------------
        # Merge both PDFs (portrait + landscape) using pypdf
        # ----------------------------------------------------------------
        try:
            from pypdf import PdfWriter, PdfReader
        except ImportError:
            from PyPDF2 import PdfWriter, PdfReader

        import io, base64

        writer = PdfWriter()
        for pdf_bytes in [bank_advice_pdf, summary_pdf]:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

        out_stream = io.BytesIO()
        writer.write(out_stream)
        merged_pdf_bytes = out_stream.getvalue()

        # ----------------------------------------------------------------
        # Save merged PDF as ir.attachment and return a download URL
        # ----------------------------------------------------------------
        today_str = fields.Date.today().strftime('%Y%m%d')
        filename = 'Bank_Advice_with_Summary_{}.pdf'.format(today_str)

        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(merged_pdf_bytes),
            'res_model': 'hr.payslip',
            'res_id': self.ids[0] if self.ids else False,
            'mimetype': 'application/pdf',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}?download=true'.format(attachment.id),
            'target': 'self',
        }

