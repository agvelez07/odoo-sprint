from odoo import fields, models


class ProjectSprint(models.Model):
    _name = 'project.sprint'
    _description = 'Project Sprint'
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True)
    project_id = fields.Many2one(
        'project.project', required=True, index=True, ondelete='restrict')
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    goal = fields.Text()
    state = fields.Selection(
        [('planned', 'Planeado'), ('active', 'Ativo'), ('closed', 'Fechado')],
        default='planned', required=True, index=True)
    active = fields.Boolean(default=True)
    task_ids = fields.Many2many(
        'project.task', 'project_sprint_task_rel', 'sprint_id', 'task_id',
        string='Tarefas')
