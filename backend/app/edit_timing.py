"""Shared render/billing timing for non-destructive edits."""
def transition_overlap(edits):
    segments = edits['segments']
    if edits.get('transition', 'none') == 'none' or len(segments) < 2:
        return 0.0
    return min(edits.get('transition_duration', .3), min(s['end'] - s['start'] for s in segments) / 2)


def timeline_seconds(edits):
    return sum(s['end'] - s['start'] for s in edits['segments']) - transition_overlap(edits) * (len(edits['segments']) - 1)
