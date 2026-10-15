{
    'name': 'Project Sprints',
    'version': '18.0.1.1.0',
    'category': 'Services/Project',
    'summary': 'Organise project tasks into sprints',
    'author': 'António Velez',
    'website': 'https://github.com/agvelez07/odoo-sprint',
    'description': """Sprints para projetos Odoo: sprints por projeto, tarefas em vários sprints, fecho de sprint com assistente, progresso por pontos e equipas com roles.""",
    'depends': ['project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/team_role_data.xml',
        'views/sprint_views.xml',
        'views/task_views.xml',
        'views/project_views.xml',
        'views/team_views.xml',
        'wizard/sprint_close_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_sprint/static/src/scss/sprint.scss',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
