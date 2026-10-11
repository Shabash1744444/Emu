"""G1.1 generic frames for observed, narrated and intended events.

NOT a Russian parser and NOT a source of world truth. A language learner may
hypothesize these representations from surface strings, and world tools may
supply independently checked receipts. The schema is agnostic about how many
participant slots exist and what words denote them.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Mapping, Any
from .temporal import Interval


@dataclass(frozen=True)
class Frame:
    episode_id: str
    world: str
    predicate: str
    bindings: tuple[tuple[str,str], ...]  # arbitrary learned slot names, not a built-in set of human roles
    event_time: Optional[Interval]
    source: str
    source_root: str
    status: str  # OBSERVED / REPORTED / INTENDED / HYPOTHETICAL / FICTIONAL
    polarity: str = 'POS'  # POS / NEG / UNSET, semantic scope local to this proposition
    speaker: Optional[str] = None
    listener: Optional[str] = None
    utterance_time: Optional[Interval] = None
    narrated_time: Optional[Interval] = None
    quote_scope: tuple[str,...] = ()
    semantic_attributes: tuple[tuple[str,str], ...] = ()  # G1.2: learned attributes not expressible as a scalar timestamp

    def __post_init__(self):
        if not self.episode_id or not self.source or not self.source_root:
            raise ValueError('an event and its source are required')
        if len({k for k,v in self.bindings}) != len(self.bindings):
            raise ValueError('duplicate participant slot')
        if len({k for k,v in self.semantic_attributes}) != len(self.semantic_attributes):
            raise ValueError('duplicate semantic attribute')
        if self.status not in {'OBSERVED','REPORTED','INTENDED','HYPOTHETICAL','FICTIONAL'}:
            raise ValueError('unknown modality/status')
        if self.polarity not in {'POS','NEG','UNSET'}:
            raise ValueError('unknown polarity')

    def role(self, slot: str) -> Optional[str]:
        return dict(self.bindings).get(slot)


class FrameStore:
    """Keeps views separate. External receipts must be passed by trusted host.

    Speaker claims do not imply observed events, including when claimed by
    another model. Frame keys preserve roles, scopes, temporality and negation.
    """
    def __init__(self):
        self.frames: list[Frame] = []
        self.verified_roots: set[str] = set()

    def attest_receipt_root(self, source_root: str, *, trusted_host: bool = False):
        if not trusted_host:
            raise PermissionError('only MEDIATE host may attest external receipt roots')
        self.verified_roots.add(source_root)

    def admit(self, frame: Frame):
        if frame.status == 'OBSERVED' and frame.source_root not in self.verified_roots:
            raise PermissionError('observation without a verified receipt')
        if frame in self.frames:
            return False  # repeat of the same event/claim is NOT independent evidence
        self.frames.append(frame)
        return True

    def query(self, *, world: Optional[str] = None, speaker: Optional[str] = None,
              status: Optional[str] = None, predicate: Optional[str] = None,
              scope: Optional[tuple[str,...]] = None):
        return [f for f in self.frames if (world is None or world == f.world)
                and (speaker is None or speaker == f.speaker)
                and (status is None or status == f.status)
                and (predicate is None or predicate == f.predicate)
                and (scope is None or scope == f.quote_scope)]

    def observed_current(self, *, world: str, predicate: str, bindings: tuple[tuple[str,str], ...]):
        """Returns only verified observations, preserving temporal uncertainty.
        Multiple conflicting snapshots cannot be collapsed into a 'now' claim
        without an explicit rule of persistence and a current-time observation.
        """
        return [f for f in self.frames if f.status=='OBSERVED' and f.world==world
                and f.predicate==predicate and f.bindings==bindings]
