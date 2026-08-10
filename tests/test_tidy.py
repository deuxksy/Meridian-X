"""tidy 도메인 로직 회귀 테스트.

flatten 셸 스크립트는 SSH 없이 로컬 bash로 실행해 동작을 검증한다.
회귀 대상 버그 (2026-07-29 프로덕션 데이터 손실):
- 다중 영상 폴더에서 첫 파일만 이동 후 rm -rf로 나머지 삭제
- exclude 목록이 레거시 키(artist_folders/studio_folders)만 읽어 Actors/스튜디오 폴더 미보호
- _ssh dry_run 미적용으로 --dry-run도 실제 삭제 실행
"""
import subprocess

import pytest

from meridian_x import tidy


def _run_script(tmp_path, script):
    """빌더가 생성한 셸 스크립트를 로컬 bash로 실행."""
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=30
    )


def _make_video(directory, name):
    f = directory / name
    f.write_text("x")
    return f


def _require_case_sensitive_fs(tmp_path):
    """case-dup 폴더 생성이 가능한 파일시스템에서만 실행 (macOS APFS는 불가)."""
    probe = tmp_path / "CaseProbe"
    probe.mkdir()
    try:
        (tmp_path / "caseprobe").mkdir()
    except FileExistsError:
        pytest.skip("파일시스템이 대소문자를 구분하지 않음 (case-dup은 Linux 전용)")


class TestComputeExcludeFolders:
    """_compute_exclude_folders: flatten 제외 폴더 산출."""

    def test_dict_structure_includes_actors_artists_studios(self):
        config = {
            "classify": {
                "artists": {"WEST": ["Dakota Doll"], "JPN": ["MINAMO"]},
                "studios": {"WEST": {"Vixen": ["vixen", "tushy"]}, "JPN": {}},
            },
            "genres": {"Anime": {"keywords": [], "prefixes": []}},
        }
        exclude = set(tidy._compute_exclude_folders(config))
        assert {
            "Actors", "JPN", "FC2", "West",
            "Dakota Doll", "MINAMO", "Vixen", "Anime",
        } <= exclude

    def test_legacy_keys_supported(self):
        config = {
            "classify": {
                "artist_folders": ["Some Actor"],
                "studio_folders": ["SomeStudio"],
            },
            "genres": {},
        }
        exclude = set(tidy._compute_exclude_folders(config))
        assert {"Actors", "Some Actor", "SomeStudio"} <= exclude


class TestBuildExcludeArgs:
    """_build_exclude_args: find 제외 인자 생성 (대소문자 무시)."""

    def test_uses_iname_for_case_insensitive_match(self):
        args = tidy._build_exclude_args(["Actors", "Vixen"])
        assert args.count("-not -iname") == 2
        assert '-iname "Actors"' in args
        assert '-iname "Vixen"' in args

    def test_empty_returns_empty_string(self):
        assert tidy._build_exclude_args([]) == ""
        assert tidy._build_exclude_args(None) == ""


class TestFlattenScript:
    """_build_flatten_script: 로컬 bash 실행으로 동작 검증."""

    def test_single_video_folder_flattened(self, tmp_path):
        d = tmp_path / "SONE-446"
        d.mkdir()
        _make_video(d, "SONE-446.mp4")
        r = _run_script(tmp_path, tidy._build_flatten_script(str(tmp_path)))
        assert (tmp_path / "SONE-446.mp4").exists()
        assert not d.exists()
        assert "FLATTEN SONE-446" in r.stdout

    def test_multi_video_folder_skipped_untouched(self, tmp_path):
        """회귀: 다중 영상 폴더의 파일이 삭제되면 안 된다."""
        d = tmp_path / "MultiPart"
        d.mkdir()
        files = [_make_video(d, f"part{i}.mp4") for i in range(3)]
        r = _run_script(tmp_path, tidy._build_flatten_script(str(tmp_path)))
        assert d.exists()
        assert all(f.exists() for f in files)
        assert "SKIP_MULTIVIDEO MultiPart" in r.stdout

    def test_case_duplicate_folder_merged_to_root(self, tmp_path):
        _require_case_sensitive_fs(tmp_path)
        sibling = tmp_path / "somemovie"
        sibling.mkdir()
        dup = tmp_path / "SomeMovie"
        dup.mkdir()
        _make_video(dup, "a.mp4")
        _make_video(dup, "b.mp4")
        r = _run_script(tmp_path, tidy._build_flatten_script(str(tmp_path)))
        assert (tmp_path / "a.mp4").exists()
        assert (tmp_path / "b.mp4").exists()
        assert not dup.exists()
        assert "FLATTEN_DUP SomeMovie" in r.stdout

    def test_dup_merge_name_collision_keeps_folder(self, tmp_path):
        """병합 대상 이름이 루트에 이미 있으면 원본 보존 (삭제 금지)."""
        _require_case_sensitive_fs(tmp_path)
        (tmp_path / "b.mp4").write_text("root")
        sibling = tmp_path / "movie"
        sibling.mkdir()
        dup = tmp_path / "Movie"
        dup.mkdir()
        _make_video(dup, "b.mp4")
        r = _run_script(tmp_path, tidy._build_flatten_script(str(tmp_path)))
        assert (tmp_path / "b.mp4").read_text() == "root"
        assert dup.exists()
        assert (dup / "b.mp4").exists()

    def test_dup_detection_counts_case_variants(self):
        """중복 감지 패턴: 자기 자신 포함 2개 이상 매칭 시에만 중복 ($$ PID 버그 회귀).

        grep -F 모드에서는 ^/$가 리터럴이라 앵커 대신 -x(전체 라인 매칭)를 써야 한다.
        """
        for build in (tidy._build_flatten_script, tidy._build_flatten_probe_script):
            assert 'grep -icFx "$folder_name_lower"' in build("/nonexistent")
        r = subprocess.run(
            ["bash", "-c", 'printf "SomeMovie\\nsomemovie\\n" | grep -icFx "somemovie"'],
            capture_output=True, text=True,
        )
        assert r.stdout.strip() == "2"
        r = subprocess.run(
            ["bash", "-c", 'printf "SomeMovie\\n" | grep -icFx "somemovie"'],
            capture_output=True, text=True,
        )
        assert r.stdout.strip() == "1"
        # -F 유지: 폴더명의 '.' 등 regex 메타 문자가 와일드카드로 오작동하지 않아야 함
        r = subprocess.run(
            ["bash", "-c", 'printf "someXmovie\\nsome.movie\\n" | grep -icFx "some.movie"'],
            capture_output=True, text=True,
        )
        assert r.stdout.strip() == "1"

    def test_excluded_folder_untouched(self, tmp_path):
        """회귀: Actors 같은 분류 폴더 트리는 flatten 대상이 아니다."""
        d = tmp_path / "Actors"
        sub = d / "Dakota Doll"
        sub.mkdir(parents=True)
        _make_video(sub, "x.mp4")
        _run_script(tmp_path, tidy._build_flatten_script(
            str(tmp_path), tidy._build_exclude_args(["Actors"])
        ))
        assert (sub / "x.mp4").exists()

    def test_excluded_folder_case_variant_untouched(self, tmp_path):
        """exclude 매칭은 대소문자 무시 (actors == Actors)."""
        d = tmp_path / "actors"
        d.mkdir()
        _make_video(d, "x.mp4")
        _run_script(tmp_path, tidy._build_flatten_script(
            str(tmp_path), tidy._build_exclude_args(["Actors"])
        ))
        assert (d / "x.mp4").exists()


class TestFlattenProbeScript:
    """_build_flatten_probe_script: dry-run 읽기 전용 후보 집계."""

    def test_probe_reports_candidates_without_mutation(self, tmp_path):
        single = tmp_path / "One"
        single.mkdir()
        _make_video(single, "a.mp4")
        multi = tmp_path / "Multi"
        multi.mkdir()
        for i in range(2):
            _make_video(multi, f"m{i}.mp4")
        r = _run_script(
            tmp_path, tidy._build_flatten_probe_script(str(tmp_path))
        )
        assert "CANDIDATE One" in r.stdout
        assert "SKIP_MULTIVIDEO Multi" in r.stdout
        assert (single / "a.mp4").exists()
        assert multi.exists()
        assert len(list(multi.iterdir())) == 2


class TestSshDryRun:
    """_ssh dry_run: 명령을 실행하지 않아야 한다."""

    def test_dry_run_does_not_execute(self, monkeypatch):
        calls = []

        def fake_run(*args, **kwargs):
            calls.append(args)
            raise AssertionError("dry-run인데 SSH 명령이 실행됨")

        monkeypatch.setattr(tidy.subprocess, "run", fake_run)
        ok, output = tidy._ssh(
            {"host": "h", "user": "u", "ssh_key": "k", "path": "/p"},
            "rm -rf something",
            dry_run=True,
        )
        assert ok
        assert output == ""
        assert calls == []


class TestRunDryRun:
    """run(dry_run=True): 외부 상태 변경이 없어야 한다."""

    def _stub_pipeline(self, monkeypatch):
        import meridian_x.core
        import meridian_x.jellyfin
        config = {
            "remote": {"host": "h", "user": "u", "ssh_key": "k", "path": "/p"},
            "jellyfin": {"url": "http://x", "api_key": "k"},
            "classify": {},
            "transmission": {},
        }
        monkeypatch.setattr(meridian_x.core, "load_config", lambda: config)
        monkeypatch.setattr(tidy, "delete_junk_jellyfin", lambda *a, **k: 0)
        monkeypatch.setattr(tidy, "delete_junk_remote", lambda *a, **k: 0)
        monkeypatch.setattr(tidy, "flatten_folders", lambda *a, **k: 0)
        monkeypatch.setattr(tidy, "clean_filenames", lambda *a, **k: 0)
        calls = []
        monkeypatch.setattr(
            meridian_x.jellyfin, "refresh_from_config", lambda c: calls.append(c)
        )
        return calls

    def test_dry_run_skips_jellyfin_refresh(self, monkeypatch):
        calls = self._stub_pipeline(monkeypatch)
        tidy.run(dry_run=True, refresh=True)
        assert calls == []

    def test_real_run_triggers_jellyfin_refresh(self, monkeypatch):
        calls = self._stub_pipeline(monkeypatch)
        tidy.run(dry_run=False, refresh=True)
        assert len(calls) == 1


def test_clean_prefixes_includes_4k688():
    from pathlib import Path

    from meridian_x.core import load_config

    config_path = Path("config/settings.json")
    if not config_path.exists():
        config_path = Path("config/settings.json.example")
    config = load_config(config_path)
    prefixes = config.get("classify", {}).get("clean_prefixes", [])
    assert "hhd800.com@" in prefixes
    assert "4k688.com@" in prefixes


