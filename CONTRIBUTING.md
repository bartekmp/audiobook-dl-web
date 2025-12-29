# Contributing to audiobook-dl-web

## Commit Message Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages. This enables automatic semantic versioning and changelog generation.

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature (triggers MINOR version bump)
- **fix**: A bug fix (triggers PATCH version bump)
- **perf**: Performance improvements (triggers PATCH version bump)
- **docs**: Documentation changes only
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without feature changes
- **test**: Adding or updating tests
- **build**: Changes to build system or dependencies
- **ci**: Changes to CI configuration files and scripts
- **chore**: Other changes that don't modify src or test files

### Breaking Changes

To trigger a MAJOR version bump, add `BREAKING CHANGE:` in the footer or add `!` after the type:

```
feat!: remove deprecated API endpoint

BREAKING CHANGE: The /old-api endpoint has been removed. Use /new-api instead.
```

### Examples

```
feat(download): add support for batch URL validation

fix(config): resolve issue with empty config file creation

perf(download): improve concurrent download performance

docs(readme): update installation instructions

chore(deps): update fastapi to 0.115.0
```

## Pull Request Process

1. Ensure your code passes linting: `ruff check . && ruff format .`
2. Update documentation if needed
3. Use conventional commit messages
4. The CI will automatically run tests and linting
5. On merge to main, semantic-release will automatically version and release if applicable
