# LLM-PDDL MSc Project Handoff

## 1. Project goal

This MSc project builds a unified and extensible LLM + PDDL planning
and verification pipeline.

The final system should support these planning domains:

1. block_building
2. occlusion_manipulation
3. gearbox_assembly

The architecture must allow:

- adding a new scene in an existing domain mainly by adding a scene JSON;
- adding a new domain by adding:
  - domain.pddl
  - domain_config.json
  - a domain adapter
  - a symbolic verifier
  - scene JSON files;
- keeping the common pipeline unchanged when scenes or domains are added.

VAL remains the final authority for plan validity.
The Python symbolic verifier is used for fast diagnosis and detailed
feedback, not as a replacement for VAL.

Fast Downward, VAL, the refinement loop, batch runner, and result
collector already exist and must not be reimplemented without evidence
that functionality is missing.

---

## 2. Required working method

Before modifying any code:

1. Inspect the current relevant files.
2. Search for existing implementations to avoid duplication.
3. State clearly whether each action is:
   - REVIEW
   - ADD
   - REPLACE
   - TEST
   - COMMIT
4. Make one small, testable change at a time.
5. Preserve the currently working Scene 02 pipeline until its replacement
   has been independently tested.
6. Do not guess current file contents from old conversation summaries.
7. Do not move or rename files unless current code proves it is necessary.
8. Do not use `git add .`.
9. Do not commit generated PDDL or temporary search reports unless the
   repository already intentionally tracks them.
10. If evidence is insufficient, explicitly say what cannot be confirmed.

---

## 3. Target architecture

The intended common flow is:

scene JSON
-> SceneConfig
-> DomainConfig
-> dynamically loaded DomainAdapter
-> prepared SceneConfig
-> generic PDDL problem builder
-> domain-independent PlanModel
-> dynamically loaded symbolic verifier
-> LLM plan generation
-> VAL validation
-> structured feedback
-> iterative repair
-> batch execution
-> result collection

Domain-specific behavior must not be placed in the common pipeline.

Common modules should not contain block/occlusion/gearbox-specific
object names, predicates, actions, or scene IDs.

---

## 4. Current scenes

Current scene files are located directly under:

data/scenes/

Current files:

- data/scenes/scene_01_blocksworld_basic.json
- data/scenes/scene_02_pyramid.json
- data/scenes/scene_03_large_pyramid.json

Do not assume they are under data/scenes/block_building/.
Do not move them during the current pipeline migration.

All three scenes have:

domain_id = block_building

Expected plans:

- scene_01_blocksworld_basic: 4 steps
- scene_02_pyramid: 6 steps
- scene_03_large_pyramid: 12 steps

---

## 5. Completed common infrastructure

The following modules have been added and tested:

### JSON and configuration

- src/config_io.py
- src/scene_config.py
- src/domain_config.py

Responsibilities:

- shared JSON-object loading;
- recursive scene discovery;
- explicit domain_id;
- flat and typed objects;
- domain pack discovery;
- predicate/action arity configuration;
- canonical project paths.

### Block domain pack

- domains/block_building/domain.pddl
- domains/block_building/domain_config.json

Current block domain has:

Predicates:
- ontable/1
- on/2
- on-bridge/3
- clear/1
- holding/1
- handempty/0
- left-free/1
- right-free/1

Actions:
- pick-up/1
- put-down/1
- stack/2
- unstack/2
- stack-bridge/3
- unstack-bridge/3

### Generic PDDL problem generation

- src/pddl_problem_builder.py

Responsibilities:

- validate predicates using DomainConfig.predicate_arities;
- support zero-, unary-, binary-, and higher-arity predicates;
- support underscore-to-hyphen predicate resolution;
- generate problem.pddl for different domains;
- not contain block-specific defaults.

### Domain adapter architecture

- src/domain_adapters/base.py
- src/domain_adapters/__init__.py
- src/domain_adapters/block_building.py

Common DomainAdapter interface:

- validate_domain_link()
- validate_scene()
- prepare_scene()
- build_plan_prompt()
- build_feedback()

Dynamic loading uses:

domain_config.json:
"adapter": "<module_name>"

BlockBuildingAdapter responsibilities:

- validate block scenes;
- preserve ordinary Scene 01 state;
- detect bridge scenes;
- add missing left_free/right_free defaults for bridge scenes;
- preserve explicitly supplied values;
- build scene-specific block prompts;
- add block-specific repair guidance.

### Domain-independent plan model

- src/plan_model.py

Responsibilities:

- immutable PlanStep;
- parse function-style actions;
- parse PDDL-style actions;
- validate action name against DomainConfig;
- validate action arity;
- validate scene object references;
- load expected_plan from SceneConfig;
- output structured JSON plan;
- output VAL-compatible PDDL plan text.

### Symbolic verifier architecture

- src/verifiers/base.py
- src/verifiers/__init__.py
- src/verifiers/block_building.py

Responsibilities:

- common VerificationResult;
- dynamic verifier loading;
- block state simulation;
- ordinary BlocksWorld actions;
- bridge actions;
- detailed failure location and state context;
- all supported positive block goals.

Important fix:

The old Scene 02 verifier did not check ordinary `on` goals.
The new BlockBuildingVerifier checks Scene 01 goal:
on(blockB, blockC).

VAL remains authoritative.

---

## 6. Tests already created and passed

- test_scene_config.py
- test_domain_config.py
- test_pddl_problem_builder.py
- test_domain_adapter_base.py
- test_block_building_adapter.py
- test_plan_model.py
- test_block_building_verifier.py

Verified outcomes:

- all three scenes load;
- all three scenes link to block_building;
- generic PDDL problems can be generated;
- Scene 02 receives 6 left/right support-slot defaults;
- Scene 03 receives 10 left/right support-slot defaults;
- Scene 01 does not receive bridge defaults;
- expected plans load as 4, 6, and 12 steps;
- all three expected plans pass BlockBuildingVerifier;
- incomplete Scene 01 plan fails ordinary on-goal checking;
- invalid Scene 02 plan fails at the correct handempty violation.

---

## 7. Existing legacy pipeline that must be migrated carefully

Current legacy files include:

- src/pyramid_demo_v3.py
- src/external_val_feedback_loop.py
- src/run_batch_refinement.py
- src/collect_refinement_results.py
- src/external_tools/fast_downward_runner.py
- src/external_tools/val_runner.py

The current external_val_feedback_loop.py is Scene 02-specific.

It currently imports legacy items from pyramid_demo_v3.py:

- LLMPlanner
- PlanStep
- REFERENCE_PLAN
- SCENE_DESCRIPTION
- SymbolicVerifier

It also uses fixed global values for:

- SCENE_NAME
- DOMAIN_FILE
- PROBLEM_FILE
- RESULTS_ROOT

These fixed globals are referenced by several functions, including run
directory creation, VAL execution, and summaries.

Do not merely delete these globals and create local variables in one
function. All dependencies must be traced and updated.

The legacy pipeline currently treats VAL as final authority and uses the
Python symbolic verifier for diagnostic feedback. Preserve this behavior.

---

## 8. Current next phase

The next phase is to migrate external_val_feedback_loop.py from a fixed
Scene 02 loop into a scene-selectable common block pipeline.

The intended CLI will eventually support:

--scene scene_01_blocksworld_basic
--scene scene_02_pyramid
--scene scene_03_large_pyramid

The loop should obtain runtime context through:

scene = load_scene_config(scene_id)
domain = load_domain_config(scene.domain_id)
adapter = get_domain_adapter(domain)
prepared_scene = adapter.prepare_scene(scene)
verifier = get_symbolic_verifier(domain)
problem_file = write_pddl_problem(prepared_scene, domain)
domain_file = domain.domain_file
results_root = prepared_scene.results_directory

However, migration must be incremental.

Do not rewrite the complete loop in the first change.

First review:

- all uses of SCENE_NAME;
- all uses of DOMAIN_FILE;
- all uses of PROBLEM_FILE;
- all uses of RESULTS_ROOT;
- current LLMPlanner interface;
- current plan parsing type;
- current mock/reference-plan logic;
- run-directory path construction;
- VAL input file generation;
- feedback creation;
- batch-runner assumptions.

Then propose the smallest safe first replacement.

---

## 9. Planned migration order

### Phase A — common runtime context

- add scene_id input;
- load SceneConfig and DomainConfig;
- dynamically load adapter and verifier;
- prepare scene;
- generate problem.pddl;
- resolve domain/problem/results paths;
- test initialization for all three scenes;
- do not yet run the complete LLM/VAL loop.

### Phase B — common plan type and parsing

- replace legacy PlanStep use with src.plan_model.PlanStep;
- adapt LLM output parsing without block-specific hard-coded action lists;
- load expected_plan from each scene;
- replace fixed REFERENCE_PLAN;
- keep output file format VAL-compatible.

### Phase C — common symbolic feedback

- replace legacy SymbolicVerifier with dynamically loaded verifier;
- use prepared SceneConfig;
- use adapter.build_feedback();
- keep VAL as final authority.

### Phase D — full single-scene loop tests

For Scene 01, Scene 02, Scene 03:

- reference plan -> VAL;
- invalid mock plan -> rejection;
- symbolic diagnosis -> structured feedback;
- corrected plan -> VAL acceptance.

### Phase E — batch and collection

Only after the single-scene loop passes all three scenes:

- add scene selection to run_batch_refinement.py;
- update collect_refinement_results.py;
- organize results by domain_id / scene_id / method / model / run.

### Phase F — new domains

After block pipeline is stable:

- occlusion_manipulation domain pack, adapter, verifier, scenes;
- gearbox_assembly domain pack, adapter, verifier, scenes.

The common pipeline must not be modified merely to register these domains.

---

## 10. Work not yet completed

The following are not yet complete:

- unified LLM output parser integrated into the new pipeline;
- external_val_feedback_loop.py migration;
- formal Fast Downward/VAL regression for all three block scenes;
- multi-scene batch runner;
- multi-scene result collector;
- occlusion domain;
- gearbox domain;
- Approach 2;
- final experiments and dissertation evaluation.

Do not claim these parts are complete.

---

## 11. Immediate safety gate for the next chat

Before suggesting a code modification, the assistant must:

1. inspect the current uploaded files;
2. inspect git status and recent commits;
3. list every fixed global and legacy import used by
   external_val_feedback_loop.py;
4. identify which functions depend on them;
5. state exactly which files will change;
6. state exactly which files will not change;
7. give a test that fails before the change and passes after it;
8. avoid changing batch, collector, or new-domain files in the same step.

Only after this review should code replacement instructions be provided.