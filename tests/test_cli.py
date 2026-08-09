import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from typer.testing import CliRunner

from url_resolver.cli import app
from url_resolver.models import DownloadMetadata

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "url-resolver" in result.output.lower() or "usage" in result.output.lower() or "direct link" in result.output.lower()


@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_parse_command_extract_only(mock_mf_extract, mock_ouo_resolve, mock_httpx_get):
    # Mock post page fetch
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '''
    <html><body>
      <div class="entry-content">
        <a href="https://ouo.io/hHzh1N">Download</a>
      </div>
    </body></html>
    '''
    # Mock mediafire page fetch
    mock_mf_resp = MagicMock()
    mock_mf_resp.status_code = 200
    mock_mf_resp.text = "<html><body>Mediafire Page</body></html>"

    mock_httpx_get.side_effect = [mock_post_resp, mock_mf_resp]
    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar/file"
    mock_mf_extract.return_value = "https://download1586.mediafire.com/xyz/sample.rar"

    result = runner.invoke(app, ["parse", "https://misskon.com/123", "--extract-only"])
    assert result.exit_code == 0
    assert "https://download1586.mediafire.com/xyz/sample.rar" in result.output


@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_parse_command_json_output(mock_mf_extract, mock_ouo_resolve, mock_httpx_get):
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '<a href="https://ouo.io/hHzh1N">Download</a>'
    mock_httpx_get.return_value = mock_post_resp

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    result = runner.invoke(app, ["parse", "https://misskon.com/123", "--extract-only", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["direct_url"] == "https://download.mediafire.com/direct.rar"


@patch("url_resolver.cli.Aria2Dispatcher")
@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_parse_command_dispatch_aria2(mock_mf_extract, mock_ouo_resolve, mock_httpx_get, mock_dispatcher_cls):
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '<a href="https://ouo.io/hHzh1N">Download</a>'
    mock_httpx_get.return_value = mock_post_resp

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    mock_dispatcher_inst = MagicMock()
    mock_dispatcher_inst.dispatch.return_value = "gid_abc123"
    mock_dispatcher_cls.return_value = mock_dispatcher_inst

    result = runner.invoke(app, ["parse", "https://misskon.com/123"])
    assert result.exit_code == 0
    assert "gid_abc123" in result.output
    mock_dispatcher_inst.dispatch.assert_called_once()


@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_parse_command_output_file(mock_mf_extract, mock_ouo_resolve, mock_httpx_get, tmp_path):
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '<a href="https://ouo.io/hHzh1N">Download</a>'
    mock_httpx_get.return_value = mock_post_resp

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    out_file = tmp_path / "urls.txt"
    result = runner.invoke(app, ["parse", "https://misskon.com/123", "--extract-only", "-o", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "https://download.mediafire.com/direct.rar" in content


@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_crawl_command(mock_mf_extract, mock_ouo_resolve, mock_httpx_get):
    cat_html = '''
    <html><body>
      <div class="post-listing">
        <h2 class="post-box-title"><a href="https://misskon.com/post-1/">Post 1</a></h2>
      </div>
      <div class="pagination">
        <a href="https://misskon.com/tag/test/page/2/" class="page">2</a>
      </div>
    </body></html>
    '''
    post_html = '<a href="https://ouo.io/hHzh1N">Download</a>'

    mock_cat_resp = MagicMock()
    mock_cat_resp.status_code = 200
    mock_cat_resp.text = cat_html

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = post_html

    mock_httpx_get.side_effect = [mock_cat_resp, mock_post_resp, mock_cat_resp]

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    result = runner.invoke(app, ["crawl", "https://misskon.com/tag/test/", "--pages", "1", "--limit", "1", "--extract-only"])
    assert result.exit_code == 0
    assert "https://download.mediafire.com/direct.rar" in result.output


@patch("url_resolver.cli.pyperclip.paste")
@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_clip_command(mock_mf_extract, mock_ouo_resolve, mock_httpx_get, mock_clip_paste):
    mock_clip_paste.return_value = "https://misskon.com/123"

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '<a href="https://ouo.io/hHzh1N">Download</a>'
    mock_httpx_get.return_value = mock_post_resp

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    result = runner.invoke(app, ["clip", "--extract-only"])
    assert result.exit_code == 0
    assert "https://download.mediafire.com/direct.rar" in result.output


@patch("url_resolver.cli.httpx.get")
@patch("url_resolver.cli.OuoBypasser.resolve", new_callable=AsyncMock)
@patch("url_resolver.cli.MediafireResolver.extract_direct_url")
def test_batch_command(mock_mf_extract, mock_ouo_resolve, mock_httpx_get, tmp_path):
    batch_file = tmp_path / "urls.txt"
    batch_file.write_text("https://misskon.com/post1/\n# comment\nhttps://misskon.com/post2/\n")

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = '<a href="https://ouo.io/hHzh1N">Download</a>'
    mock_httpx_get.return_value = mock_post_resp

    mock_ouo_resolve.return_value = "https://www.mediafire.com/file/sample/file.rar"
    mock_mf_extract.return_value = "https://download.mediafire.com/direct.rar"

    result = runner.invoke(app, ["batch", str(batch_file), "--extract-only"])
    assert result.exit_code == 0
    assert "https://download.mediafire.com/direct.rar" in result.output
