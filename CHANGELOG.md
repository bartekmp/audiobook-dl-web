# CHANGELOG



## v0.2.0 (2025-12-31)

### Feature

* feature: cache busting (#2)

* feature: add cache busting to avoid using old front files

* fix: sanitize folder names

* fix: match proper file for metadata retrieval ([`4568a66`](https://github.com/bartekmp/audiobook-dl-web/commit/4568a666159931128307d88b37bac704c1b382d5))


## v0.1.0 (2025-12-30)

### Feature

* feature: bump version ([`a535fb1`](https://github.com/bartekmp/audiobook-dl-web/commit/a535fb1bfe4a01b3f231599a9b17af11868ad1be))

* feature: Major UI/UX improvements and code refactoring

Features:
- Add real-time progress tracking with percentage updates for downloads
- Extract metadata (title, author, narrator, duration, size) from completed files
- Add service badges to identify audiobook platforms at a glance
- Implement collapsible task cards with persistent state during polling
- Add favicon with custom SVG design
- Optimize polling to stop when no active downloads present
- Display full file paths with improved dark mode styling

Code Quality:
- Extract output parsing logic to dedicated output_processor.py module
- Refactor JavaScript: extract constants, merge duplicate functions
- Refactor Python: add helper functions, reduce code duplication (~190 lines)
- Add task.duration property to eliminate repeated calculations
- Replace print() with logger for consistent error handling
- Simplify template context rendering with get_base_context() helper

Documentation:
- Add screenshots for all major features (home, config, downloads, settings)
- Update README with new user-facing features and capabilities ([`f4474c2`](https://github.com/bartekmp/audiobook-dl-web/commit/f4474c297a3f76704c5cfd743e4328c75df981db))

### Unknown

* Merge pull request #1 from bartekmp/feature/major-upgrades

feature: Major UI/UX improvements and code refactoring ([`3b98f64`](https://github.com/bartekmp/audiobook-dl-web/commit/3b98f6494c449b4b80ffa39c5340ea5450d7b5c8))


## v0.0.2 (2025-12-29)

### Fix

* fix: use correct semrel output variable name ([`4bc0c69`](https://github.com/bartekmp/audiobook-dl-web/commit/4bc0c69233e8c7bba7f16397c9cf24c52bf658f2))


## v0.0.1 (2025-12-29)

### Fix

* fix: GH Actions permissions ([`b22c355`](https://github.com/bartekmp/audiobook-dl-web/commit/b22c355a652faabfe45fc2446a88af7da33dce3f))

### Unknown

* audiobook-dl-web project v0.1.0 ([`017976f`](https://github.com/bartekmp/audiobook-dl-web/commit/017976fb7a24567f560b99ec1ded14996cbdddbe))
