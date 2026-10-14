from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    sprint_ids = fields.Many2many(
        'project.sprint', 'project_sprint_task_rel', 'task_id', 'sprint_id',
        string='Sprints')
    current_sprint_id = fields.Many2one(
        'project.sprint', compute='_compute_current_sprint',
        store=True, index=True, string='Sprint atual')
    effort_points = fields.Integer(string='Pontos de esforço')

    @api.depends('sprint_ids.state')
    def _compute_current_sprint(self):
        for task in self:
            task.current_sprint_id = task.sprint_ids.filtered(
                lambda s: s.state == 'active')[:1]

    @api.constrains('sprint_ids', 'project_id')
    def _check_sprints_same_project(self):
        for task in self:
            wrong = task.sprint_ids.filtered(
                lambda s: s.project_id != task.project_id)
            if wrong:
                raise ValidationError(_(
                    'A tarefa "%(task)s" só pode estar em sprints do seu projeto (%(project)s).',
                    task=task.name,
                    project=task.project_id.display_name or _('sem projeto')))
