"""
HTML content text validation module.
Detects and fixes typos before rendering.
"""
import re
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# Protected terms with correct spelling (lowercase -> correct)
PROTECTED_TERMS = {
    # Brand
    "olivenet": "Olivenet",
    "olivaborplus": "olivaborplus",

    # Technical terms
    "lorawan": "LoRaWAN",
    "iot": "IoT",
    "mqtt": "MQTT",
    "modbus": "Modbus",
    "scada": "SCADA",
    "plc": "PLC",
    "oee": "OEE",
    "kktc": "KKTC",

    # Common tech terms
    "instagram": "Instagram",
    "wifi": "WiFi",
    "bluetooth": "Bluetooth",
}

# Common typo patterns
COMMON_TYPOS = {
    "olivenet": ["ovenet", "oivenet", "olivnet", "oliveneet", "oliveenet", "olivent", "oilvent", "olivennet"],
    "lorawan": ["lorwan", "lowaran", "loarwan", "loorawan", "lorawon", "lorawen"],
    "iot": ["lot", "iiot", "oit", "liot"],
}


def extract_text_from_html(html_content: str) -> str:
    """
    Extract all text content from HTML.

    Args:
        html_content: Raw HTML string

    Returns:
        Extracted text with whitespace normalized
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script and style tags
    for tag in soup(['script', 'style']):
        tag.decompose()

    return soup.get_text(separator=' ', strip=True)


def find_typos(text: str) -> List[Dict]:
    """
    Find known typos in text.

    Args:
        text: Text content to check

    Returns:
        List of issue dictionaries with type, found, expected, severity
    """
    issues = []
    words = re.findall(r'\b\w+\b', text.lower())

    for word in words:
        # Check against known typos
        for correct, typos in COMMON_TYPOS.items():
            if word in typos:
                issues.append({
                    "type": "typo",
                    "found": word,
                    "expected": PROTECTED_TERMS.get(correct, correct),
                    "severity": "high"
                })

        # Find words similar to protected terms but not exact match (fuzzy)
        for term_lower, term_correct in PROTECTED_TERMS.items():
            if word != term_lower and len(word) > 3:
                similarity = SequenceMatcher(None, word, term_lower).ratio()
                if 0.7 < similarity < 1.0:  # Similar but not same
                    issues.append({
                        "type": "similar",
                        "found": word,
                        "expected": term_correct,
                        "similarity": round(similarity * 100, 1),
                        "severity": "medium"
                    })

    return issues


def check_protected_terms(text: str) -> List[Dict]:
    """
    Check if protected terms are spelled correctly (case sensitivity).

    Args:
        text: Text content to check

    Returns:
        List of case issues
    """
    issues = []

    for term_lower, term_correct in PROTECTED_TERMS.items():
        # Case-insensitive search
        pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE)
        matches = pattern.findall(text)

        for match in matches:
            if match != term_correct:
                issues.append({
                    "type": "case",
                    "found": match,
                    "expected": term_correct,
                    "severity": "low"
                })

    return issues


def validate_html_content(html_content: str) -> Dict:
    """
    Validate HTML content for text issues.

    Args:
        html_content: Raw HTML string

    Returns:
        Dictionary with:
        - valid: bool - True if no issues found
        - issues: List of all issues
        - issue_count: Total number of issues
        - high_severity_count: Number of high severity issues
        - text_preview: First 200 chars of extracted text
        - can_render: bool - True if no high severity issues (OK to render)
    """
    text = extract_text_from_html(html_content)

    typos = find_typos(text)
    term_issues = check_protected_terms(text)

    all_issues = typos + term_issues

    # Evaluate severity
    high_severity = [i for i in all_issues if i.get("severity") == "high"]

    return {
        "valid": len(all_issues) == 0,
        "issues": all_issues,
        "issue_count": len(all_issues),
        "high_severity_count": len(high_severity),
        "text_preview": text[:200] + "..." if len(text) > 200 else text,
        "can_render": len(high_severity) == 0  # Only block on high severity
    }


def fix_common_issues(html_content: str) -> Tuple[str, List[str]]:
    """
    Automatically fix known issues in HTML content.

    Args:
        html_content: Raw HTML string

    Returns:
        Tuple of (fixed_html, list_of_fixes_applied)
    """
    fixes = []
    fixed = html_content

    # Fix known typos
    for correct, typos in COMMON_TYPOS.items():
        correct_term = PROTECTED_TERMS.get(correct, correct)
        for typo in typos:
            # Case insensitive replace
            pattern = re.compile(re.escape(typo), re.IGNORECASE)
            if pattern.search(fixed):
                fixed = pattern.sub(correct_term, fixed)
                fixes.append(f"'{typo}' -> '{correct_term}'")

    # Fix case issues for protected terms (more aggressive)
    for term_lower, term_correct in PROTECTED_TERMS.items():
        # Find word boundaries to avoid partial matches
        pattern = re.compile(r'\b' + re.escape(term_lower) + r'\b', re.IGNORECASE)
        matches = pattern.findall(fixed)

        for match in matches:
            if match != term_correct:
                fixed = fixed.replace(match, term_correct)
                if f"'{match}' -> '{term_correct}'" not in fixes:
                    fixes.append(f"'{match}' -> '{term_correct}'")

    return fixed, fixes


def get_validation_summary(validation_result: Dict) -> str:
    """
    Get a human-readable summary of validation results.

    Args:
        validation_result: Result from validate_html_content()

    Returns:
        Summary string
    """
    if validation_result["valid"]:
        return "No issues found"

    summary_parts = []

    if validation_result["high_severity_count"] > 0:
        summary_parts.append(f"{validation_result['high_severity_count']} critical typos")

    medium_count = len([i for i in validation_result["issues"] if i.get("severity") == "medium"])
    if medium_count > 0:
        summary_parts.append(f"{medium_count} potential issues")

    low_count = len([i for i in validation_result["issues"] if i.get("severity") == "low"])
    if low_count > 0:
        summary_parts.append(f"{low_count} case issues")

    return ", ".join(summary_parts)
