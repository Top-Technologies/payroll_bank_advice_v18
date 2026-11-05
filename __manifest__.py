

{
    'name': 'Payroll Bank Advice v18',
    'version': '18.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Generate Professional Bank Advice Letters for Payroll',
    'author': 'top tech',
    'license': 'LGPL-3',
    'depends': [
        'hr_payroll',
        'hr_work_entry_contract_enterprise',
        'hr',
        'account',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/payroll_bank_advice_settings.xml',
        'views/hr_payslip_views.xml',
        'reports/payroll_bank_advice_report.xml',
        'reports/payroll_bank_advice_template.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'assets': {},
}
