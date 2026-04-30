{
    'name': 'Đánh giá xếp loại cán bộ, viên chức',
    'version': '19.0.1.3.0',
    'category': 'Human Resources',
    'summary': 'Hệ thống tự đánh giá, xếp loại chất lượng CBVC bệnh viện theo QĐ 06/2026/QĐ-UBND',
    'description': """
        Module đánh giá, xếp loại chất lượng cán bộ, công chức, viên chức, người lao động
        theo Quyết định số 06/2026/QĐ-UBND tỉnh Quảng Ninh.

        Chức năng chính:
        - Tự đánh giá hằng tháng (Mẫu số 01)
        - Tổng hợp đánh giá theo quý
        - Xếp loại chất lượng năm (Mẫu số 02)
        - Workflow phê duyệt nhiều cấp
        - Kiểm tra ràng buộc tỷ lệ xếp loại
        - Báo cáo tổng hợp theo khoa/phòng
    """,
    'author': 'Hospital IT Department',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'mail',
        'bus',
    ],
    'data': [
        'security/evaluation_security.xml',
        'security/ir.model.access.csv',
        'data/criteria_data.xml',
        'wizards/quarterly_aggregate_wizard_views.xml',
        'wizards/yearly_aggregate_wizard_views.xml',
        'wizards/ratio_check_wizard_views.xml',
        'views/evaluation_criteria_views.xml',
        'views/evaluation_config_views.xml',
        'views/evaluation_template_views.xml',
        'views/monthly_evaluation_views.xml',
        'views/quarterly_summary_views.xml',
        'views/yearly_classification_views.xml',
        'views/dashboard_views.xml',
        'views/menu.xml',
        'reports/report_mau_01.xml',
        'reports/report_mau_02.xml',
        'reports/report_department_summary.xml',
        'data/cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bv_danh_gia/static/src/css/evaluation_form.css',
            'bv_danh_gia/static/src/js/notification_service.js',
            'bv_danh_gia/static/src/js/evaluation_form_view.js',
            'bv_danh_gia/static/src/js/dashboard.js',
            'bv_danh_gia/static/src/xml/evaluation_form_templates.xml',
            'bv_danh_gia/static/src/xml/dashboard_templates.xml',
        ],
    },
    'external_dependencies': {
        'python': ['python-docx'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
