from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..models.sprint import CLOSED_STATES


class ProjectSprintCloseWizard(models.TransientModel):
    _name = 'project.sprint.close.wizard'
    _description = 'Fechar sprint'

    sprint_id = fields.Many2one('project.sprint', required=True, readonly=True)
    project_id = fields.Many2one(related='sprint_id.project_id')
    open_task_ids = fields.Many2many(
        'project.task', compute='_compute_open_tasks', string='Tarefas por concluir')
    destination = fields.Selection(
        [('next', 'Mover para outro sprint'),
         ('backlog', 'Devolver ao backlog')],
        default='backlog', required=True)
    next_sprint_id = fields.Many2one(
        'project.sprint', string='Sprint de destino',
        domain="[('project_id', '=', project_id), ('state', '=', 'planned')]")

    @api.depends('sprint_id.task_ids.state')
    def _compute_open_tasks(self):
        for wizard in self:
            wizard.open_task_ids = wizard.sprint_id.task_ids.filtered(
                lambda t: t.state not in CLOSED_STATES)

    def action_confirm(self):
        self.ensure_one()
        sprint = self.sprint_id
        if sprint.state != 'active':
            raise UserError(_('Só é possível fechar sprints ativos.'))
        if self.destination == 'next' and not self.next_sprint_id:
            raise UserError(_('Escolha o sprint de destino.'))
        open_tasks = sprint.task_ids.filtered(lambda t: t.state not in CLOSED_STATES)
        # fecha primeiro, para nunca haver dois sprints ativos ao mover as tarefas
        sprint.state = 'closed'
        if self.destination == 'next':
            # a tarefa fica ligada ao sprint antigo (historico) e ao novo
            self.next_sprint_id.task_ids = [Command.link(t.id) for t in open_tasks]
        else:
            sprint.task_ids = [Command.unlink(t.id) for t in open_tasks]
        return {'type': 'ir.actions.act_window_close'}
