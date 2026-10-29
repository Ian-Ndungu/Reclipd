"""Conservative, deterministic interpretation of editorial briefs.

Only explicit timestamp ranges and lexical topic exclusions are hard constraints.
Rendering options remain controlled by the project's typed configuration.
"""
import re

STOP = set('a an the and or to of in on at is it for with about please clip clips video videos find show select focus include only moments moment where that this from make create generate keep section sections discussion discuss talking talk me best engaging highlight highlights'.split())

def terms(text):
    tokens = set(re.findall(r"[^\W\d_]+", text.casefold(), re.UNICODE)) - STOP
    return {word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")) else word for word in tokens}


def parse_brief(text):
    exclusions = []
    def exclude(match):
        exclusions.append(terms(match.group(1)))
        return ' '
    positive = re.sub(r"\b(?:avoid|exclude|skip|do not include|don't include)\s+([^.;\n]+)", exclude, text, flags=re.I)
    ranges = []
    def seconds(value):
        total = 0
        for part in value.split(':'):
            total = total * 60 + int(part)
        return total
    def time_range(match):
        start, end = seconds(match.group(1)), seconds(match.group(2))
        if end <= start:
            raise ValueError('Clipping instruction time range must end after it starts.')
        ranges.append((start, end))
        return ' '
    positive = re.sub(r"(?<!\d)(\d{1,3}:\d{2}(?::\d{2})?)\s*(?:-|–|—|to)\s*(\d{1,3}:\d{2}(?::\d{2})?)(?!\d)", time_range, positive)
    return terms(positive), [x for x in exclusions if x], ranges
