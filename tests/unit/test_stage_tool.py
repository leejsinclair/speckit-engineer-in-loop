"""The release tag check in tools/stage.py."""

from tools.stage import _version, check_release_tag


def test_a_tag_matching_both_manifests_is_accepted() -> None:
    assert check_release_tag(f"v{_version()}") is None


def test_a_tag_naming_another_version_is_refused_with_the_reason() -> None:
    reason = check_release_tag("v99.0.0")
    assert reason and "preset.yml says" in reason and "extension.yml says" in reason
