"""The entire obligation must survive both held and laid-down document artwork."""
import xml.etree.ElementTree as ET
import pytest
from history_of_x.rig_art import prop_art


@pytest.mark.parametrize("kind", ["paper", "paper_flat"])
def test_paper_never_truncates_the_second_language_obligation(kind):
    content = "Article 17: MAY (Amharic) / MUST (Italian)"
    root = ET.fromstring("<svg>" + prop_art(kind, content) + "</svg>")
    lines = [element.text for element in root.iter("text")]
    assert " ".join(lines) == content
    assert all(12 <= float(element.attrib["font-size"]) <= 26 for element in root.iter("text"))
