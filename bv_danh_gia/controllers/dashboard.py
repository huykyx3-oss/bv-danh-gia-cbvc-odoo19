from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import datetime


class EvaluationDashboardController(http.Controller):

    def _employee_for_user(self, user):
        """user.employee_id hoặc nhân viên trùng user_id (trường hợp chưa gán trên user)."""
        emp = user.employee_id
        if emp:
            return emp
        return request.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1)

    @staticmethod
    def _parse_id(val):
        if val is None or val is False:
            return False
        try:
            return int(val)
        except (TypeError, ValueError):
            return False

    def _empty_chart(self, year):
        return {
            'months': list(range(1, 13)),
            'nv_scores': [None] * 12,
            'tp_scores': [None] * 12,
            'meta': {
                'year': year,
                'labels': [f'T{m}' for m in range(1, 13)],
            },
        }

    def _employee_in_department(self, employee_id, department_id):
        if not employee_id or not department_id:
            return False
        Emp = request.env['hr.employee'].sudo()
        return bool(Emp.search_count([
            ('id', '=', employee_id),
            ('department_id', '=', department_id),
        ]))

    def _chart_nv_self_track_total(self, rec):
        """Trùng bước NV trong _compute_nv_tp_scores: Phần I (self) + Phần II từ pct_*."""
        max_pts = rec.task_score_max or 70.0
        gs_nv = sum(rec.criteria_line_ids.mapped('self_score'))
        if rec.is_manager:
            nv_pct = (
                rec.pct_quantity + rec.pct_quality + rec.pct_progress
                + rec.pct_field_result + rec.pct_organization + rec.pct_team_cohesion
            )
            task_nv = (nv_pct / 6.0) * max_pts / 100.0
        else:
            nv_pct = rec.pct_quantity + rec.pct_quality + rec.pct_progress
            task_nv = (nv_pct / 3.0) * max_pts / 100.0
        return gs_nv + task_nv

    def _chart_nv_tp_pair(self, rec):
        """Điểm biểu đồ khớp form mục III (monthly_evaluation_views).

        - NV: luôn tính lại nhánh NV (self + pct), không tin total_score_nv trong DB khi stale (=0 dù có pct).
        - Đường legend \"TK/TP\": total_score — ô Tổng điểm cột TK/TP (general final + task_score).
          Không dùng total_score_tp (chỉ dept_pct phần II) -> lệch khi task_score lấy pct vì dept_pct trống.
        """
        out_nv = self._chart_nv_self_track_total(rec)
        out_tp = float(rec.total_score or 0.0)
        return out_nv, out_tp

    @http.route('/bv_danh_gia/dashboard_data', type='json', auth='user')
    def get_dashboard_data(self, **kwargs):
        user = request.env.user
        employee = self._employee_for_user(user)
        Evaluation = request.env['bv.monthly.evaluation'].sudo()

        is_hr = user.has_group('bv_danh_gia.group_evaluation_hr')
        is_director = user.has_group('bv_danh_gia.group_evaluation_director')
        is_dept_manager = user.has_group('bv_danh_gia.group_evaluation_dept_manager')

        result = {
            'user_name': user.name,
            'my_user_id': user.id,
            'employee_name': employee.name if employee else '',
            'department_name': employee.department_id.name if employee and employee.department_id else '',
            'my_employee_id': employee.id if employee else False,
            'my_department_id': employee.department_id.id if employee and employee.department_id else False,
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

    @http.route('/bv_danh_gia/dashboard_chart_data', type='json', auth='user')
    def dashboard_chart_data(self, year=None, mode=None, employee_id=None, department_id=None):
        """Series điểm NV tự chấm / TK-TP chấm theo 12 tháng (phiếu approved)."""
        user = request.env.user
        employee = self._employee_for_user(user)
        Evaluation = request.env['bv.monthly.evaluation'].sudo()
        Emp = request.env['hr.employee'].sudo()
        Dept = request.env['hr.department'].sudo()

        is_hr = user.has_group('bv_danh_gia.group_evaluation_hr')
        is_director = user.has_group('bv_danh_gia.group_evaluation_director')
        is_dept_manager = user.has_group('bv_danh_gia.group_evaluation_dept_manager')

        if year is None:
            year = datetime.date.today().year
        else:
            try:
                year = int(year)
            except (TypeError, ValueError):
                year = datetime.date.today().year

        mode = mode if isinstance(mode, str) else 'avg_all'
        if mode not in ('avg_all', 'employee', 'department'):
            mode = 'avg_all'

        emp_id = self._parse_id(employee_id)
        dept_id = self._parse_id(department_id)
        my_dept_id = employee.department_id.id if employee and employee.department_id else False

        if is_hr or is_director:
            role = 'hospital'
        elif is_dept_manager and employee and employee.department_id:
            role = 'department'
        else:
            role = 'employee'

        if role == 'employee':
            mode = 'employee'
            emp_id = employee.id if employee else False
            dept_id = False
            if not emp_id:
                return self._empty_chart(year)

        elif role == 'department':
            if not my_dept_id:
                return self._empty_chart(year)
            dept_id = my_dept_id
            if mode == 'department':
                mode = 'avg_all'
            if mode == 'employee' and emp_id:
                if not self._employee_in_department(emp_id, my_dept_id):
                    raise AccessError(
                        'Bạn chỉ được xem điểm của nhân viên thuộc khoa/phòng của mình.')

        else:
            if mode == 'employee' and emp_id and not Emp.browse(emp_id).exists():
                raise AccessError('Nhân viên không tồn tại.')
            if mode == 'department' and dept_id and not Dept.browse(dept_id).exists():
                raise AccessError('Khoa/phòng không tồn tại.')

        base_domain = [('state', '=', 'approved'), ('year', '=', year)]

        if mode == 'avg_all':
            domain_extra = []
            if role == 'department':
                domain_extra = [('department_id', '=', dept_id)]
            chart_domain = base_domain + domain_extra
            return self._aggregate_monthly_averages(Evaluation, chart_domain, year)

        if mode == 'department':
            if not dept_id:
                return self._empty_chart(year)
            chart_domain = base_domain + [('department_id', '=', dept_id)]
            return self._aggregate_monthly_averages(Evaluation, chart_domain, year)

        if mode == 'employee':
            if not emp_id:
                return self._empty_chart(year)
            chart_domain = base_domain + [('employee_id', '=', emp_id)]
            return self._aggregate_monthly_points(Evaluation, chart_domain, year)

        return self._empty_chart(year)

    def _aggregate_monthly_averages(self, Evaluation, chart_domain, year):
        nv_scores = []
        tp_scores = []
        for m in range(1, 13):
            month_domain = chart_domain + [('month', '=', str(m))]
            recs = Evaluation.search(month_domain)
            if recs:
                nv_vals = []
                tp_vals = []
                for r in recs:
                    nv, tp = self._chart_nv_tp_pair(r)
                    nv_vals.append(nv)
                    tp_vals.append(tp)
                nv_scores.append(round(sum(nv_vals) / len(nv_vals), 2))
                tp_scores.append(round(sum(tp_vals) / len(tp_vals), 2))
            else:
                nv_scores.append(None)
                tp_scores.append(None)
        return {
            'months': list(range(1, 13)),
            'nv_scores': nv_scores,
            'tp_scores': tp_scores,
            'meta': {
                'year': year,
                'labels': [f'T{m}' for m in range(1, 13)],
            },
        }

    def _aggregate_monthly_points(self, Evaluation, chart_domain, year):
        nv_scores = []
        tp_scores = []
        for m in range(1, 13):
            month_domain = chart_domain + [('month', '=', str(m))]
            rec = Evaluation.search(month_domain, limit=1)
            if rec:
                nv, tp = self._chart_nv_tp_pair(rec)
                nv_scores.append(round(nv, 2))
                tp_scores.append(round(tp, 2))
            else:
                nv_scores.append(None)
                tp_scores.append(None)
        return {
            'months': list(range(1, 13)),
            'nv_scores': nv_scores,
            'tp_scores': tp_scores,
            'meta': {
                'year': year,
                'labels': [f'T{m}' for m in range(1, 13)],
            },
        }

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
