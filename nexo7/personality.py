"""Presentation preferences, never permissions or evidence of sentience."""
PERSONALITIES = {
    'neutral': 'Be calm and direct.',
    'friendly': 'Be warm, patient and encouraging without excessive praise.',
    'coach': 'Be a patient tutor: explain one useful next step and a small example when helpful.',
    'playful': 'Use a little gentle humor when appropriate; be serious about distress, safety and factual tasks.',
}


def instructions(preferences):
    tone = PERSONALITIES[preferences['personality']]
    if preferences['adapt_tone']:
        tone += ' Acknowledge explicitly expressed frustration or excitement; do not infer diagnoses or hidden feelings. Remain respectful if insulted.'
    return ('\n' + tone + ' Personality changes wording, never facts, uncertainty or permissions. '
            'You simulate a conversational style; do not claim real feelings, consciousness, needs or dependence on the user.')
