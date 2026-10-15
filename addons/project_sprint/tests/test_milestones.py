from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import SprintTeamCase


@tagged('post_install', '-at_install')
class TestMilestones(SprintTeamCase):

    def _milestone(self, project=None, **kwargs):
        today = fields.Date.context_today(self.env['project.milestone'])
        vals = {'name': 'Marco', 'project_id': (project or self.project_a).id,
                'deadline': today + timedelta(days=20)}
        vals.update(kwargs)
        return self.env['project.milestone'].create(vals)

    def test_creating_a_milestone_turns_on_milestones_in_the_project(self):
        self.project_a.allow_milestones = False
        self._milestone()
        self.assertTrue(self.project_a.allow_milestones)

    def test_sprint_can_only_use_milestones_of_its_project(self):
        other = self._milestone(project=self.project_b)
        with self.assertRaises(ValidationError):
            self.sprint_a.milestone_id = other

    def test_sprint_ending_after_the_milestone_deadline_is_at_risk(self):
        today = fields.Date.context_today(self.env['project.milestone'])
        milestone = self._milestone(deadline=today + timedelta(days=5))
        self.sprint_a.milestone_id = milestone
        self.assertTrue(self.sprint_a.milestone_at_risk)   # sprint acaba em 14 dias
        milestone.deadline = today + timedelta(days=30)
        self.assertFalse(self.sprint_a.milestone_at_risk)

    def test_reached_milestone_or_closed_sprint_is_not_at_risk(self):
        today = fields.Date.context_today(self.env['project.milestone'])
        milestone = self._milestone(deadline=today + timedelta(days=5))
        self.sprint_a.milestone_id = milestone
        milestone.is_reached = True
        self.assertFalse(self.sprint_a.milestone_at_risk)
        milestone.is_reached = False
        self.sprint_a.state = 'closed'
        self.assertFalse(self.sprint_a.milestone_at_risk)

    def test_milestone_lists_its_sprints(self):
        milestone = self._milestone()
        self.sprint_a.milestone_id = milestone
        self.assertEqual(milestone.sprint_ids, self.sprint_a)

    def test_deleting_a_milestone_keeps_the_sprint(self):
        milestone = self._milestone()
        self.sprint_a.milestone_id = milestone
        milestone.unlink()
        self.assertFalse(self.sprint_a.milestone_id)

    def test_milestone_changes_notify_the_team(self):
        milestone = self._milestone()
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(milestone))
        milestone.with_user(self.lead_a).write({'is_reached': True})
        self.assertIn(self.eng_a1.partner_id, self.team_notifications(milestone))
