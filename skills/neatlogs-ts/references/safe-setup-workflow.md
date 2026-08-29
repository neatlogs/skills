# Safe setup and verification

Use this workflow before changing a TypeScript project. It prevents a Skill from
mistaking installation, compilation, local span creation, or HTTP acceptance for
a working customer trace.

## 1. Detect without editing

Inspect `package.json`, the lockfile, runtime configuration, framework imports,
installed `neatlogs` version, and existing wrappers/hooks. Read
[`support-manifest.json`](support-manifest.json). If Node or the SDK is older than
the declared minimum, stop with the documented upgrade command. Do not guess an
integration for an ambiguous multi-service repository.

## 2. Run local Doctor

Run the manifest's `doctor.local_command` from the target package. `--no-install`
is mandatory: Doctor must use the already-installed SDK and must not download or
execute a package implicitly. `doctor --local` is read-only and network-free.

Require `format_version: "neatlogs.doctor/v2"`. If the executable or contract is
missing, report the installed version and upgrade requirement; do not edit source.
Never copy credentials into the command line, Skill text, source, logs, or agent
context.

## 3. Plan only supported changes

Use explicit wrappers and hooks from the support table in `SKILL.md`. Never add an
`instrumentations` init option or an Edge entrypoint. Show the user the proposed
files, commands, and diff before mutation. Preserve unrelated edits and existing
package-manager choices.

Only apply deterministic local fixes after approval. A missing credential is not
a source-code fix: ask the user to configure it through their normal secret store.
Backend-only reason codes are not locally repairable.

## 4. Validate and roll back safely

Run only user-approved install, format, typecheck, test, build, start, and exercise
commands. If an approved edit breaks validation, revert only the changes made by
this Skill or give exact manual recovery steps. Never discard pre-existing work.

Run the workflow a second time. A correctly instrumented project must require no
additional source edits.

## 5. Prove persisted visibility

Exercise a real application path using generated non-user diagnostic content, then
run the manifest's `doctor.probe_command`. Success requires a correlated diagnostic
session whose backend receipts reach finalized visibility with a non-empty,
complete persisted span tree. Stop with the diagnostic ID and first stable reason
code for backend-only failures.

Do not claim success from package installation, build success, local spans, HTTP
2xx, Kafka enqueue, or an uncorrelated/latest trace.
