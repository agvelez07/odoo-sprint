from datetime import timedelta

from odoo import Command, fields
from odoo.tests.common import TransactionCase


class SprintTeamCase(TransactionCase):
    """Duas equipas (A e B), um projeto por equipa e um projeto sem equipa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(
            no_reset_password=True, mail_notrack=True)
        group_user = cls.env.ref('project.group_project_user')
        group_manager = cls.env.ref('project.group_project_manager')

        def make_user(login, groups):
            return Users.create({
                'name': login.capitalize(), 'login': login, 'email': f'{login}@test.local',
                'notification_type': 'inbox',
                'groups_id': [Command.link(g.id) for g in groups],
            })

        cls.manager = make_user('manager', [group_manager])
        cls.lead_a = make_user('lead_a', [group_user])
        cls.eng_a1 = make_user('eng_a1', [group_user])
        cls.eng_a2 = make_user('eng_a2', [group_user])
        cls.lead_b = make_user('lead_b', [group_user])
        cls.eng_b1 = make_user('eng_b1', [group_user])

        role = cls.env.ref('project_sprint.role_backend')
        Team = cls.env['project.team']
        cls.team_a = Team.create({
            'name': 'Equipa A', 'lead_id': cls.lead_a.id,
            'member_ids': [Command.create({'user_id': u.id, 'role_id': role.id})
                           for u in (cls.eng_a1, cls.eng_a2)],
        })
        cls.team_b = Team.create({
            'name': 'Equipa B', 'lead_id': cls.lead_b.id,
            'member_ids': [Command.create({'user_id': cls.eng_b1.id, 'role_id': role.id})],
        })

        Project = cls.env['project.project']
        cls.project_a = Project.create({'name': 'Projeto A', 'team_id': cls.team_a.id})
        cls.project_b = Project.create({'name': 'Projeto B', 'team_id': cls.team_b.id})
        cls.project_free = Project.create({'name': 'Projeto livre'})

        Task = cls.env['project.task']
        cls.task_a1 = Task.create({
            'name': 'Tarefa de A1', 'project_id': cls.project_a.id,
            'user_ids': [Command.set([cls.eng_a1.id])], 'effort_points': 3})
        cls.task_a2 = Task.create({
            'name': 'Tarefa de A2', 'project_id': cls.project_a.id,
            'user_ids': [Command.set([cls.eng_a2.id])], 'effort_points': 2})
        cls.task_a_free = Task.create({
            'name': 'Tarefa sem responsável', 'project_id': cls.project_a.id})
        cls.task_b1 = Task.create({
            'name': 'Tarefa de B1', 'project_id': cls.project_b.id,
            'user_ids': [Command.set([cls.eng_b1.id])]})

        today = fields.Date.context_today(cls.env['project.sprint'])
        Sprint = cls.env['project.sprint']
        cls.sprint_a = Sprint.create({
            'project_id': cls.project_a.id,
            'date_start': today, 'date_end': today + timedelta(days=14),
            'task_ids': [Command.set([cls.task_a1.id, cls.task_a2.id])]})
        cls.sprint_b = Sprint.create({
            'project_id': cls.project_b.id,
            'date_start': today, 'date_end': today + timedelta(days=14),
            'task_ids': [Command.set([cls.task_b1.id])]})
        cls.flush_tracking()

    @classmethod
    def flush_tracking(cls):
        """As mensagens de tracking só são criadas no pre-commit: forçar aqui."""
        cls.env.flush_all()
        cls.env.cr.precommit.run()

    def team_notifications(self, record, since=None):
        """Contactos que receberam notificações 'Atualização da equipa'
        (só das mensagens novas, se `since` trouxer as que já existiam)."""
        self.flush_tracking()
        subtype = self.env.ref(
            'project_sprint.mt_team_update_' + record._name.replace('.', '_'))
        messages = (record.message_ids - (since or record.message_ids.browse())).filtered(
            lambda m: m.subtype_id == subtype)
        return self.env['mail.notification'].search(
            [('mail_message_id', 'in', messages.ids)]).res_partner_id
