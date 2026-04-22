#!/bin/bash
# setup-project-board.sh - Complete project board setup script
# Usage: ./setup-project-board.sh <repo_owner> <repo_name> <project_name>

set -e

OWNER="${1:-rykunk21}"
REPO="${2:-forexdqn}"
PROJECT_NAME="${3:-TDD Board}"

echo "=== GitHub Project Board Setup ==="
echo "Owner: $OWNER"
echo "Repo: $REPO"
echo "Project: $PROJECT_NAME"
echo ""

# Get token from your existing script
TOKEN=$(bash ~/scripts/get-github-token.sh 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "Error: Could not get GitHub token from ~/scripts/get-github-token.sh"
    exit 1
fi

echo "✓ Token acquired"

# ============================================================================
# STEP 1: Create Project v2
# ============================================================================
echo ""
echo "Step 1: Creating Project v2..."

PROJECT_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/graphql \
  -d "{\"query\": \"mutation { createProjectV2(input: {ownerId: \\\"\\\\\\\"$OWNER\\\\\\\"\\\", title: \\\"\\\\\\\"$PROJECT_NAME\\\\\\\"\\\"}) { projectV2 { id number url } } }\"}")

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.data.createProjectV2.projectV2.id')
PROJECT_NUMBER=$(echo "$PROJECT_RESPONSE" | jq -r '.data.createProjectV2.projectV2.number')
PROJECT_URL=$(echo "$PROJECT_RESPONSE" | jq -r '.data.createProjectV2.projectV2.url')

if [ "$PROJECT_ID" = "null" ] || [ -z "$PROJECT_ID" ]; then
    echo "Error creating project. Response:"
    echo "$PROJECT_RESPONSE"
    exit 1
fi

echo "✓ Project created: $PROJECT_URL"
echo "  Project ID: $PROJECT_ID"
echo "  Project Number: $PROJECT_NUMBER"

# ============================================================================
# STEP 2: Get Repository ID
# ============================================================================
echo ""
echo "Step 2: Getting repository ID..."

REPO_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/graphql \
  -d "{\"query\": \"query { repository(owner: \\\"\\\\\\\"$OWNER\\\\\\\"\\\", name: \\\"\\\\\\\"$REPO\\\\\\\"\\\") { id } }\"}")

REPO_ID=$(echo "$REPO_RESPONSE" | jq -r '.data.repository.id')

echo "✓ Repository ID: $REPO_ID"

# ============================================================================
# STEP 3: Create Status Field with Options
# ============================================================================
echo ""
echo "Step 3: Creating Status field with TDD columns..."

FIELD_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  https://api.github.com/graphql \
  -d "{\"query\": \"mutation { createProjectV2Field(input: {projectId: \\\"\\\\\\\"$PROJECT_ID\\\\\\\"\\\", dataType: SINGLE_SELECT, name: \\\"\\\\\\\"Status\\\\\\\"\\\", singleSelectOptions: [{name: \\\"\\\\\\\"Backlog\\\\\\\"\\\", color: GRAY}, {name: \\\"\\\\\\\"Red\\\\\\\"\\\", color: RED}, {name: \\\"\\\\\\\"Green\\\\\\\"\\\", color: GREEN}, {name: \\\"\\\\\\\"Refactor\\\\\\\"\\\", color: PURPLE}, {name: \\\"\\\\\\\"Done\\\\\\\"\\\", color: GREEN}]}) { projectV2Field { id name options { id name } } } }\"}")

FIELD_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.id')

echo "✓ Status field created: $FIELD_ID"

# Extract option IDs dynamically
BACKLOG_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.options[] | select(.name == "Backlog") | .id')
RED_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.options[] | select(.name == "Red") | .id')
GREEN_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.options[] | select(.name == "Green") | .id')
REFACTOR_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.options[] | select(.name == "Refactor") | .id')
DONE_ID=$(echo "$FIELD_RESPONSE" | jq -r '.data.createProjectV2Field.projectV2Field.options[] | select(.name == "Done") | .id')

echo "  Option IDs extracted:"
echo "    Backlog: $BACKLOG_ID"
echo "    Red: $RED_ID"
echo "    Green: $GREEN_ID"
echo "    Refactor: $REFACTOR_ID"
echo "    Done: $DONE_ID"

# ============================================================================
# STEP 4: Create Labels in Repository
# ============================================================================
echo ""
echo "Step 4: Creating TDD labels in repository..."

for label in "backlog" "red" "green" "refactor"; do
    curl -s -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$OWNER/$REPO/labels" \
      -d "{\"name\": \"$label\", \"color\": \"$(case $label in
        backlog) echo '808080';;
        red) echo 'FF0000';;
        green) echo '00FF00';;
        refactor) echo '800080';;
      esac)\"}" > /dev/null
    echo "✓ Created label: $label"
done

# ============================================================================
# STEP 5: Generate Dynamic Workflow File
# ============================================================================
echo ""
echo "Step 5: Generating dynamic workflow..."

mkdir -p .github/workflows

cat > .github/workflows/sync-board.yml << 'WORKFLOW_EOF'
name: Sync TDD Labels to Project Board

on:
  issues:
    types: [labeled, unlabeled, opened, closed, reopened]

env:
  OWNER: ${{ github.repository_owner }}
  REPO: ${{ github.event.repository.name }}

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Query project structure
        id: query
        env:
          GH_TOKEN: ${{ secrets.PROJECT_PAT }}
        run: |
          # Find project by name and get its structure
          PROJECTS=$(gh api graphql -f query='
            query($owner: String!) {
              user(login: $owner) {
                projectsV2(first: 10) {
                  nodes { id number title }
                }
              }
            }
          ' -F owner="$OWNER" | jq -c '.data.user.projectsV2.nodes')
          
          echo "Found projects: $PROJECTS"
          
          # Get the first project (or filter by name)
          PROJECT_ID=$(echo "$PROJECTS" | jq -r '.[0].id')
          PROJECT_NUMBER=$(echo "$PROJECTS" | jq -r '.[0].number')
          
          echo "project_id=$PROJECT_ID" >> $GITHUB_OUTPUT
          echo "project_number=$PROJECT_NUMBER" >> $GITHUB_OUTPUT
          
          # Query the Status field and its options
          FIELDS=$(gh api graphql -f query='
            query($projectId: ID!) {
              node(id: $projectId) {
                ... on ProjectV2 {
                  fields(first: 20) {
                    nodes {
                      ... on ProjectV2SingleSelectField {
                        id
                        name
                        options { id name }
                      }
                    }
                  }
                }
              }
            }
          ' -F projectId="$PROJECT_ID" | jq -c '.data.node.fields.nodes[] | select(.name == "Status")')
          
          FIELD_ID=$(echo "$FIELDS" | jq -r '.id')
          echo "field_id=$FIELD_ID" >> $GITHUB_OUTPUT
          
          # Export option mapping as JSON
          OPTIONS=$(echo "$FIELDS" | jq -c '.options')
          echo "options=$OPTIONS" >> $GITHUB_OUTPUT
      
      - name: Update project item status
        env:
          GH_TOKEN: ${{ secrets.PROJECT_PAT }}
          PROJECT_ID: ${{ steps.query.outputs.project_id }}
          FIELD_ID: ${{ steps.query.outputs.field_id }}
          OPTIONS: ${{ steps.query.outputs.options }}
        run: |
          ISSUE_NUMBER="${{ github.event.issue.number }}"
          ISSUE_STATE="${{ github.event.issue.state }}"
          ISSUE_URL="${{ github.event.issue.html_url }}"
          
          echo "Processing issue #$ISSUE_NUMBER (state: $ISSUE_STATE)"
          
          # Get current labels
          LABELS=$(gh issue view "$ISSUE_NUMBER" --repo "$OWNER/$REPO" --json labels -q '[.labels[].name] | join(" ")')
          echo "Labels: $LABELS"
          
          # Determine target status
          if [ "$ISSUE_STATE" = "closed" ]; then
            TARGET_STATUS="Done"
          elif echo "$LABELS" | grep -q "refactor"; then
            TARGET_STATUS="Refactor"
          elif echo "$LABELS" | grep -q "green"; then
            TARGET_STATUS="Green"
          elif echo "$LABELS" | grep -q "red"; then
            TARGET_STATUS="Red"
          else
            TARGET_STATUS="Backlog"
          fi
          
          echo "Target status: $TARGET_STATUS"
          
          # Get option ID for target status
          OPTION_ID=$(echo "$OPTIONS" | jq -r ".[] | select(.name == \"$TARGET_STATUS\") | .id")
          
          if [ -z "$OPTION_ID" ] || [ "$OPTION_ID" = "null" ]; then
            echo "Error: Could not find option ID for $TARGET_STATUS"
            exit 1
          fi
          
          echo "Option ID: $OPTION_ID"
          
          # Add to project
          gh project item-add "${{ steps.query.outputs.project_number }}" --owner "$OWNER" --url "$ISSUE_URL" || true
          
          # Get item ID
          ITEM_ID=$(gh project item-list "${{ steps.query.outputs.project_number }}" --owner "$OWNER" --format json \
            | jq -r ".items[] | select(.content.number == $ISSUE_NUMBER) | .id")
          
          if [ -n "$ITEM_ID" ] && [ "$ITEM_ID" != "null" ]; then
            # Update status
            gh project item-edit \
              --project-id "$PROJECT_ID" \
              --id "$ITEM_ID" \
              --field-id "$FIELD_ID" \
              --single-select-option-id "$OPTION_ID"
            echo "✓ Updated issue #$ISSUE_NUMBER to $TARGET_STATUS"
          else
            echo "Could not find project item ID"
          fi
WORKFLOW_EOF

echo "✓ Workflow file created: .github/workflows/sync-board.yml"

# ============================================================================
# STEP 6: Generate Configuration File
# ============================================================================
echo ""
echo "Step 6: Generating project configuration..."

cat > .github/project-config.json << EOF
{
  "project": {
    "id": "$PROJECT_ID",
    "number": $PROJECT_NUMBER,
    "url": "$PROJECT_URL",
    "name": "$PROJECT_NAME"
  },
  "repo": {
    "owner": "$OWNER",
    "name": "$REPO",
    "id": "$REPO_ID"
  },
  "status_field": {
    "id": "$FIELD_ID",
    "name": "Status",
    "options": {
      "backlog": "$BACKLOG_ID",
      "red": "$RED_ID",
      "green": "$GREEN_ID",
      "refactor": "$REFACTOR_ID",
      "done": "$DONE_ID"
    }
  },
  "labels": ["backlog", "red", "green", "refactor"]
}
EOF

echo "✓ Configuration saved: .github/project-config.json"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "============================================================"
echo " Setup Complete!"
echo "============================================================"
echo ""
echo "Project Board: $PROJECT_URL"
echo ""
echo "Next Steps:"
echo "1. Create a Personal Access Token with 'project' scope at:"
echo "   https://github.com/settings/tokens"
echo ""
echo "2. Add the PAT as a repository secret:"
echo "   - Go to: https://github.com/$OWNER/$REPO/settings/secrets/actions"
echo "   - Name: PROJECT_PAT"
echo "   - Value: <your PAT>"
echo ""
echo "3. Commit and push the workflow:"
echo "   git add .github/workflows/sync-board.yml .github/project-config.json"
echo "   git commit -m 'Add dynamic project board sync workflow'"
echo "   git push"
echo ""
echo "4. Test by creating an issue and changing its label"
echo ""
echo "Configuration saved to .github/project-config.json"
echo "============================================================"
