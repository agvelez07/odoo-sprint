from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectTeam(models.Model):
    _name = 'project.team'
    _description = 'Equipa de engenharia'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    member_ids = fields.One2many('project.team.member', 'team_id', string='Membros')
    lead_id = fields.Many2one('res.users', string='Líder', compute='_compute_lead',
                              store=True, index=True)
    project_ids = fields.One2many('project.project', 'team_id', string='Projetos')
    member_count = fields.Integer(compute='_compute_member_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Já existe uma equipa com este nome.'),
    ]

    @api.depends('member_ids.role', 'member_ids.user_id')
    def _compute_lead(self):
        for team in self:
            lead = team.member_ids.filtered(lambda m: m.role == 'lead')[:1]
            team.lead_id = lead.user_id

    @api.depends('member_ids')
    def _compute_member_count(self):
        for team in self:
            team.member_count = len(team.member_ids)


class ProjectTeamMember(models.Model):
    _name = 'project.team.member'
    _description = 'Membro de equipa'

    team_id = fields.Many2one('project.team', required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string='Utilizador', required=True,
                              ondelete='cascade', index=True)
    role = fields.Selection([('engineer', 'Engenheiro'), ('lead', 'Líder de equipa')],
                            required=True, default='engineer')

    _sql_constraints = [
        ('user_team_uniq', 'unique(team_id, user_id)',
         'Este utilizador já pertence à equipa.'),
    ]

    @api.constrains('role', 'team_id')
    def _check_one_lead(self):
        for member in self.filtered(lambda m: m.role == 'lead'):
            leads = self.search_count([('team_id', '=', member.team_id.id),
                                       ('role', '=', 'lead')])
            if leads > 1:
                raise ValidationError('Uma equipa só pode ter um líder.')
