---
name: orchestrators/feature-cards
description: Orchestrates full card generation from a feature request file — validates input, spawns cards/creator to generate User Story + all Task cards (sized to the 3-day checkpoint ceiling), runs structural consistency checks on the output, and reports with a manual follow-up checklist. Use when you have a filled .claude/resources/<feature>.md and want all cards generated in one command. (Tools: Read, Agent)
model: sonnet
---

# Orchestrate Feature Cards

End-to-end pipeline: `.claude/resources/<feature>.md` → `.claude/output/<slug>/user-story.md` + all Task cards.

## Step 1 — Validate the feature request

Read the file provided by the user. Check every template field:

| Field | Pass condition |
|---|---|
| `Feature name` | Present, not a placeholder |
| `Who wants it` | Present, not a placeholder |
| `What they do` | Present, not a placeholder |
| `What confirms it worked` | Present, not a placeholder |
| `Description` | Present, at least one sentence |
| `Sprint 1 demo?` | Either "yes" or "no" |

If any field fails → stop. Tell the user exactly which fields need filling. Do not proceed until all fields pass.

## Step 2 — Check for existing output

Derive the slug from the Feature name (kebab-case). Check whether `.claude/output/<slug>/` already contains any `.md` files.

- Empty or missing → proceed
- Files already exist → tell the user which files exist and ask for explicit confirmation to overwrite before continuing

## Step 3 — Spawn cards/creator

Spawn the `cards/creator` agent with:
- The path to the feature request file
- Instruction to write all output to `.claude/output/<slug>/`

Wait for the agent to complete and collect the list of files it wrote.

## Step 4 — Structural consistency checks

Read every file written by the cards/creator and verify:

| Check | Pass condition |
|---|---|
| `user-story.md` exists | File is present |
| Minimum task count | At least 2 task files (≥1 impl task + Figma task) |
| All tasks sized to 3 days | No task description suggests it spans more than one independent deliverable |
| Task `Blocks:` consistency | Every task's `Blocks:` value matches the user story title character-for-character |
| User story `Is Blocked By:` consistency | Every task title appears in the user story's `Is Blocked By:` list, and no extra entries exist |
| Figma task present | Exactly one task file has no `# GitHub Integration` section |
| No unfilled placeholders | No `<card-number>` in branch names is a violation — those are expected. Flag any other `<placeholder>` that was not intentionally left for the user to fill |

If any check fails → report each failure specifically (which file, which field, what was found vs. expected). Ask the user whether to re-run the cards/creator or fix manually.

## Step 5 — Report to user

On success, output:

```
Cards generated: .claude/output/<feature-slug>/

  user-story.md
  task-01-<slug>.md
  task-02-<slug>.md
  ...
  task-NN-figma-design.md

  Total: 1 User Story + N Task cards (including Figma Design task)
  All tasks sized to ≤3-day checkpoint ceiling ✓

Next steps (manual):
  1. Copy each file into the PMTool (Scrumboard) Backlog column.
  2. Once real card numbers exist, fill in <card-number> in every task's GitHub Integration branch name and confirm all dependency links on the board.
  3. Fill in the real Figma link(s) in the Figma Design task and verify every quoted button label, title, and UI text against the live Figma file.
  4. At sprint planning: move the story and its tasks to Planned, add the active sprint tag to all of them, assign members to each task, and verify the dependency web shows "Is Blocked By" on the User Story for every task.
```
