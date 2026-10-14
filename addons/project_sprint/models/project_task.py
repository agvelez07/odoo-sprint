from odoo import api, fields, models


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
