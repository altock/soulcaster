import ast
import json
import shlex
from pathlib import Path


def _extract_agent_script(source_path: Path) -> str:
    module = ast.parse(source_path.read_text())
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "AGENT_SCRIPT":
                    return ast.literal_eval(node.value)
    raise AssertionError("AGENT_SCRIPT not found in sandbox runner")


def test_embedded_agent_script_compiles():
    script_path = Path(__file__).resolve().parents[1] / "agent_runner" / "sandbox.py"
    agent_script = _extract_agent_script(script_path)
    compile(agent_script, "agent_script.py", "exec")


class TestPrUrlParsing:
    """Test PR URL parsing used in REST API update."""

    def test_parse_standard_pr_url(self):
        """Parse a standard GitHub PR URL."""
        pr_url = "https://github.com/owner/repo/pull/123"
        pr_parts = pr_url.rstrip("/").split("/")
        pr_number = pr_parts[-1]
        pr_repo = pr_parts[-3]
        pr_owner = pr_parts[-4]

        assert pr_number == "123"
        assert pr_repo == "repo"
        assert pr_owner == "owner"

    def test_parse_pr_url_with_trailing_slash(self):
        """Parse PR URL with trailing slash."""
        pr_url = "https://github.com/altock/soulcaster/pull/141/"
        pr_parts = pr_url.rstrip("/").split("/")
        pr_number = pr_parts[-1]
        pr_repo = pr_parts[-3]
        pr_owner = pr_parts[-4]

        assert pr_number == "141"
        assert pr_repo == "soulcaster"
        assert pr_owner == "altock"

    def test_parse_pr_url_with_hyphenated_names(self):
        """Parse PR URL with hyphens in owner/repo names."""
        pr_url = "https://github.com/my-org/my-repo-name/pull/42"
        pr_parts = pr_url.rstrip("/").split("/")
        pr_number = pr_parts[-1]
        pr_repo = pr_parts[-3]
        pr_owner = pr_parts[-4]

        assert pr_number == "42"
        assert pr_repo == "my-repo-name"
        assert pr_owner == "my-org"


class TestRestApiCommandConstruction:
    """Test REST API command construction for PR updates."""

    def test_api_url_construction(self):
        """Verify API URL is correctly constructed."""
        pr_owner = "altock"
        pr_repo = "soulcaster"
        pr_number = "141"

        api_url = f"https://api.github.com/repos/{pr_owner}/{pr_repo}/pulls/{pr_number}"
        assert api_url == "https://api.github.com/repos/altock/soulcaster/pulls/141"

    def test_payload_json_escaping(self):
        """Verify PR body with special chars is properly JSON-escaped."""
        body = 'Test with "quotes" and\nnewlines'
        payload = json.dumps({"body": body})

        # Verify it's valid JSON
        parsed = json.loads(payload)
        assert parsed["body"] == body

    def test_shlex_quote_api_url(self):
        """Verify shlex.quote handles API URLs correctly."""
        api_url = "https://api.github.com/repos/owner/repo/pulls/123"
        quoted = shlex.quote(api_url)

        # URL is safe for shell (no special chars that need quoting)
        assert quoted == "https://api.github.com/repos/owner/repo/pulls/123"

    def test_shlex_quote_url_with_special_chars(self):
        """Verify shlex.quote adds quotes for URLs with shell special chars."""
        # URL with query params (& is shell special char)
        api_url = "https://api.github.com/repos/owner/repo?foo=bar&baz=1"
        quoted = shlex.quote(api_url)
        assert quoted == "'https://api.github.com/repos/owner/repo?foo=bar&baz=1'"

    def test_curl_command_structure(self):
        """Verify curl command has correct structure."""
        api_url = "https://api.github.com/repos/owner/repo/pulls/123"
        payload_file = "/tmp/pr_update_payload.json"

        cmd = (
            f'curl -s -X PATCH {shlex.quote(api_url)} '
            f'-H "Authorization: Bearer $GITHUB_TOKEN" '
            f'-H "Accept: application/vnd.github+json" '
            f'-H "X-GitHub-Api-Version: 2022-11-28" '
            f'-d @{shlex.quote(payload_file)}'
        )

        assert "PATCH" in cmd
        assert "Bearer $GITHUB_TOKEN" in cmd
        assert "application/vnd.github+json" in cmd
        assert "-d @" in cmd


class TestGeminiSdkUsage:
    """Test Google Gen AI SDK usage in AGENT_SCRIPT."""

    def test_uses_new_google_genai_sdk(self):
        """Verify AGENT_SCRIPT uses new google-genai SDK, not deprecated google-generativeai."""
        script_path = Path(__file__).resolve().parents[1] / "agent_runner" / "sandbox.py"
        agent_script = _extract_agent_script(script_path)

        # Should use new SDK import
        assert "from google import genai" in agent_script
        assert "genai.Client" in agent_script

        # Should NOT use deprecated SDK
        assert "google.generativeai" not in agent_script
        assert "genai.configure" not in agent_script
        assert "GenerativeModel" not in agent_script

    def test_uses_gemini_3_flash_model(self):
        """Verify AGENT_SCRIPT uses gemini-3-flash-preview model."""
        script_path = Path(__file__).resolve().parents[1] / "agent_runner" / "sandbox.py"
        agent_script = _extract_agent_script(script_path)

        assert 'model="gemini-3-flash-preview"' in agent_script

    def test_uses_client_models_generate_content(self):
        """Verify AGENT_SCRIPT uses client.models.generate_content API."""
        script_path = Path(__file__).resolve().parents[1] / "agent_runner" / "sandbox.py"
        agent_script = _extract_agent_script(script_path)

        assert "client.models.generate_content" in agent_script


class TestMarkdownWrapperStripping:
    """Test markdown code block wrapper removal."""

    def test_strip_markdown_wrapper(self):
        """
        Remove leading and trailing Markdown code-fence wrappers (``` or ```markdown) so only the inner content remains.
        """
        text = "```markdown\n## Summary\nThis is content\n```"

        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        assert text == "## Summary\nThis is content"

    def test_strip_plain_code_block_wrapper(self):
        """Strip plain ``` wrapper."""
        text = "```\n## Summary\nThis is content\n```"

        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        assert text == "## Summary\nThis is content"

    def test_no_wrapper_unchanged(self):
        """Content without wrapper stays unchanged."""
        text = "## Summary\nThis is content"
        original = text

        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        assert text == original

    def test_strip_only_ending_wrapper(self):
        """Handle case where only ending ``` exists."""
        text = "## Summary\nThis is content\n```"

        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        assert text == "## Summary\nThis is content"
