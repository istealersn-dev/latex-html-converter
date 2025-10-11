## 🚨 MANDATORY WORKFLOW - ALWAYS FOLLOW FIRST

**CRITICAL**: Always follow this workflow before making ANY code changes:

### 📋 Pre-Task Checklist (REQUIRED)
1. ✅ **Check git status**: `git status` and `git branch` 
2. ✅ **Verify on main branch**: Must be on clean `main` before starting
3. ✅ **Get Linear branch name**: Use exact `gitBranchName` from Linear issue
4. ✅ **Create feature branch**: `git checkout -b feature/ken-##-description`
5. ✅ **Verify correct branch**: `git branch` to confirm feature branch active
6. ✅ **Make changes on feature branch ONLY**
7. ✅ **Code Quality Validation** (MANDATORY before commit):
   - Run `pnpm lint` - All ESLint rules must pass
   - Run `pnpm typecheck` - TypeScript compilation must succeed
   - Run `pnpm test` - All tests must pass
   - Verify JSDoc documentation for new functions/classes
8. ✅ **Push feature branch**: `git push -u origin feature/ken-##-description`
9. ✅ **Create PR**: Use GitHub CLI with proper description
10. ✅ **Let GitHub-Linear integration handle status updates**

### ⚠️ NEVER DO THESE:
- ❌ Make changes directly on `main` branch
- ❌ Work without creating proper feature branch first
- ❌ Manually update Linear issue status (GitHub integration handles this)
- ❌ Skip branch verification steps