"""TransmissionClient 도메인 로직 회귀 테스트.

transmission-rpc 마이그레이션 후에도 순수 함수 동작이 보존되는지 검증.
RPC 호출 / 네트워크 / Client 생성은 포함하지 않는다.
"""
from types import SimpleNamespace

from meridian_x.transmission import TransmissionClient


class TestExtractLabelsFromName:
    """_extract_labels_from_name: JAV 메이커 / West 스튜디오+배우 추출."""

    def test_jav_maker_code(self):
        # SNOS-125 → ['snos']
        assert TransmissionClient._extract_labels_from_name("SNOS-125 타이틀") == ["snos"]

    def test_jav_fc2(self):
        # FC2-PPV-4895410 → ['fc2']
        assert TransmissionClient._extract_labels_from_name("FC2-PPV-4895410") == ["fc2"]

    def test_west_studio_and_actress(self):
        # Vixen.16.09.06.Lily.Love.XXX → ['vixen', 'lily love']
        result = TransmissionClient._extract_labels_from_name(
            "Vixen.16.09.06.Lily.Love.XXX.1080p"
        )
        assert result == ["vixen", "lily love"]

    def test_west_studio_only_when_no_actress(self):
        # 배우명 추출 불가 시 스튜디오만
        result = TransmissionClient._extract_labels_from_name(
            "Brazzers.20.10.01.XXX"
        )
        assert result == ["brazzers"]

    def test_no_match_returns_empty(self):
        assert TransmissionClient._extract_labels_from_name("random title no pattern") == []


def _file(name, size):
    """테스트용 File mock (transmission-rpc File 객체의 name/size 호환)."""
    return SimpleNamespace(name=name, size=size)


def _client():
    """__init__ 없이 인스턴스 생성 (RPC 연결 회피)."""
    return TransmissionClient.__new__(TransmissionClient)


class TestFilterFiles:
    """_filter_files: 확장자/키워드/크기 기반 파일 제외 인덱스 반환."""

    FILTERS = {
        "exclude_extensions": [".html", ".url", ".txt"],
        "exclude_keywords": ["sample", "trailer"],
        "min_file_size_mb": 100,
    }

    def test_exclude_by_extension(self):
        files = [_file("ad.html", 1000)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_exclude_by_keyword(self):
        files = [_file("movie sample.mp4", 500_000_000)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_exclude_by_min_size(self):
        # 50MB < 100MB min
        files = [_file("small.mp4", 50 * 1024 * 1024)]
        assert _client()._filter_files(files, self.FILTERS) == [0]

    def test_keep_valid_file(self):
        files = [_file("big.mp4", 500 * 1024 * 1024)]
        assert _client()._filter_files(files, self.FILTERS) == []

    def test_mixed_files_correct_indices(self):
        files = [
            _file("ad.html", 1000),               # 0: ext
            _file("main.mp4", 500_000_000),        # 1: keep
            _file("trailer.mp4", 200_000_000),     # 2: keyword
            _file("small.mp4", 10_000_000),        # 3: size
        ]
        assert _client()._filter_files(files, self.FILTERS) == [0, 2, 3]

    def test_empty_filters_excludes_nothing(self):
        files = [_file("ad.html", 1000), _file("main.mp4", 500_000_000)]
        assert _client()._filter_files(files, {}) == []
