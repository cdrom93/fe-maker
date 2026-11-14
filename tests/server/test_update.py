import io
import zipfile

import pytest

from fe_maker import update


def test_versions_in_order():
    order = ["0.1.0-prealpha.9", "0.1.0-prealpha.15", "0.1.0-prealpha.42", "0.1.0-alpha.1", "0.1.0-beta.2", "0.1.0",
             "0.2.0-prealpha.1", "0.43", "0.44", "0.100", "1.0"]
    assert sorted(order, key=update.parse_version) == order
    assert update.parse_version("v0.1.0-alpha.3") == update.parse_version("0.1.0-alpha.3")
    assert update.parse_version("not a version") == ()
    assert update.parse_version("v0.43") == update.parse_version("0.43.0")


def _release(tag, draft=False, name=None):
    name = name or f"fe-maker-{tag.removeprefix('v')}.zip"
    return {"tag_name": tag, "draft": draft, "html_url": f"https://github.com/{update.REPO}/releases/tag/{tag}",
            "assets": [{"name": name, "browser_download_url": f"{update.DOWNLOAD_PREFIX}{tag}/{name}"}]}


def test_newest_published_release_with_a_package():
    releases = [_release("v0.1.0-alpha.2", draft=True), _release("v0.1.0-alpha.1"), _release("v0.1.0-prealpha.20"),
                _release("v0.1.0-alpha.3", name="notes.txt")]
    found = update.newest(releases, "0.1.0-prealpha.15")
    assert found["version"] == "0.1.0-alpha.1" and found["url"].endswith("/fe-maker-0.1.0-alpha.1.zip")
    assert update.newest(releases, "0.1.0-alpha.1") is None
    elsewhere = _release("v9.0.0")
    elsewhere["assets"][0]["browser_download_url"] = "https://example.com/fe-maker-9.0.0.zip"
    assert update.newest([elsewhere], "0.1.0") is None


def _package(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buffer.getvalue()


def _install(root):
    (root / "server/fe_maker").mkdir(parents=True)
    (root / "server/fe_maker/__init__.py").write_text("old")
    (root / "server/fe_maker/gone.py").write_text("old")
    (root / "ui/dist").mkdir(parents=True)
    (root / "ui/dist/index.html").write_text("old")
    (root / "lancer-fe-maker.bat").write_text("old")
    (root / ".venv").mkdir()
    (root / ".venv/keep").write_text("venv")


NEW = {"fe-maker/server/fe_maker/__init__.py": b"new", "fe-maker/ui/dist/index.html": b"new",
       "fe-maker/lancer-fe-maker.bat": b"new", "fe-maker/README.md": b"new"}


def test_a_package_replaces_fe_makers_files_only(tmp_path):
    root = tmp_path / "fe-maker"
    _install(root)
    assert update.installable(root)
    update.unpack(_package(NEW), tmp_path / "new")
    update.replace(root, tmp_path / "new")
    assert (root / "server/fe_maker/__init__.py").read_text() == "new"
    assert not (root / "server/fe_maker/gone.py").exists()   # a module the new version dropped
    assert (root / "lancer-fe-maker.bat").read_text() == "new" and (root / "README.md").read_text() == "new"
    assert (root / ".venv/keep").read_text() == "venv"
    assert (root / ".update-old/server/fe_maker/gone.py").exists()


def test_a_bad_package_is_refused(tmp_path):
    for files in ({"other/server/fe_maker/__init__.py": b"x"}, {"fe-maker/../evil.py": b"x", **NEW},
                  {"fe-maker/README.md": b"x"}):
        with pytest.raises(update.UpdateError):
            update.unpack(_package(files), tmp_path / "new")
    with pytest.raises(update.UpdateError):
        update.unpack(b"not a zip", tmp_path / "new")


def test_a_checkout_does_not_update_itself(tmp_path):
    root = tmp_path / "fe-maker"
    _install(root)
    (root / ".git").mkdir()
    assert not update.installable(root)
    with pytest.raises(update.UpdateError):
        update.install({"url": update.DOWNLOAD_PREFIX + "x.zip"}, root)
