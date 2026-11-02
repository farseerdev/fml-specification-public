# Governance

## Roles

- **Editor** — Zrinko Dolic (Farseer). The editor maintains the specification,
  its companion documents and this repository, and decides on changes.
- **Contributors** — anyone who opens an issue or a pull request.

## How a change is decided

1. A change starts as an issue or a pull request that states the problem, the
   proposed text and, for a language change, a minimal model that shows it
   (CONTRIBUTING.md).
2. The editor labels it: *correction*, *clarification*, *new feature* or
   *breaking*. A *breaking* change waits for the next major version.
3. A proposal is open for comment for at least 14 days before it is merged,
   except corrections of typing errors and broken references.
4. The editor merges or declines it, and says why. A declined proposal can be
   raised again with new evidence.

## The standard and its implementation profiles

The specification defines the language. What an engine adds beyond it is
documented in that engine's implementation profile (FML §2.5); the names a
published profile uses are listed in FML Annex D and are never given another
meaning by a later version of the specification [EXT-4]. A profile may be
proposed by anyone who implements FML; the Farseer Implementation Profile is
maintained by Farseer.

## Releases

A release fixes a version of the specification and of its companion
documents, tags the repository and records the changes in CHANGELOG.md and in
Annex G. Versioning follows CONTRIBUTING.md.
