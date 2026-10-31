# Larkspur engagement

This repo is a simulated forward deployed engineering engagement for Larkspur Freight Lines, a fictional regional LTL carrier. Every person, system, customer and number here is invented, and all data is synthetic. Manoj is using it to practice FDE work end to end, from November 2, 2026 to March 21, 2027.

The engagement design, the week by week plan and the coverage matrix live in the claude-field-notes repo under engagement/. Read DESIGN.md there before planning any week's work, and check which week it is.

## Where this runs

Everything runs on cooper, Manoj's Ubuntu VPS. This repo lives at ~/projects/larkspur-engagement and Claude Code runs on cooper itself, under Manoj's normal user without sudo. Nothing runs on his Mac.

## The learning contract

Manoj writes everything Larkspur's people would touch: the agents, the MCP server, the evals, the gateway, the console and the infrastructure for them. In those areas, pair: explain, review, suggest the next step, write tests on request, and answer questions. Don't write the implementation unless he asks for it outright, and when you notice you've started, stop and hand it back.

Claude may write freely: the legacy estate, the data generator and world engine, scaffolding and boilerplate, CI wiring, Dockerfiles and compose files, and reviews.

## Layout

* legacy/: Larkspur's old systems, built to behave like twelve year old software
  * freightcore/: FREIGHTCORE's XML over HTTP service in the 2014 SOAP style, with a WSDL, header auth, internal status codes and a five worker limit
  * deskline/: Deskline, the SaaS helpdesk Larkspur's support team uses, with a bearer token API, rate limits and a ticket webhook
  * batch/: the nightly fixed width extracts and the EDI 214 run at noon and 6pm
  * schema/: FREIGHTCORE's cryptic Postgres schema and Deskline's
* data/: the seeded history generator. Same seed, same Larkspur, every run
* world/: larkspur world, which moves the business forward on a real Eastern time clock
* mcp/: freightcore mcp, TypeScript in strict mode with Zod and Vitest
* agents/: Python with uv, ruff, pyright and pytest; FastAPI services and Agent SDK agents
* evals/: golden sets, graders and the eval harness; the held out split is never used for tuning
* console/: React and TypeScript with Vite
* gateway/: the LLM gateway, TypeScript
* infra/: compose files, up.sh, smoke.sh, Caddy snippets and deploy scripts
* docs/deliverables/: client deliverables, each submitted as a pull request labeled deliverable

## Scenery rules

legacy/, data/ and world/ are scenery. Before November 16, don't summarize or explain their internals to Manoj unless he asks; reading FREIGHTCORE is the week 3 exercise. data/larkspur_data/scenario.enc holds Larkspur's hidden facts and incident calendar. Never decrypt it, print it, or reason from it out loud. The world engine reads it at runtime with LARKSPUR_SCENARIO_KEY, and that's the only thing that should.

The sim schema in Postgres belongs to the simulation, not to Larkspur. sim.truth holds the true category of every contact. Don't use it to build or tune anything; it exists only for a final calibration check on the held out split at the end of the engagement.

* Plan mode for any change in legacy/
* Agents and tools never write to FREIGHTCORE's tables. The one write path is the SOAP service's SchedulePickup, used from week 7
* Keep legacy code crufty. Don't refactor or clean it up unless the week's exercise calls for it

## Running Larkspur

* Start or update: `./infra/up.sh`, which builds the image, seeds the database the first time and runs smoke.sh. `./infra/up.sh --reseed` rebuilds history from the seed
* Health: `./infra/smoke.sh`. Logs: `docker compose -f infra/compose.yaml logs -f world`
* Every port binds to 127.0.0.1 because Docker's published ports bypass ufw. FREIGHTCORE is on 8080, Deskline on 8090, Postgres on 5433. Manoj reaches them with an SSH tunnel such as `ssh -L 8090:127.0.0.1:8090 cooper`
* Public endpoints come later through the existing Caddy server: the agent console and a tracking page, each on a subdomain of agentdidthis.dev behind sign in, and freightcore mcp's remote endpoint behind OAuth. Every public page says Larkspur is fictional
* Caddy and anything under /var/www/site need sudo. Propose the exact change and let Manoj run it; never edit the live site's files
* Secrets live in .env on cooper and in GitHub Actions secrets, never in the repo. The Anthropic key comes from a separate workspace with a monthly spend limit
* Ansible practice targets a throwaway VM, never cooper

## Writing

Deliverables, docs and commit messages follow Manoj's writing rules: no dashes, no parentheses as rhythm, sentence case headings, plain words, concrete numbers.
