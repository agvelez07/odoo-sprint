# Project Sprints — Odoo 18

`project_sprint` module for the *much. Consulting — Software Engineering Challenge*:
sprints for engineering teams, built on top of Odoo 18's **Project** app.

## Running the project

You need Docker + Docker Compose.

```bash
cp .env.example .env     # first time only (development values)
docker compose up -d     # creates the "sprints" database and installs the module
```

Open <http://localhost:8069> and log in as the administrator. Menu **Sprints** (top-left corner).

### Demo data (3 teams, 5 projects, 9 sprints, 8 milestones, 42 tasks, 12 users)

```bash
docker compose cp scripts/seed_demo.py odoo:/tmp/seed_demo.py
docker compose exec odoo bash -c "odoo shell -d sprints --db_host=db --db_user=odoo --db_password=odoo --no-http < /tmp/seed_demo.py"
```

(Works in bash, cmd and PowerShell: the `<` redirection happens inside the container.)
The script only creates the data if it does not exist yet, so it can be run more than once.

### Demo users

All use the `@demo.local` domain and the password **demo** (local environment only; to use another one,
run the second command as `docker compose exec -e DEMO_PASSWORD=... odoo bash -c "..."`).
Tip: open one incognito window per user to show the permission differences side by side.

| User | Role | Team |
|---|---|---|
| `gestor` | Project manager (sees and edits everything) | all |
| `ana.costa` | Lead | Backend |
| `bruno.silva`, `carla.mendes`, `diogo.ramos` | Engineers | Backend |
| `eduardo.faria` | Lead | Frontend |
| `filipa.rocha`, `goncalo.pinto`, `helena.duarte` | Engineers | Frontend |
| `ines.moreira` | Lead | DevOps and QA |
| `joao.lopes`, `katia.nunes` | Engineers | DevOps and QA |

`gestor@demo.local` shows the manager role without using Odoo's administration account.

### Automated tests

```bash
docker compose exec odoo odoo -d sprints_test -i project_sprint --test-enable --test-tags /project_sprint --stop-after-init --http-port=8070 --db_host=db --db_user=odoo --db_password=odoo
docker compose exec db dropdb -U odoo sprints_test
```

(the second line deletes the test database)

There are 55 tests (sprints, permissions, notifications and milestones). They use a separate
database, so the demo data is not touched.

### Starting from scratch

```bash
docker compose down -v   # deletes the database and Odoo's files
docker compose up -d
```

> If you already had data from an earlier version, open each **Team** and click **Sync followers**
> (managers only): it applies the visibility rules and notifications to the projects, sprints and tasks that already existed.

## What the module does

| Menu | Description |
|---|---|
| **My tasks** | Tasks assigned to me in planned or active sprints, sorted by deadline (`4 d left`, `3 d overdue`). |
| **Sprints** | List, kanban (by state) and points chart. The form shows progress, tasks, milestone and Start/Close buttons. |
| **Board** | Kanban of the tasks by stage, for all active sprints or a single one (**Board** button on the sprint). **Only leads and managers can drag.** |
| **Milestones** | Project milestones of the team. A sprint can point to a milestone and warns if it ends after the deadline. |
| **Teams** | Teams with a lead, members and roles (roles form a configurable hierarchy). |

Sprint business rules: one active sprint per project; tasks can only be in sprints of their own
project; a task can go through several sprints; when closing a sprint with unfinished tasks, a
wizard asks whether they move to another sprint or go back to the backlog; progress counts effort
points (or tasks, if there are no points); cancelled tasks do not count.

## Permissions

| | Manager | Team lead | Engineer |
|---|---|---|---|
| View projects, tasks, sprints, milestones and team | everything | own team only | own team only |
| Create, start, close and edit sprints | ✔ | own team | ✘ (view only) |
| **Reorder the board** (drag) | ✔ | own team | ✘ (view only) |
| Create and edit milestones | ✔ | own team | ✘ (view only) |
| Edit tasks | all | all of the team's | those assigned to them or created by them |
| Comment on tasks | ✔ | ✔ | ✔ (including colleagues' tasks) |
| Manage team members and roles | ✔ | own team | ✘ |
| Create teams | ✔ | ✘ | ✘ |

Projects without a team keep Odoo's normal behaviour.

## Notifications

Whenever someone changes something that belongs to a team, the lead and the members get a notice
in the Odoo inbox (messages icon), except the person who made the change:

- **Tasks:** change of stage, assignee, deadline, points, sprint, project, etc. (reordering the board does not notify).
- **Sprints:** creation, start/close, dates, milestone, tasks added or removed.
- **Milestones:** creation and changes (name, deadline, reached).
- **Team:** members joining, leaving or changing role; change of lead.
- **Automatic alerts** (daily scheduled action): a sprint that ends tomorrow or became overdue.

Anyone with an outgoing mail server configured and the "Email" preference in their profile also
receives them by email.

## Technical decisions (for the defence)

- **Teams = followers.** Visibility uses Odoo's native mechanism: a team's projects get "Followers"
  privacy and the team is subscribed to the projects, sprints and tasks. With the same mechanism this
  gives both the visibility filter (native rules) *and* the list of who is notified.
  Followers sync themselves when the team, the lead, the members or the project change.
- **Access rules (`security/security.xml`).** Group rules add up (OR) and global rules restrict (AND).
  That is why reading is granted by group rules (everyone sees their team) and editing of tasks and
  milestones by global rules with a manager exception. Write permissions also live in the database,
  not only in the interface.
- **Dragging on the board.** The read-only view has `records_draggable="false"`; the menu action picks
  the right view for the user. Since hiding things in the UI is not security, the task `write` rejects
  `sequence` changes from anyone who is neither the team lead nor a manager (`_check_can_reorder`).
- **Views by role.** A view that inherits from another cannot have `groups`; so there are primary
  views (`mode="primary"`) for the read-only version and the action chooses which one to open.
- **Notifications with `mail.thread`.** Instead of creating a new notifications model, the chatter and
  message subtypes are used. By default Odoo only notifies some changes (the others stay silently in
  the history); the `project.team.notify.mixin` mixin makes every tracked change notify the team.
- **Structure.** `deadline_mixin` (deadlines, shared by task and sprint) and `team_notify_mixin`
  (notifications) avoid repeated code; each model only says which team it belongs to (`_get_notify_team`).
- **Changing a record's project.** Moving a sprint or task to another project removes what belonged to
  the old project (tasks, milestone, sprints), both in the form (onchange) and on `write`
  (list, import, API), instead of leaving the user with a blocking error.

## Structure

```
addons/project_sprint/
├── models/      sprint, task, project, team, milestone, mixins (deadlines and notifications)
├── security/    groups, access rules (security.xml) and per-model permissions (ir.model.access.csv)
├── views/       sprints, board, my tasks, milestones, teams, tasks and projects
├── data/        roles, team message types, scheduled alerts action
├── wizard/      sprint closing wizard
├── tests/       55 automated tests
└── static/      styles
scripts/seed_demo.py   demo data
```

## Limitations and next steps

- The module's texts are in Portuguese and Odoo's are in English (no `.po` translation files).
- No burndown/velocity; the chart shows total and completed points per project.
- Deadline alerts run once a day (Odoo scheduled action).