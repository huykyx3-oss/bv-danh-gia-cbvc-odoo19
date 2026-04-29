from odoo import models, fields, api
from odoo.exceptions import UserError


class QuarterlyAggregateWizard(models.TransientModel):
    _name = 'bv.quarterly.aggregate.wizard'
    _description = 'Wizard tổng hợp đánh giá quý từ phiếu tháng'

    quarter = fields.Selection([
        ('1', 'Quý I'), ('2', 'Quý II'),
        ('3', 'Quý III'), ('4', 'Quý IV'),
    ], string='Quý', required=True)
    year = fields.Integer(string='Năm', required=True,
                          default=lambda self: fields.Date.today().year)
    department_id = fields.Many2one(
        'hr.department', string='Khoa/Phòng',
        help='Để trống để tổng hợp tất cả khoa/phòng')

    def action_aggregate(self):
        self.ensure_one()
        MonthlyEval = self.env['bv.monthly.evaluation']
        QuarterlySummary = self.env['bv.quarterly.summary']

        q = int(self.quarter)
        months = [str(m) for m in range((q - 1) * 3 + 1, q * 3 + 1)]

        domain = [
            ('year', '=', self.year),
            ('month', 'in', months),
            ('state', 'in', ['dept_approved', 'hr_reviewed', 'approved']),
        ]
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))

        evals = MonthlyEval.search(domain)
        if not evals:
            raise UserError(
                f'Không tìm thấy phiếu đánh giá tháng đã duyệt cho Quý {q}/{self.year}.')

        employee_ids = evals.mapped('employee_id')
        created_count = 0

        for emp in employee_ids:
            emp_evals = evals.filtered(lambda e: e.employee_id == emp)
            scores = {int(e.month): e.total_score for e in emp_evals}

            m1 = (q - 1) * 3 + 1
            existing = QuarterlySummary.search([
                ('employee_id', '=', emp.id),
                ('quarter', '=', self.quarter),
                ('year', '=', self.year),
            ], limit=1)

            vals = {
                'employee_id': emp.id,
                'quarter': self.quarter,
                'year': self.year,
                'month1_score': scores.get(m1, 0.0),
                'month2_score': scores.get(m1 + 1, 0.0),
                'month3_score': scores.get(m1 + 2, 0.0),
            }

            if existing:
                existing.write(vals)
            else:
                QuarterlySummary.create(vals)
                created_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tổng hợp quý hoàn tất',
                'message': f'Đã tổng hợp {len(employee_ids)} nhân viên cho Quý {q}/{self.year}. '
                           f'Tạo mới: {created_count}, Cập nhật: {len(employee_ids) - created_count}.',
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': 'Tổng hợp quý',
                    'res_model': 'bv.quarterly.summary',
                    'view_mode': 'list,form',
                    'domain': [('quarter', '=', self.quarter), ('year', '=', self.year)],
                },
            },
        }
