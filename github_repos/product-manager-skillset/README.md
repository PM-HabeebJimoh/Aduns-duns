# product-manager-skillset

Agent Skills for working alongside a Product Manager (PM) — following the [shadcn skill format](https://github.com/shadcn-ui/ui/tree/main/skills). Drop these into any agent that supports Agent Skills (Claude Code, Codex CLI, Cursor, Windsurf, etc.) and it will proactively help with discovery, PRDs, prioritization, metrics, and launches — using the same conventions and vocabulary a senior PM would.

## Install

```bash
npx skills add PM-HabeebJimoh/Aduns-duns --skill product-manager --global
```

Or copy the folder manually into your agent's skills directory:

```bash
cp -r skills/product-manager ~/.claude/skills/
# or ~/.codex/skills/, ~/.cursor/skills/, etc.
```

## What's Inside

```text
skills/
└── product-manager/
    ├── SKILL.md                          # Main skill — activation, workflow, response format
    ├── references/
    │   ├── prd-template.md               # Canonical PRD structure with field-by-field guidance
    │   ├── prioritization-frameworks.md  # RICE, ICE, WSJF, Kano, MoSCoW — when to use each
    │   ├── metrics-frameworks.md         # North Star, AARRR, HEART, input vs. output metrics
    │   ├── discovery-playbook.md         # Continuous discovery, JTBD, interview scripts
    │   ├── okr-guide.md                  # Writing outcome-based OKRs, common anti-patterns
    │   ├── stakeholder-comms.md          # Status updates, escalation, exec review formats
    │   └── launch-checklist.md           # Beta → GA rollout gates, comms, rollback plans
    ├── examples/
    │   ├── prd-example.md                # A filled-in PRD for a fictional feature
    │   ├── rice-scoring-example.md       # A worked RICE prioritization
    │   └── weekly-update-example.md      # A well-written weekly stakeholder update
    └── scripts/
        └── new-prd.sh                    # Scaffolds a new PRD from the template
```

## Skills Provided

### `product-manager`
Acts as an embedded senior PM. Activates proactively when the user is:
- Writing a PRD, spec, one-pager, or launch doc
- Prioritizing a backlog or roadmap
- Defining success metrics or OKRs
- Preparing a stakeholder update or exec review
- Framing a discovery / research plan
- Planning a launch (beta, phased rollout, GA)

And explicitly when the user says things like *"write a PRD for…"*, *"prioritize this list"*, *"what metric should I track"*, *"help me plan the launch"*, *"draft an OKR"*, *"how should I frame this to the exec team"*.

## Design Principles

Same as the shadcn skill philosophy:

1. **Search / template before generating from scratch.** Reuse the canonical PRD, OKR, and update formats in `references/` before inventing new ones.
2. **Small, composable references.** Each reference file solves one thing well. The main `SKILL.md` stays short and routes the agent to the right reference.
3. **Concrete over abstract.** Every reference includes a worked example — no generic advice without a filled-in artifact next to it.
4. **Action-oriented output.** Responses end with the next decision, not with a summary.

## Compatibility

- Claude Code (`~/.claude/skills/`)
- Codex CLI (`~/.codex/skills/`)
- Cursor & Windsurf (`.cursor/skills/`, `.windsurf/skills/`)
- Any agent that reads YAML-frontmatter Markdown skills

## Contributing

PRs welcome. Highest-value additions:
- New reference files (competitive teardowns, pricing frameworks, incident post-mortems)
- More worked examples in `examples/`
- Localized versions of the PRD template

## License

MIT
