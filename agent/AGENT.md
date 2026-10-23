# Use case

- **Pitch:** LocalGigs is an offline local-gig platform that helps people discover short-term event work and helps organizers review applications responsibly.
- **Who it is for:** Adults seeking local event opportunities and verified organizers. Any participation by people aged 14–18 requires age-appropriate opportunities, appropriate guardian approval and applicable legal safeguards.
- **Features:**
  - browse local gigs and submit applications;
  - organizers review applications and update application status;
  - a decision panel explains whether an application needs more information or can proceed to the next review step;
  - designed for eventual deployment on Amazon Bedrock AgentCore Runtime.
- **The decision handed to Strands Decider 2B:** before an application advances, is the proposed action grounded in the available gig details, explicitly requested, and sufficiently clear to proceed? (`#guardrails`)
- **Why a decision model:** it evaluates contextual ambiguity and returns confidence scores that the agent can use to guide or pause an action.
- **Amazon Bedrock:** the final hackathon deployment must use the required AWS services. Local development and hosted-model tests do not themselves satisfy that deployment requirement.
