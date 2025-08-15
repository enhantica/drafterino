# Drafterino

Turn labeled pull requests into draft releases and version bumps.

Drafterino is a lightweight GitHub Action that automatically generates draft 
release notes and determines the next version number — all based on merged 
pull requests and their labels. It:

- Detects merged pull requests since the last release
- Groups them into release note sections based on labels
- Computes the next version using SemVer (`major.minor.patch`) with optional `.postN` suffix
- Creates or updates a draft GitHub release
- Publishes the draft via [`softprops/action-gh-release`](https://github.com/softprops/action-gh-release)

## Example Configuration

```yaml
name: Update release draft

on:
  push:
    branches:
      - main
      - master

jobs:
  draft-release-notes:
    permissions:
      contents: write

    runs-on: ubuntu-latest

    steps:
      - name: Drafts the next release notes
        uses: enhantica/drafterino@v1

        with:
          config: |
            title: 'draft-release $COMPUTED_VERSION'
            tag: 'v$COMPUTED_VERSION'
            note-template: '- $PR_TITLE (#$PR_NUMBER)'

            default-bump: post

            major-bump-labels: ['significant']
            minor-bump-labels: ['enhancement']
            patch-bump-labels: ['bug', 'maintenance']
            post-bump-labels: ['documentation']

            release-notes:
              - title: 'Added'
                labels: ['significant', 'enhancement']
              - title: 'Fixed'
                labels: ['bug']
              - title: 'Changed'
                labels: ['maintenance', 'documentation']

        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```
