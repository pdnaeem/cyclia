# Maintainer notes

## Author credits

All author information lives in `credits.json`. After editing it, run `python engine/tools/apply_credits.py`
(the build scripts do this automatically). It updates the Windows installer pages and images, the start-up
splash, the welcome screen, Help > About (with photo, links and copy-ready citation), the footer and
reference list of every Word report, the Excel exports, `CITATION.cff`, `LICENSE` and `app/package.json`.
Setting `repository` to the GitHub URL also points auto-update at that repository.

## Signing (removes "unknown publisher" warnings)

Buy a code-signing certificate (Windows) and an Apple Developer account (macOS), then add the repository
secrets listed at the top of `.github/workflows/build.yml` and set `mac.notarize` to `true` in
`app/package.json`. Unsigned builds work without them.

When you have a Windows certificate, also add `"signtoolOptions": {"publisherName": "<the name on the
certificate>"}` under `build.win` in `app/package.json`. Do not add it before: the updater then verifies the
signature of every downloaded update, and unsigned updates are rejected (this broke updates in 1.2.x).

## Before and after the first public release

These need things only you have:
1. Run the benchmark on a real ecoinvent release against ecoinvent's own LCIA results or openLCA.
2. Run the ecoinvent login connector once with real credentials.
3. Confirm with ecoinvent that a desktop tool reading the user's own download fits their licence.
4. Buy the signing certificates if you want warning-free installs.
5. Trademark search for "Cyclia"; put the repository on GitHub with a DOI (Zenodo); publish a software paper
   (JOSS, SoftwareX or Int J LCA) with `docs/METHODS.md`, the validation suite and the ecoinvent benchmark
   (publish aggregate deviations only, not ecoinvent's values).

The tutorial database is illustrative only and must not be cited.

## Releasing an update

1. Put the changed files into the repository folder (or edit them there).
2. Run `python engine/tools/new_version.py 1.2.1` (with the new number). It sets the version everywhere,
   adds a changelog section and creates `docs/RELEASE_NOTES_v1.2.1.md`. Fill in both.
3. GitHub Desktop: commit "Cyclia 1.2.1", then Push origin.
4. History tab: right-click the commit, Create Tag, `v1.2.1`, then Push origin (it pushes the tag).
5. GitHub Actions builds the installers and publishes the release (about 30 minutes). Paste the release
   notes into the release description. Zenodo gives the new version a DOI. Installed copies update
   themselves on their next start.

Version numbers: last digit for fixes (1.2.1), middle for new features (1.3.0), first for big changes
that break old project files (2.0.0).
