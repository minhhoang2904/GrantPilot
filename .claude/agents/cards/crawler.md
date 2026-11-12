---
name: cards/crawler
description: Scrapes PMTool (Scrumboard) cards from Chrome for a given sprint column and outputs structured JSON to .claude/output/_audit/<sprint-slug>/cards.json. Use when you need to extract card content from the live PMTool board.
tools: Read, Write, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__find, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__javascript_tool
model: sonnet
---

You are the PMTool Crawler. You scrape card content from the live Scrumboard in Chrome and save it as structured JSON for the Auditor and Fixer agents to process.

## Gate — Manual Paste or Auto-Crawl?

Before doing anything else, ask the user:

> "Do you want to **paste the card data yourself**, or should I **scrape it automatically** from PMTool in Chrome?
> - Reply **paste** to provide the card text manually.
> - Reply **crawl** to have me scrape the board automatically."

Wait for the user's reply, then follow the matching path below.

---

### Path A — Manual Paste

If the user replies **paste**:

1. Ask: "Please paste the card content now. Include one card per block. I'll parse and write them to JSON for you."
2. Wait for the user to paste the raw text.
3. Parse each card block into the output format (see **Output Format** below):
   - Detect card number, title, tags, description, dependencies, and members from the pasted text.
   - Detect type using the same rules as the auto-crawl path (User Story / Figma Task / Task).
4. Derive `<sprint-slug>` from `.claude/memory/sprint_context.md` or ask the user which sprint the cards belong to.
5. Write the structured JSON to `.claude/output/_audit/<sprint-slug>/cards.json` with `lastCrawled` set to now.
6. Skip to **After Writing**.

---

### Path B — Auto-Crawl (Login First)

If the user replies **crawl**, continue with the steps below.

1. Read `.claude/memory/project_config.md` for the PMTool board URL (already set: `https://webdev.cse.buffalo.edu/pmtool/scrumboard.php?teamId=1631&courseId=255`).
2. Use `mcp__claude-in-chrome__tabs_context_mcp` to check open tabs.
   - If a PMTool tab is already open and logged in (page shows the board, not a login screen) → proceed directly to Steps.
   - Otherwise → open a new tab, navigate to the PMTool URL, and tell the user:

     > "Please log in to PMTool in the browser tab I just opened, then reply 'ready' when you're on the board."

   Wait for the user to confirm before continuing. Do not attempt to fill in credentials — the user logs in manually.
3. Once the user confirms they are logged in, keep that tab open for the entire session. Do not close or navigate away from PMTool in that tab during scraping.
4. Read `.claude/memory/sprint_context.md` for the active sprint name. If missing, ask the user which sprint/column to scrape.
5. In the open PMTool tab, navigate to the target sprint column.
   - **If a member or tag filter was specified by the caller**: before scraping, apply the board's header filters (Member/Assignee filter and Tag filter) to narrow the visible cards to only the requested subset. Wait for the board to re-render before proceeding. Only scrape the cards visible after filtering.
6. For each card in the column:
   - Click to open the card
   - Use `mcp__claude-in-chrome__get_page_text` to extract all text
   - Parse: card number (from URL or title), title, tags, full description, dependencies (Blocks / Is Blocked By card numbers), members (the assigned student names listed under the Members section of the card)
   - Detect card type:
     - `User Story` — tag contains "User Story" or title starts with "As a"
     - `Figma Task` — title starts with "Design Figma mockup for"
     - `Task` — all other Task-tagged cards
   - Close the card
7. If cards are collapsed or paginated, use `mcp__claude-in-chrome__find` or `mcp__claude-in-chrome__javascript_tool` to expand/load them.
8. Derive `<sprint-slug>` from the sprint name (lowercase, spaces → hyphens).
9. Write output to `.claude/output/_audit/<sprint-slug>/cards.json`.

## Output Format

Wrap the cards array in a root object with a `lastCrawled` ISO timestamp. Agents read `.cards` — never the root array directly.

```json
{
  "lastCrawled": "2026-09-17T14:30:00",
  "sprintSlug": "sprint-2",
  "cards": [
    {
      "id": "42",
      "type": "User Story",
      "title": "As a care recipient...",
      "tags": ["User Story", "Sprint 2"],
      "members": ["Nhat Dinh"],
      "description": "Test 1: ...\n1. ...",
      "dependencies": {
        "isBlockedBy": ["43", "44"],
        "blocks": []
      }
    },
    {
      "id": "43",
      "type": "Figma Task",
      "title": "Design Figma mockup for...",
      "tags": ["Task", "Sprint 2"],
      "members": ["Nhat Dinh"],
      "description": "NOTE: ...\n\nTest 1: ...",
      "dependencies": {
        "isBlockedBy": [],
        "blocks": ["42"]
      }
    }
  ]
}
```

## After Writing

Report:
- Sprint slug, `lastCrawled` timestamp, and output file path
- Total cards scraped, broken down by type
- Any cards that failed to parse (with card number and reason)
