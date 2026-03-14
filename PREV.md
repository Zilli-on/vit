I want you to generate a deeply comprehensive `CLAUDE.md` file for a startup-scale software project I am building.

The product idea is:

A Git / GitHub–style version control and collaboration system for video editing projects.

Core idea:
Traditional video editing workflows are extremely linear. In real creative production workflows, the main editor, colorist, sound designer, assistant editor, and creative director influence one another in parallel. I want to build a system that allows these collaborators to work in parallel, branch creative work, sync changes, review changes, and merge them back together in a way conceptually similar to Git/GitHub — but adapted for video editing timelines, media assets, and post-production workflows.

Important product framing:
This is NOT “Git for raw video files” in the naive sense.

Instead it should be framed as:

- GitHub-style collaboration for post-production
- version control for edit decisions and timeline metadata
- centralized asset management for heavy media
- semantic merging for timelines
- locking or ownership for non-mergeable binary workflows

This system should borrow architectural concepts from:

- Git
- GitHub
- SVN / Subversion
- Perforce
- collaborative editing systems

but apply them specifically to video editing pipelines.

The `CLAUDE.md` file you generate will act as the master operating manual for building this entire product using Claude Code.

The document must be extremely comprehensive, thoughtful, structured, and practical. It should guide implementation over many weeks and help Claude behave like a staff-level systems architect, founding engineer, and technical project planner.

Write the `CLAUDE.md` as if it will guide the entire development of this system.

Assume the implementation stack will likely be:

- TypeScript monorepo
- Next.js web app
- Node.js backend
- Postgres
- Redis
- S3-compatible storage
- FFmpeg media workers
- Electron or Tauri desktop sync client

Optimize architectural decisions around this stack unless there is a strong reason not to.

The `CLAUDE.md` should contain the following sections:

---------------------------------------

1. PROJECT PURPOSE

Define the product vision clearly:

- what problem this solves
- why current video editing collaboration workflows are broken
- why Git works well for code but cannot directly handle video projects
- how this system adapts Git concepts to video editing timelines
- how SVN/Perforce concepts help with large binary assets
- who the target users are (editors, colorists, sound designers, assistant editors)
- what the initial wedge / MVP should be
- what NOT to build initially

---------------------------------------

2. PRODUCT PHILOSOPHY

Include guiding principles such as:

- metadata, not media, is the primary merge surface
- centralized storage for heavy assets
- Git-like semantics for timeline changes
- semantic diff and merge, not file diff
- lock where necessary, merge where possible
- additive integration with existing NLEs first
- avoid corrupting production workflows
- reversible actions and auditability
- prioritize creative workflow clarity over developer-centric abstractions

---------------------------------------

3. SYSTEM ARCHITECTURE

Provide a detailed top-down architecture including:

- desktop sync client
- web review interface
- collaboration backend
- metadata database
- asset storage layer
- proxy generation pipeline
- search / indexing / transcript pipeline
- timeline parsing / normalization layer
- commit / branch / merge engine
- locking / conflict layer
- import/export adapters for NLEs

Include ASCII diagrams where helpful.

Explain how each subsystem interacts.

---------------------------------------

4. DOMAIN MODEL

Define the core entities and their relationships.

Example entities:

- Project
- Repository
- Asset
- Proxy
- Sequence
- Track
- ClipInstance
- TimelineOperation
- Commit
- Branch
- MergeRequest
- Conflict
- Lock
- ReviewComment
- User
- Workspace
- SyncJob

For each entity describe:

- purpose
- key fields
- relationships
- which subsystem owns it

---------------------------------------

5. VERSION CONTROL MODEL

Define the Git-inspired model for timeline metadata:

Explain:

- commits
- branches
- merges
- diffs
- rollback
- tags/milestones

Clarify that this is NOT line-based text merging.

Describe how commits should represent edit operations.

Discuss whether the system should use:

- snapshots
- event sourcing
- hybrid approaches

Explain commit graph structure and parent pointers.

---------------------------------------

6. LOCKING AND SVN-LIKE CONCEPTS

Describe how SVN / Perforce concepts are incorporated:

- centralized asset storage
- partial checkout / partial sync
- file or region locking
- binary-safe workflows
- preventing concurrent edits on unmergeable data

Explain when locking should be avoided and when it is required.

---------------------------------------

7. ASSET MANAGEMENT STRATEGY

Describe how media assets are handled:

- raw footage vs proxies
- hash-based asset identity
- deduplication
- object storage architecture
- selective downloads
- local caching
- upload pipelines
- checksum validation
- bandwidth-aware syncing
- proxy generation workers
- storage backends like S3 / R2 / B2 / NAS

Explain why media assets should NOT follow Git clone semantics.

---------------------------------------

8. TIMELINE / METADATA STRATEGY

Describe the internal representation of timelines.

Include:

- normalized timeline schema
- clip placements
- trims
- transitions
- markers
- effects
- color grading metadata
- audio automation
- subtitles

Discuss possible representations:

- JSON snapshots
- event sourcing
- protobuf structures
- CRDT / OT approaches

Recommend an MVP-friendly internal representation.

---------------------------------------

9. IMPORT / EXPORT STRATEGY

Explain how the system integrates with existing editors:

- Premiere
- DaVinci Resolve
- Final Cut
- Avid

Discuss formats such as:

- EDL
- XML
- FCPXML
- AAF

Explain why an import/export architecture is safer for MVP than deep plugin integration.

---------------------------------------

10. MVP SCOPE

Be extremely opinionated about the smartest MVP.

The MVP should likely include:

- import timeline from one format
- normalize to internal timeline schema
- commit history for timelines
- branching
- timeline diff viewer
- media asset manifest
- proxy sync
- comments and review

Explicitly list features that should NOT be attempted early.

---------------------------------------

11. IMPLEMENTATION PHASES

Break the build into clear phases:

Phase 0 – architecture + schema  
Phase 1 – timeline parsing and schema  
Phase 2 – commit graph and branching  
Phase 3 – diff engine and review UI  
Phase 4 – media manifest and proxy sync  
Phase 5 – merge engine  
Phase 6 – locking and conflict handling  
Phase 7 – deeper NLE integration

Each phase should include:

- goals
- components
- deliverables
- risks
- exit criteria

---------------------------------------

12. REPOSITORY STRUCTURE

Recommend a TypeScript monorepo layout.

Example:

apps/web  
apps/desktop  
services/api  
services/media-worker  
packages/timeline-schema  
packages/version-engine  
packages/importers  
packages/exporters  
packages/ui  
infra

Explain the responsibility of each module.

---------------------------------------

13. TECHNOLOGY STACK

Recommend specific tools and justify them.

Include:

- TypeScript
- Next.js
- Node.js backend
- Postgres
- Redis
- S3-compatible storage
- FFmpeg
- WebSockets
- Electron/Tauri
- job queues
- authentication
- observability

Also explain what NOT to over-engineer early.

---------------------------------------

14. API DESIGN

Outline the key APIs:

- project creation
- asset registration
- proxy generation
- sync operations
- commit creation
- branch creation
- diff retrieval
- merge requests
- lock acquisition
- comment system
- import/export

Provide naming conventions and example endpoints.

---------------------------------------

15. MERGE ENGINE GUIDANCE

Explain how to design semantic timeline merging.

Include:

- merge units (clip / track / sequence)
- conflict detection
- deterministic merge rules
- visual conflict resolution
- safe subset for MVP

Emphasize that merge logic is the hardest technical problem.

---------------------------------------

16. UX / PRODUCT GUIDANCE

Explain how the system should feel to creatives.

Include concepts like:

- GitHub-style timeline versioning
- visual timeline diffs
- commenting on time ranges
- branch naming conventions
- review / approval flows
- milestone tagging
- avoiding developer jargon in UX

---------------------------------------

17. ENGINEERING GUIDELINES

Include rules for how Claude Code should behave when contributing to this repo:

- act as a principal engineer
- maintain architectural consistency
- prefer incremental progress
- document assumptions
- avoid risky abstractions
- design for rollback and auditability
- propose tradeoffs before major decisions
- maintain strong typing and modular code

---------------------------------------

18. TESTING STRATEGY

Describe a robust test plan:

- parser tests
- schema validation
- diff engine tests
- merge logic tests
- asset checksum tests
- locking tests
- sync tests
- import/export roundtrip tests
- end-to-end workflows

---------------------------------------

19. RISK REGISTER

List major risks such as:

- NLE interoperability
- merge correctness
- bandwidth and sync performance
- binary metadata limitations
- user trust and data corruption
- plugin complexity
- adoption barriers

Provide mitigation strategies.

---------------------------------------

20. CLAUDE OPERATING INSTRUCTIONS

Explicitly instruct Claude Code how to assist with this project:

- behave like a staff engineer and systems architect
- prioritize clean architecture
- always restate subsystem goals before coding
- avoid silently inventing unsupported behaviors
- propose minimal next steps
- maintain consistency with this architecture
- update documentation as the system evolves

---------------------------------------

FINAL REQUIREMENTS

The output must be the full contents of the `CLAUDE.md` file.

Do not summarize.

Write the entire document as if it will guide the development of a serious startup product.

The document should be extremely structured, thorough, and implementation-oriented.

Include examples, schemas, diagrams, and tradeoff explanations where helpful.