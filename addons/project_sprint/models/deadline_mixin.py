from odoo import fields, models


class DeadlineMixin(models.AbstractModel):
    _name = 'project.deadline.mixin'
    _description = 'Prazo e dias em atraso'

    days_overdue = fields.Integer(string='Dias em atraso', compute='_compute_deadline')
    deadline_status = fields.Char(string='Prazo', compute='_compute_deadline')

    def _deadline_info(self):
        """Cada modelo devolve (data_limite, texto_fixo).
        Se houver texto_fixo, é esse o estado e não há atraso."""
        raise NotImplementedError

    def _compute_deadline(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.days_overdue = 0
            deadline, fixed_text = rec._deadline_info()
            if fixed_text:
                rec.deadline_status = fixed_text
                continue
            delta = (deadline - today).days
            if delta < 0:
                rec.days_overdue = -delta
                rec.deadline_status = f'Em atraso {-delta} d'
            elif delta == 0:
                rec.deadline_status = 'Termina hoje'
            else:
                rec.deadline_status = f'Faltam {delta} d'