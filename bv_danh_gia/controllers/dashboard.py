from odoo import http
from odoo.http import request
import json


class EvaluationDashboardController(http.Controller):

    @http.route('/bv_danh_gia/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, **kwargs):
        user = request.env.user
        employee = user.employee_id
        Evaluation = request.env['bv.monthly.evaluation'].sudo()

        is_hr = user.has_group('bv_danh_gia.group_evaluation_hr')
        is_director = user.has_group('bv_danh_gia.group_evaluation_director')
        is_dept_manager = user.has_group('bv_danh_gia.group_evaluation_dept_manager')

        result = {
            'user_name': user.name,
            'employee_name': employee.name if employee else '',
            'department_name': employee.department_id.name if employee and employee.department_id else '',
            'role': 'employee',
            'is_hr': is_hr,
            'is_director': is_director,
            'is_dept_manager': is_dept_manager,
        }

        if is_hr or is_director:
            result['role'] = 'hospital'
            evals = Evaluation.search([('state', '=', 'approved')])
            result.update(self._build_stats(evals))
            result['department_breakdown'] = self._department_breakdown(evals)
            result['pending_dept'] = Evaluation.search_count([('state', '=', 'submitted')])
            result['pending_hr'] = Evaluation.search_count([('state', '=', 'dept_approved')])
            result['pending_director'] = Evaluation.search_count([('state', '=', 'hr_reviewed')])
        elif is_dept_manager and employee and employee.department_id:
            result['role'] = 'department'
            dept = employee.department_id
            evals = Evaluation.search([
                ('department_id', '=', dept.id),
                ('state', '=', 'approved'),
            ])
            result.update(self._build_stats(evals))
            result['pending_approval'] = Evaluation.search_count([
                ('department_id', '=', dept.id),
                ('state', '=', 'submitted'),
            ])
        else:
            result['role'] = 'employee'
            if employee:
                evals = Evaluation.search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'approved'),
                ])
                result.update(self._build_stats(evals))
                my_latest = Evaluation.search([
                    ('employee_id', '=', employee.id),
                ], order='year desc, month desc', limit=6)
                result['recent_evaluations'] = [{
                    'id': e.id,
                    'month': dict(e._fields['month'].selection).get(e.month, ''),
                    'year': e.year,
                    'total_score': round(e.total_score, 1),
                    'classification': e.classification,
                    'state': e.state,
                } for e in my_latest]

        config = request.env['bv.evaluation.config'].sudo().search([], limit=1)
        result['ratio_excellent'] = config.max_excellent_ratio if config else 20.0

        return result

    def _build_stats(self, evaluations):
        total = len(evaluations)
        excellent = len(evaluations.filtered(lambda e: e.classification == 'excellent'))
        good = len(evaluations.filtered(lambda e: e.classification == 'good'))
        fair = len(evaluations.filtered(lambda e: e.classification == 'fair'))
        poor = len(evaluations.filtered(lambda e: e.classification == 'poor'))
        avg_score = round(sum(evaluations.mapped('total_score')) / total, 1) if total else 0

        ratio_excellent = round(excellent / total * 100, 1) if total else 0

        return {
            'total_evaluations': total,
            'excellent_count': excellent,
            'good_count': good,
            'fair_count': fair,
            'poor_count': poor,
            'avg_score': avg_score,
            'ratio_excellent_actual': ratio_excellent,
        }

    def _department_breakdown(self, evaluations):
        dept_data = {}
        for ev in evaluations:
            dept_name = ev.department_id.name or 'Chưa phân khoa'
            if dept_name not in dept_data:
                dept_data[dept_name] = {
                    'name': dept_name,
                    'total': 0, 'excellent': 0, 'good': 0,
                    'fair': 0, 'poor': 0, 'score_sum': 0,
                }
            d = dept_data[dept_name]
            d['total'] += 1
            d['score_sum'] += ev.total_score
            if ev.classification == 'excellent':
                d['excellent'] += 1
            elif ev.classification == 'good':
                d['good'] += 1
            elif ev.classification == 'fair':
                d['fair'] += 1
            elif ev.classification == 'poor':
                d['poor'] += 1

        result = []
        for d in dept_data.values():
            d['avg_score'] = round(d['score_sum'] / d['total'], 1) if d['total'] else 0
            d['ratio_excellent'] = round(d['excellent'] / d['total'] * 100, 1) if d['total'] else 0
            del d['score_sum']
            result.append(d)
        return sorted(result, key=lambda x: x['avg_score'], reverse=True)
