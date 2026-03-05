# Trusted Skill Repositories

When searching for existing skills to adapt, search these repositories in order.
All are MIT or Apache 2.0 licensed and safe to reference/adapt.

## Primary (large, well-maintained catalogs)

| Repository | URL | Skills | License |
|------------|-----|--------|---------|
| **Antigravity Awesome Skills** | `https://github.com/sickn33/antigravity-awesome-skills` | 978+ | MIT |

**Search pattern:** `https://github.com/sickn33/antigravity-awesome-skills/tree/main/skills/{skill-name}`
**Raw content:** `https://raw.githubusercontent.com/sickn33/antigravity-awesome-skills/main/skills/{skill-name}/SKILL.md`

## Official vendor skills

| Repository | URL | Focus | License |
|------------|-----|-------|---------|
| **Anthropic Skills** | `https://github.com/anthropics/skills` | Document manipulation, brand guidelines | MIT |
| **Vercel Labs Agent Skills** | `https://github.com/vercel-labs/agent-skills` | React best practices, web design | MIT |
| **Supabase Agent Skills** | `https://github.com/supabase/agent-skills` | Postgres best practices | MIT |
| **Microsoft Skills** | `https://github.com/microsoft/skills` | Azure, .NET, enterprise patterns | MIT |

## Search strategy

1. **Start with Antigravity** -- largest catalog, most likely to have a match
2. **Check vendor repos** -- if the skill is framework/tool-specific (React, Postgres, etc.)
3. **Web search fallback** -- `site:github.com "{skill-topic}" SKILL.md` for broader discovery

## Adaptation rules

When adapting an existing skill:
- **Keep** the structural quality (sections, tables, hard gates)
- **Replace** domain-specific content with the user's actual patterns and evidence
- **Add** the user's trigger phrases, constraints, and pitfalls from the analysis
- **Credit** the source in a comment: `<!-- Adapted from {repo} -->`
