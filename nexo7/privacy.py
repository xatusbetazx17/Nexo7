"""Conservative preflight for external text; does not guarantee de-identification."""
from .learning import privacy_warnings


def check_outbound(text):
    warnings = privacy_warnings({'question': '', 'answer': text})
    if warnings:
        raise ValueError('External request blocked: possible private information (' + '; '.join(warnings) + '). Remove it and use a general topic. Nothing was sent by this request.')
