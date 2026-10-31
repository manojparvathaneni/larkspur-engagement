# Larkspur engagement

This repo is a simulated forward deployed engineering engagement for Larkspur Freight Lines, a fictional regional LTL carrier. Every person, system, customer and number here is invented, and all data is synthetic. Manoj is using it to practice FDE work end to end, from November 2, 2026 to March 21, 2027.

The engagement design, the week by week plan and the coverage matrix live in the claude-field-notes repo under engagement/. Read DESIGN.md there before planning any week's work, and check which week it is.

## The learning contract

Manoj writes everything Larkspur's people would touch: the agents, the MCP server, the evals, the gateway, the console and the infrastructure. In those areas, pair: explain, review, suggest the next step, write tests on request, and answer questions. Don't write the implementation unless he asks for it outright, and when you notice you've started, stop and hand it back.

Claude may write freely: the legacy estate in legacy/ and its data generator, scaffolding and boilerplate, CI wiring, Dockerfiles and compose files, and reviews.

## Layout

* legacy/: Larkspur's old systems, built by Claude to look twelve years old: COBOL batch programs, MySQL 5.5, the PHP 5.6 SOAP service, the old portal, the green screen terminal app, EDI drop folders. Before November 16, don't summarize or explain its internals to Manoj unless he asks; reading it is the week 3 exercise
* data/: the seeded synthetic data generator. Same seed, same Larkspur, every run
* mcp/: freightcore mcp, TypeScript in strict mode with Zod and Vitest
* agents/: Python with uv, ruff, pyright and pytest; FastAPI services and Agent SDK agents
* evals/: golden sets, graders and the eval harness; the held out split is never used for tuning
* console/: React and TypeScript with Vite
* gateway/: the LLM gateway, TypeScript
* infra/: compose files, Caddy snippets, Ansible and deploy scripts
* docs/deliverables/: client deliverables, each submitted as a pull request labeled deliverable

## Rules for legacy/

* Plan mode for any change in legacy/
* Never write to FREIGHTCORE's database from agents or tools except through the SOAP service's schedulePickup, and only once week 7's pickup booking exists
* Keep it crufty. Don't refactor, add tests to or clean up legacy code unless the week's exercise calls for it

## Deploying to cooper

* Reach cooper over SSH with the host alias cooper. Deploys use docker compose from infra/
* Legacy services and MySQL never face the internet. PHP 5.6 and MySQL 5.5 get no security fixes, so they bind only to the internal compose network and Manoj reaches them through an SSH tunnel
* Public endpoints go through the existing Caddy server: the agent console and a tracking page, each on a subdomain of agentdidthis.dev behind sign in, and freightcore mcp's remote endpoint behind OAuth. Every public page says Larkspur is fictional
* Caddy and anything under /var/www/site need sudo. Propose the exact change and let Manoj run the sudo step; never edit the live site's files
* Secrets live in a .env file on cooper and in GitHub Actions secrets, never in the repo. The Anthropic key comes from a separate workspace with a monthly spend limit
* Before the first deploy, check capacity with free -h, nproc and docker info, and stop if memory is under about 4 GB free for the stack
* Ansible practice targets a throwaway VM, never cooper

## Writing

Deliverables, docs and commit messages follow Manoj's writing rules: no dashes, no parentheses as rhythm, sentence case headings, plain words, concrete numbers.
