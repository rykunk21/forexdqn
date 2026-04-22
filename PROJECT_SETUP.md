# Project Board Setup

Complete automation for creating a TDD Kanban board with GitHub Projects v2.

## What It Does

1. **Creates a Project v2** board with 5 columns: Backlog, Red, Green, Refactor, Done
2. **Creates labels** in your repository: `backlog`, `red`, `green`, `refactor`
3. **Generates a dynamic workflow** that queries your project structure at runtime
4. **Outputs configuration** for reference

## Usage

```bash
# Run the setup script
./setup-project-board.sh [owner] [repo] [project_name]

# Or with defaults (rykunk21/forexdqn "TDD Board")
./setup-project-board.sh
```

## Prerequisites

1. GitHub token with access to create projects and labels
2. `jq` installed for JSON parsing
3. Repository already exists on GitHub

## After Running

1. **Create a PAT** (Personal Access Token):
   - Go to https://github.com/settings/tokens
   - Select scopes: `repo`, `project`, `workflow`
   - Generate and copy the token

2. **Add the PAT to repo secrets**:
   - Go to `https://github.com/[owner]/[repo]/settings/secrets/actions`
   - Name: `PROJECT_PAT`
   - Value: your token

3. **Commit and push the workflow**:
   ```bash
   git add .github/
   git commit -m "Add project board automation"
   git push
   ```

4. **Test it**:
   ```bash
   # Create an issue
   gh issue create --title "Test issue" --label "backlog"
   
   # Move it by changing the label
   gh issue edit 1 --add-label "red" --remove-label "backlog"
   ```

## How the Workflow Works

Unlike static workflows, this one:

1. **Queries your project** at runtime using the GitHub CLI
2. **Finds the Status field** and its options dynamically
3. **Maps labels to columns** based on actual project structure
4. **Updates the item** to the correct column

This means if you rename columns or add new ones, the workflow adapts automatically (as long as the label-column mapping still makes sense).

## Files Created

- `.github/workflows/sync-board.yml` - Dynamic workflow
- `.github/project-config.json` - Reference configuration

## Column Mapping

| Label | Column | Meaning |
|-------|--------|---------|
| `backlog` | Backlog | Issue created, not yet started |
| `red` | Red | Write failing tests |
| `green` | Green | Make tests pass |
| `refactor` | Refactor | Clean up code |
| *closed* | Done | Issue complete |

## Troubleshooting

**"Could not find option ID"**
- Check that the Status field exists in your project settings
- Verify the column names match exactly (case-sensitive)

**"Authentication failed"**
- Ensure PROJECT_PAT is set in Actions secrets
- Token needs `project` scope

**"Project not found"**
- Make sure the script ran successfully and created the project
- Check the project-config.json for correct IDs
