from processing.markdown_renderer import render_markdown_html


def test_short_and_long_answers_remain_readable_markdown():
    short = render_markdown_html("Gotowe.")
    assert short == "<p>Gotowe.</p>"

    long = render_markdown_html(
        "## Wynik\n\n" + "Opis obserwacji. " * 80 +
        "\n\n### Następne kroki\n\n1. Sprawdź ostrość\n2. Zapisz obraz"
    )
    assert "<h2>Wynik</h2>" in long
    assert "<h3>Następne kroki</h3>" in long
    assert "<ol>" in long


def test_renders_headings_emphasis_lists_quotes_and_rule():
    html = render_markdown_html(
        "# Tytuł\n\n**ważne** i *kursywa*\n\n"
        "- punkt\n    - podpunkt\n- drugi\n\n\n"
        "1. pierwszy\n2. drugi\n\n> Uwaga\n\n---"
    )

    assert "<h1>Tytuł</h1>" in html
    assert "<strong>ważne</strong>" in html
    assert "<em>kursywa</em>" in html
    assert "<ul>" in html and "<ol>" in html
    assert "podpunkt" in html and "<blockquote>" in html
    assert "<hr" in html


def test_renders_tables_and_language_highlighted_code():
    html = render_markdown_html(
        "| Obiekt | FWHM |\n| --- | ---: |\n| M27 | 2.4 px |\n\n"
        "```python\nprint('gwiazdy')\n```"
    )

    assert "<table>" in html and "<th>Obiekt</th>" in html
    assert "<td>M27</td>" in html
    assert 'class="codehilite"' in html
    assert '<span class="n">print</span>' in html or '<span class="nb">print</span>' in html


def test_keeps_newlines_and_handles_incomplete_markdown_during_streaming():
    partial = render_markdown_html("## Niedokończony nagłówek\nLinia pierwsza\nLinia druga\n\n```python\nprint(")
    assert "<h2>Niedokończony nagłówek</h2>" in partial
    assert "Linia pierwsza<br" in partial
    assert "Linia druga" in partial
    assert "print(" in partial


def test_strips_unsafe_html_and_only_keeps_web_links():
    html = render_markdown_html(
        '<script>alert("xss")</script><img src="https://example.com/x.png" '
        'onerror="alert(1)"><a href="javascript:alert(1)" onclick="alert(2)">zły link</a> '
        '<a href="https://example.com">bezpieczny link</a>'
    )

    assert "<script" not in html.lower()
    assert "<img" not in html.lower()
    assert "onerror" not in html.lower() and "onclick" not in html.lower()
    assert "javascript:" not in html.lower()
    assert 'href="https://example.com"' in html
