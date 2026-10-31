# Larkspur Freight Lines engagement

A simulated forward deployed engineering engagement for Larkspur Freight Lines, a fictional regional LTL carrier. Every person, system, customer and number here is invented, and all data is synthetic. Any resemblance to a real carrier is accidental.

I'm Manoj Parvathaneni, a support engineer learning to build with Claude on the way to forward deployed engineering. From November 2026 to March 2027 I'm running a full engagement for Larkspur the way an FDE would: discovery, evals, an MCP server over a legacy system, agents, a pilot launch, security review and handover. Larkspur's old systems are deliberately old, so the integration work is real.

What I learn each week is written up in my field notes.

## Layout

* legacy: Larkspur's old systems, deliberately twelve years old
* data: the seeded synthetic data generator
* mcp: freightcore mcp, the MCP server over the legacy system, in TypeScript
* agents: the support resolution agent and claims assistant, in Python
* evals: golden sets, graders and the eval harness
* console: the agent console, in React and TypeScript
* gateway: the LLM gateway
* infra: compose files, Caddy snippets and deploy scripts
* docs/deliverables: what Larkspur's stakeholders receive
