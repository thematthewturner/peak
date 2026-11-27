from peak.sanitize import sanitize_html

PNG = "data:image/png;base64,iVBORw0KGgo="


def test_inline_raster_kept_svg_and_remote_dropped():
    assert PNG in sanitize_html(f'<img src="{PNG}" alt="a">')
    assert "src=" not in sanitize_html('<img src="data:image/svg+xml;base64,PHN2Zz4=">')
    assert "src=" not in sanitize_html('<img src="https://evil.example/x.png">')
    assert "src=" not in sanitize_html('<img src="javascript:alert(1)">')


SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100" role="img" '
       'aria-label="Bar chart" onload="alert(1)"><defs><clipPath id="c0"><rect width="200" height="100"/></clipPath></defs>'
       '<g clip-path="url(#c0)" style="fill:#333;stroke-width:2"><path d="M0 0L10 10" stroke="red" onclick="x()"/>'
       '<text x="5" y="5" font-size="12">Q1</text></g></svg>')


def test_svg_chart_is_kept_with_shapes_text_and_accessibility_label():
    out = sanitize_html(SVG)
    for needle in ("<svg", 'aria-label="Bar chart"', "<path", 'd="M0 0L10 10"', "<text", "Q1", "<rect"):
        assert needle in out, needle
    assert out.count("<svg") == 1 and out.count("</svg>") == 1


def test_svg_strips_scripts_handlers_and_external_references():
    bad = ('<svg><script>alert(1)</script><g onload="x()"><a href="javascript:1"><circle fill="url(http://evil/x)" r="1"/></a>'
           '<image href="http://evil/x.png"/><foreignObject><iframe src="x"></iframe></foreignObject>'
           '<use href="http://evil/s.svg#a"/><animate attributeName="x"/><set to="1"/>'
           '<rect style="fill:red;background:url(http://evil/y)" width="1" height="1"/></g></svg>')
    out = sanitize_html(bad).lower()
    for needle in ("script", "onload", "javascript", "evil", "<image", "<use", "<animate", "<set", "foreignobject", "iframe"):
        assert needle not in out, needle


def test_svg_ids_are_prefixed_and_fragment_refs_follow():
    out = sanitize_html(SVG)
    assert 'id="pk-c0"' in out and "url(#pk-c0)" in out and 'id="c0"' not in out


def test_svg_style_keeps_only_safe_properties():
    out = sanitize_html('<svg><rect style="fill:#333;position:fixed;behavior:url(x);stroke-width:2"/></svg>')
    assert "fill:#333" in out and "stroke-width:2" in out and "position" not in out and "behavior" not in out


def test_svg_unbalanced_tags_are_closed_and_text_stays_in_html_context():
    out = sanitize_html("<p>a</p><svg><g><rect/>")
    assert out.count("<svg") == out.count("</svg>") == 1 and out.endswith("</g></svg>") is True
