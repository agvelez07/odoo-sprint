from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    team_id = fields.Many2one('project.team', string='Equipa', index=True)
    sprint_ids = fields.One2many('project.sprint', 'project_id', string='Sprints')
    sprint_count = fields.Integer(compute='_compute_sprint_count')

    def _compute_sprint_count(self):
        for project in self:
            project.sprint_count = len(project.sprint_ids)

    def action_view_sprints(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'project_sprint.project_sprint_action')
        action['domain'] = [('project_id', '=', self.id)]
        action['context'] = {'default_project_id': self.id}
        return action
