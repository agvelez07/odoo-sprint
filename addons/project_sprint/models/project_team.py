from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectTeam(models.Model):
    _name = 'project.team'
    _description = 'Equipa de engenharia'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    lead_id = fields.Many2one('res.users', string='Líder de equipa',
                              required=True, index=True, ondelete='restrict')
    member_ids = fields.Many2many('res.users', 'project_team_user_rel',
                                  'team_id', 'user_id', string='Engenheiros')
    project_ids = fields.One2many('project.project', 'team_id', string='Projetos')
    member_count = fields.Integer(compute='_compute_member_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Já existe uma equipa com este nome.'),
    ]

    @api.depends('member_ids')
    def _compute_member_count(self):
        for team in self:
            team.member_count = len(team.member_ids)

    @api.onchange('lead_id')
    def _onchange_lead_id(self):
        self.member_ids -= self.lead_id

    @api.constrains('lead_id', 'member_ids')
    def _check_lead_not_member(self):
        for team in self:
            if team.lead_id in team.member_ids:
                raise ValidationError(
                    'O líder da equipa não pode ser também engenheiro da mesma equipa.')