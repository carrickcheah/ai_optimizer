# Claude Code Configuration

## Auto-Approval Rules
- **Auto-approve all read-only and testing commands** including:
  - `curl -s` (API testing)
  - `echo` (output display)
  - `uv run` (script execution)
  - `source .venv/bin/activate` (environment activation)
  - `ls`, `cat`, `head`, `tail` (file reading)
  - `git status`, `git log`, `git diff` (git inspection)
  - `ps`, `top`, `df` (system monitoring)
  - Any command that only reads/tests without modifying files

## Commands that require approval:
- File editing (`Edit`, `Write`, `MultiEdit`)
- File creation/deletion
- `git commit`, `git push` (version control changes)
- Package installation (`npm install`, `pip install`)

## Testing Protocol
- Use `uv run` or `source .venv/bin/activate` in `/Users/carrickcheah/Project/ai_optimizer/backend`
- Testing commands are always approved automatically
- No permission needed for read-only operations