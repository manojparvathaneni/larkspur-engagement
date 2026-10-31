# Larkspur Freight Lines engagement

A simulated forward deployed engineering engagement for Larkspur Freight Lines, a fictional regional LTL carrier. Every person, system, customer and number here is invented, and all data is synthetic. Any resemblance to a real carrier is accidental.

I'm Manoj Parvathaneni, a support engineer learning to build with Claude on the way to forward deployed engineering. From November 2026 to March 2027 I'm running a full engagement for Larkspur the way an FDE would: discovery, evals, an MCP server over a legacy system, agents, a pilot launch, security review and handover.

Larkspur is alive. A seeded history gives it a past quarter of 120,000 shipments and 24,000 customer contacts, and a world engine keeps the business moving on a real clock: freight gets picked up and scanned, invoices go out, things get damaged, customers write in, and Larkspur's own agents answer at their usual pace.

Larkspur's people reach me through issues labeled client; docs/CLIENT.md explains how that works. What I learn each week is written up in my field notes.

## Layout

* legacy: Larkspur's old systems: FREIGHTCORE's SOAP style service, the Deskline helpdesk, batch jobs and EDI
* data: the seeded history generator
* world: the engine that runs Larkspur on a real clock
* mcp: freightcore mcp, the MCP server over the legacy system, in TypeScript
* agents: the support resolution agent and claims assistant, in Python
* evals: golden sets, graders and the eval harness
* console: the agent console, in React and TypeScript
* gateway: the LLM gateway
* infra: compose, startup and smoke tests
* docs/deliverables: what Larkspur's stakeholders receive

## Running it

On a Linux host with Docker:

    cp .env.example .env    # fill it in
    ./infra/up.sh
