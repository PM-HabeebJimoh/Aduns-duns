# product-manager

Agent Skill for Product Management work, written in the exact format used by the official [`shadcn-ui/ui`](https://github.com/shadcn-ui/ui/tree/main/skills/shadcn) skill: a `SKILL.md` with YAML frontmatter (`name`, `description`, `user-invocable`, `allowed-tools`), companion topic docs at the skill root, and a `rules/` directory of Incorrect/Correct pattern pairs.

## Install

Copy the skill directory into your agent's skills folder:

```bash
# Claude Code
mkdir -p ~/.claude/skills
cp -r skills/product-manager ~/.claude/skills/

# Cursor / Windsurf
mkdir -p .cursor/skills
cp -r skills/product-manager .cursor/skills/

# Copilot (AGENTS.md style)
curl -fsSL https://raw.githubusercontent.com/PM-HabeebJimoh/Aduns-duns/main/github_repos/product-manager-skillset/skills/product-manager/SKILL.md >> AGENTS.md
```

## Structure

Mirrors [`skills/shadcn/`](https://github.com/shadcn-ui/ui/tree/main/skills/shadcn) exactly:

```text
skills/product-manager/
├── SKILL.md              # Main entry — frontmatter + Principles + Critical Rules → rules/*
├── discovery.md          # Companion — user research, JTBD, interview technique
├── prd.md                # Companion — PRD canonical structure and field-by-field guidance
├── prioritization.md     # Companion — RICE / ICE / WSJF / Kano / MoSCoW selection & scoring
├── metrics.md            # Companion — North Star, AARRR, HEART, OKRs, metric definitions
├── launch.md             # Companion — dogfood → beta → % rollout → GA gates
├── rules/                # Enforced patterns with Incorrect/Correct pairs
│   ├── problem-framing.md
│   ├── prd-structure.md
│   ├── metrics-definition.md
│   ├── okrs.md
│   ├── prioritization.md
│   ├── stakeholder-comms.md
│   └── launch-safety.md
├── agents/               # (reserved) sub-agent prompts
├── assets/               # (reserved) diagrams, templates
└── evals/                # Prompt/response evals for skill quality
    └── prd-quality.md
```

Same conventions as the official shadcn skill:
- `SKILL.md` links out to each rule file via `→ [name.md](./rules/name.md)`
- Rules files open with a `## Contents` list, then one `##` heading per rule, then **Incorrect** / **Correct** blocks separated by `---`
- Companion docs at the skill root (like shadcn's `cli.md`, `customization.md`, `mcp.md`, `registry.md`) hold deep reference material

## License

MIT
