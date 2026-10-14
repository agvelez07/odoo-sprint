{
    'name': 'Project Sprints',
    'version': '18.0.1.1.0',
    'category': 'Services/Project',
    'summary': 'Organise project tasks into sprints',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/sprint_views.xml',
        'views/task_views.xml',
        'wizard/sprint_close_wizard_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
