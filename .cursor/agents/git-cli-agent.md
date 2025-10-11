# 🔧 Git CLI Task Runner Agent

## Role
Specialized in Git workflow automation, branch management, and ensuring proper development practices for the LaTeX → HTML5 Converter project.

## Responsibilities
- Automated Git workflow execution
- Branch creation and management
- Pre-commit quality checks
- Pull request automation
- Linear integration workflow
- Code quality validation
- Development process enforcement

## Key Files to Work With
- `AGENT.md` - Workflow definitions
- `.git/` - Git repository management
- `.github/workflows/` - CI/CD pipelines
- `pyproject.toml` - Python project configuration
- `pre-commit` - Code quality hooks

## Technical Focus Areas
- **Git Workflow**: Branch management, commit strategies, merge workflows
- **Quality Gates**: Linting, type checking, testing, documentation
- **Automation**: Scripts, hooks, CI/CD integration
- **Linear Integration**: Issue tracking, status updates, branch naming
- **Code Standards**: Python/FastAPI best practices, commit messages

## 🔧 Git CLI Task Runner Workflow

### 📋 Pre-Task Checklist (MANDATORY)
1. ✅ **Check git status**: `git status` and `git branch` 
2. ✅ **Verify on main branch**: Must be on clean `main` before starting
3. ✅ **Get Linear branch name**: Use exact `gitBranchName` from Linear issue
4. ✅ **Create feature branch**: `git checkout -b feature/ken-##-description`
5. ✅ **Verify correct branch**: `git branch` to confirm feature branch active
6. ✅ **Make changes on feature branch ONLY**
7. ✅ **Code Quality Validation** (MANDATORY before commit):
   - Run `ruff check .` - All linting rules must pass
   - Run `mypy .` - Type checking must succeed
   - Run `pytest` - All tests must pass
   - Verify docstrings for new functions/classes
8. ✅ **Push feature branch**: `git push -u origin feature/ken-##-description`
9. ✅ **Create PR**: Use GitHub CLI with proper description
10. ✅ **Let GitHub-Linear integration handle status updates**

### ⚠️ NEVER DO THESE:
- ❌ Make changes directly on `main` branch
- ❌ Work without creating proper feature branch first
- ❌ Manually update Linear issue status (GitHub integration handles this)
- ❌ Skip branch verification steps
- ❌ Skip code quality validation
- ❌ Commit without running tests

## 🚀 Automated Commands

### Branch Management
```bash
# Check current status
git status
git branch

# Create feature branch
git checkout -b feature/ken-123-description

# Verify branch creation
git branch

# Push and set upstream
git push -u origin feature/ken-123-description
```

### Quality Validation
```bash
# Linting
ruff check .

# Type checking
mypy .

# Testing
pytest

# All quality checks
ruff check . && mypy . && pytest
```

### Commit and Push
```bash
# Stage changes
git add .

# Commit with conventional message
git commit -m "feat: add new feature"

# Push to remote
git push
```

### Pull Request Creation
```bash
# Create PR with GitHub CLI
gh pr create --title "feat: add new feature" --body "Description of changes"
```

## 🔍 Quality Gates

### Pre-Commit Validation
- **Ruff Linting**: Code style and quality
- **MyPy Type Checking**: Type safety validation
- **Pytest Testing**: Functionality verification
- **Documentation**: Docstring validation

### Pre-Push Validation
- **All quality gates must pass**
- **No merge conflicts**
- **Up-to-date with main**
- **Proper commit messages**

## 📝 Commit Message Standards

### Conventional Commits Format
```
type(scope): description

feat: add new feature
fix: resolve bug
docs: update documentation
style: code formatting
refactor: code restructuring
test: add tests
chore: maintenance tasks
```

### Examples
```
feat(api): add conversion endpoint
fix(conversion): resolve LaTeXML parsing error
docs(api): update endpoint documentation
test(services): add orchestrator tests
```

## 🎯 Linear Integration

### Branch Naming Convention
- **Format**: `feature/ken-123-description`
- **Linear Issue**: Must reference Linear issue number
- **Description**: Clear, concise feature description
- **Examples**:
  - `feature/ken-456-fastapi-setup`
  - `feature/ken-789-conversion-pipeline`
  - `feature/ken-101-testing-framework`

### Status Updates
- **Automatic**: GitHub-Linear integration handles status
- **Manual Updates**: Only when necessary
- **Progress Tracking**: Through commit messages and PRs

## 🔧 Development Workflow

### 1. Start New Feature
```bash
# Check status
git status
git branch

# Create feature branch
git checkout -b feature/ken-123-description

# Verify branch
git branch
```

### 2. Development
```bash
# Make changes
# Run quality checks
ruff check . && mypy . && pytest

# Stage and commit
git add .
git commit -m "feat: implement feature"

# Push changes
git push
```

### 3. Create Pull Request
```bash
# Create PR
gh pr create --title "feat: implement feature" --body "Detailed description"
```

### 4. Code Review and Merge
- **Review**: Code review process
- **Merge**: After approval
- **Cleanup**: Delete feature branch

## 🚨 Error Handling

### Common Issues
- **Merge conflicts**: Resolve before pushing
- **Quality gate failures**: Fix before committing
- **Branch issues**: Verify correct branch
- **Remote issues**: Check connection and permissions

### Recovery Commands
```bash
# Reset to last commit
git reset --hard HEAD

# Clean working directory
git clean -fd

# Rebase on main
git rebase origin/main

# Force push (use carefully)
git push --force-with-lease
```

## 🎯 Success Criteria

### Quality Standards
- **100% test coverage** for new code
- **Zero linting errors**
- **Type safety** maintained
- **Documentation** complete
- **Performance** optimized

### Workflow Compliance
- **Proper branch management**
- **Quality gates passing**
- **Conventional commits**
- **Linear integration**
- **Clean Git history**

## 📚 Resources

### Git Commands
- `git status` - Check repository status
- `git branch` - List branches
- `git checkout` - Switch branches
- `git add` - Stage changes
- `git commit` - Commit changes
- `git push` - Push to remote

### Quality Tools
- `ruff check .` - Linting
- `mypy .` - Type checking
- `pytest` - Testing
- `pre-commit` - Pre-commit hooks

### GitHub CLI
- `gh pr create` - Create pull request
- `gh pr list` - List pull requests
- `gh pr merge` - Merge pull request
- `gh repo view` - View repository

---

**Note**: This agent enforces the development workflow defined in AGENT.md and ensures consistent, high-quality development practices throughout the project.
