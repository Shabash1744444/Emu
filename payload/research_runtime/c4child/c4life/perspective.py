"""Perspective bookkeeping: who said / thinks what, when it was said, and what time it talks about.

Derived only from MEDIATE INBOUND utterance records and from the mind's own OUTBOUND records — never from content
labels.  A claim is stored EXACTLY as said (nesting and negations preserved); `effective()` computes what it
amounts to logically (double negation cancels) only when a question needs it.
Times: `t_said` is the world clock of the utterance (verified transport); `narrated` is what the content talks about:
an int, an interval [a, b], or None (unknown).  'недавно' becomes an interval, never a point.
Speaker identity comes from the channel (host-verified), never from 'я учитель' inside the content."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

SELF = 'C4'


def effective(c: dict) -> Tuple[dict, bool]:
    """Strip negations: returns (base proposition, polarity)."""
    pol = True
    while c.get('op') == 'NOT':
        pol = not pol
        c = c['arg']
    return c, pol


def prop_key(c: dict) -> tuple:
    base, _ = effective(c)
    op = base.get('op')
    if op == 'STATE':
        return ('STATE', base.get('world'), base.get('var'))
    if op == 'CAUSES':
        return ('CAUSES', base.get('world'), base.get('cause'), base.get('effect'))
    if op == 'MECH':
        return ('MECH', base.get('world'), base.get('var'))
    if op in ('SAY', 'THINK'):
        return (op, base.get('holder')) + prop_key(base['arg'])
    return (op,)


class Perspective:
    def __init__(self):
        self.said: List[dict] = []          # {speaker, content, t_said, narrated, seq, channel_role, self}
        self.role_claims: List[dict] = []

    def add(self, *, speaker: str, content: dict, t_said: int, narrated: Any, seq: int, channel_role: str,
            own: bool = False):
        rec = {'speaker': speaker, 'content': content, 't_said': t_said, 'narrated': narrated, 'seq': seq,
               'channel_role': channel_role, 'own': own}
        self.said.append(rec)
        if content.get('op') == 'ROLE':
            self.role_claims.append(rec)
        return rec

    # ------------------------------------------------------------------ queries
    def said_about(self, speaker: str, key: tuple, *, narrated_t: Optional[int] = None) -> List[dict]:
        out = []
        for r in self.said:
            if r['speaker'] != speaker:
                continue
            c = r['content']
            if prop_key(c) != key:
                continue
            if narrated_t is not None:
                n = r['narrated']
                if n is None:
                    continue
                if isinstance(n, list):
                    if not (n[0] <= narrated_t <= n[1]):
                        continue
                elif n != narrated_t:
                    continue
            out.append(r)
        return out

    def latest_stance(self, speaker: str, key: tuple, at_t: Optional[int] = None) -> Optional[dict]:
        rows = [r for r in self.said_about(speaker, key) if at_t is None or r['t_said'] <= at_t]
        return rows[-1] if rows else None

    def stances(self, speaker: str, key: tuple) -> List[dict]:
        """What `speaker` holds about `key`, in the order said: her direct assertions about it and her own
        reports of her thinking ('I think that ...').  Reports BY OTHERS of what she thinks are quotes, not stances."""
        out = []
        for r in self.said:
            if r['speaker'] != speaker:
                continue
            if prop_key(r['content']) == key:
                out.append(r)
                continue
            base, pol = effective(r['content'])
            if base.get('op') == 'THINK' and base.get('holder') == speaker and prop_key(base['arg']) == key:
                out.append(r)
        return out

    @staticmethod
    def stance_content(r: dict, speaker: str):
        """(base proposition, polarity) of a stance record, unwrapping a self-report of thinking."""
        base, pol = effective(r['content'])
        if base.get('op') == 'THINK' and base.get('holder') == speaker:
            b2, p2 = effective(base['arg'])
            return b2, (pol == p2)
        return base, pol

    def quotes_of(self, quoted: str, key: Optional[tuple] = None) -> List[dict]:
        """Utterances of OTHERS that report what `quoted` said: SAY(quoted, ...)."""
        out = []
        for r in self.said:
            base, pol = effective(r['content'])
            if base.get('op') == 'SAY' and base.get('holder') == quoted and r['speaker'] != quoted:
                if key is None or prop_key(base['arg']) == key:
                    out.append(r)
        return out

    def own_statements(self, key: Optional[tuple] = None) -> List[dict]:
        return [r for r in self.said if r['own'] and (key is None or prop_key(r['content']) == key)]

    def to_dict(self):
        return {'said': self.said, 'role_claims': self.role_claims}

    @classmethod
    def from_dict(cls, d):
        p = cls()
        p.said, p.role_claims = list(d['said']), list(d['role_claims'])
        return p


class SourceReliability:
    """Prequential reliability of a speaker: Beta counts of claims about world states that the mind could later check
    against its OWN verified observations.  Never raised by repetition or by the speaker's own claims of authority."""

    def __init__(self):
        self.counts: Dict[str, List[int]] = {}

    def score(self, speaker: str, agreed: bool):
        c = self.counts.setdefault(speaker, [0, 0])
        c[0 if agreed else 1] += 1

    def mean(self, speaker: str) -> float:
        a, b = self.counts.get(speaker, [0, 0])
        return (a + 1) / (a + b + 2)

    def to_dict(self):
        return dict(self.counts)

    @classmethod
    def from_dict(cls, d):
        s = cls()
        s.counts = {k: list(v) for k, v in d.items()}
        return s
