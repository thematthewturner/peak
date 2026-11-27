from peak.sanitize import sanitize_html

PNG = "data:image/png;base64,iVBORw0KGgo="


def test_inline_raster_kept_svg_and_remote_dropped():
    assert PNG in sanitize_html(f'<img src="{PNG}" alt="a">')
    assert "src=" not in sanitize_html('<img src="data:image/svg+xml;base64,PHN2Zz4=">')
    assert "src=" not in sanitize_html('<img src="https://evil.example/x.png">')
    assert "src=" not in sanitize_html('<img src="javascript:alert(1)">')
