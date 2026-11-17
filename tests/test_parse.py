from aiwash.parse import parse_10k


def test_item_headings_in_layout_tables():
    # Amazon and Walmart put "ITEM 1A. | Risk Factors" in a one-row table
    html = """<body>
      <table><tr><td>ITEM&#160;1A.</td><td>Risk Factors</td></tr></table>
      <div>Our business could be harmed by many things that we describe below in detail.</div>
    </body>"""
    blocks = parse_10k(html)
    assert blocks[-1].item == "1A"
    assert blocks[-1].section == "Item 1A. Risk Factors"


def test_page_breaks_are_counted():
    html = """<body>
      <div>Item 1. Business</div>
      <div>First page text that is long enough to keep.</div>
      <hr style="page-break-after: always">
      <div>Second page text that is long enough to keep.</div>
    </body>"""
    blocks = parse_10k(html)
    assert [b.page for b in blocks] == [1, 1, 2]


def test_hidden_xbrl_header_is_skipped():
    html = """<body>
      <div style="display:none"><ix:header>dei:EntityRegistrantName Apple</ix:header></div>
      <div>Visible text.</div>
    </body>"""
    assert [b.text for b in parse_10k(html)] == ["Visible text."]


def test_real_data_tables_stay_tables():
    html = """<body><table>
      <tr><td>Revenue</td><td>$</td><td>100</td></tr>
      <tr><td>Cost</td><td>$</td><td>60</td></tr>
    </table></body>"""
    (block,) = parse_10k(html)
    assert block.is_table
    assert block.text == "Revenue | 100\nCost | 60"
