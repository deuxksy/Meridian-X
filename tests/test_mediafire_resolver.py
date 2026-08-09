from url_resolver.extractors.mediafire import MediafireResolver

def test_extract_mediafire_direct_url():
    sample_html = '''
    <html>
      <body>
        <a id="downloadButton" href="https://download1586.mediafire.com/xyz/test_file.rar" class="input popsok">Download (120MB)</a>
      </body>
    </html>
    '''
    resolver = MediafireResolver()
    direct_url = resolver.extract_direct_url(sample_html)
    assert direct_url == "https://download1586.mediafire.com/xyz/test_file.rar"

def test_extract_mediafire_direct_url_aria_label():
    sample_html = '''
    <html>
      <body>
        <a aria-label="Download file" href="https://download1586.mediafire.com/xyz/test_file_aria.rar">Download</a>
      </body>
    </html>
    '''
    resolver = MediafireResolver()
    direct_url = resolver.extract_direct_url(sample_html)
    assert direct_url == "https://download1586.mediafire.com/xyz/test_file_aria.rar"

def test_extract_mediafire_direct_url_not_found():
    sample_html = '''
    <html>
      <body>
        <p>No download button here</p>
      </body>
    </html>
    '''
    resolver = MediafireResolver()
    direct_url = resolver.extract_direct_url(sample_html)
    assert direct_url is None
