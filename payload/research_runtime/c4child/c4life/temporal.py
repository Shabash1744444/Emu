"""Experimental C4 G1.1: external time substrate, independent of language.

This is an opt-in external organ, NOT a modification of frozen G1/G0 or life 104.
A tick is an ordinal; it is never assumed to represent a second.  UTC is an
external observation with provenance, not something C4 generates from ticks.

The substrate separates:
 - STEP: private computation order, no physical duration implied
 - WORLD_TICK: simulation order, rate not presumed
 - MONOTONIC: elapsed duration within one boot/session only
 - UTC: sampled external civil clock (may jump / be inaccurate)
 - EVENT_TIME: what occurred, may precede receipt or be uncertain
 - UTTERANCE_TIME: when a source actually spoke
 - NARRATED_TIME: period mentioned by utterance (not its receipt time)

Unknown and ambiguous intervals are explicitly preserved; a source claim
cannot mint verified event timestamps.  The host is responsible for attesting
clock samples, just as it does for action receipts.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Sequence
import time

US = 1_000_000


def micros(iso_aware: str) -> int:
    dt = datetime.fromisoformat(iso_aware)
    if dt.tzinfo is None:
        raise ValueError('External timestamps must have explicit UTC offset')
    return int(round(dt.timestamp() * US))


def local_date(utc_us: int, zone: str):
    return datetime.fromtimestamp(utc_us / US, tz=timezone.utc).astimezone(ZoneInfo(zone)).date()


@dataclass(frozen=True)
class Interval:
    lo_us: int
    hi_us: int
    provenance: str
    status: str = 'MEASURED'  # MEASURED / ESTIMATED / SOURCE_CLAIM / SIMULATED

    def __post_init__(self):
        if self.hi_us < self.lo_us:
            raise ValueError('negative interval')
        if not self.provenance:
            raise ValueError('provenance is required')

    @classmethod
    def point(cls, center_us: int, uncertainty_us: int, provenance: str, status='MEASURED'):
        if uncertainty_us < 0:
            raise ValueError('negative uncertainty')
        return cls(center_us-uncertainty_us, center_us+uncertainty_us, provenance, status)


def order(a: Interval, b: Interval) -> str:
    """Definite temporal relation; overlap could be simultaneity OR ambiguous order."""
    if a.hi_us < b.lo_us:
        return 'BEFORE'
    if b.hi_us < a.lo_us:
        return 'AFTER'
    return 'UNKNOWN_OR_OVERLAP'


@dataclass(frozen=True)
class ClockAnchor:
    session: str
    monotonic_us: int
    utc_us: int
    uncertainty_us: int
    source: str
    attested: bool = False
    journal_seq: Optional[int] = None      # provenance in this life (not an independent source root)
    adopted_from: Optional[int] = None    # inherited parent record when re-admitted under new code

    def __post_init__(self):
        if not self.session or not self.source or self.uncertainty_us < 0:
            raise ValueError('invalid clock anchor')


def sample_host_clock(session: str, source: str = 'HOST_OS_UNVERIFIED') -> ClockAnchor:
    """Convenience host API; NOT attested against an external timeserver."""
    a = time.monotonic_ns()
    wall = time.time_ns()
    b = time.monotonic_ns()
    return ClockAnchor(session, ((a + b)//2)//1000, wall//1000,
                       max(1000, (b-a)//1000+1000), source, False)


class ClockMap:
    """A set of recorded synchronization pairs, never a tick->UTC conversion.

    Only bracketed interpolation is permitted.  An OS clock discontinuity
    invalidates interpolation across the discontinuity; no extrapolation.
    Monotonic clocks may not be compared across sessions/reboots.
    """
    def __init__(self, max_jump_us: int = 2_000_000):
        self.anchors: list[ClockAnchor] = []
        self.max_jump_us = max_jump_us

    def add(self, a: ClockAnchor):
        if a in self.anchors:
            return False  # identical repeated delivery does not mint an independent root
        self.anchors.append(a)
        self.anchors.sort(key=lambda x: (x.session, x.monotonic_us, x.utc_us))
        return True

    def estimate_utc(self, session: str, monotonic_us: int) -> Optional[Interval]:
        arr = [x for x in self.anchors if x.session == session]
        exact = [x for x in arr if x.monotonic_us == monotonic_us]
        if exact:
            if len({x.utc_us for x in exact}) > 1:
                return None
            x = exact[-1]
            return Interval.point(x.utc_us, x.uncertainty_us, x.source,
                                  'MEASURED' if x.attested else 'ESTIMATED')
        lo = [x for x in arr if x.monotonic_us < monotonic_us]
        hi = [x for x in arr if x.monotonic_us > monotonic_us]
        if not lo or not hi:
            return None
        l, h = lo[-1], hi[0]
        dt_m = h.monotonic_us - l.monotonic_us
        dt_w = h.utc_us - l.utc_us
        if abs(dt_w - dt_m) > self.max_jump_us + l.uncertainty_us + h.uncertainty_us:
            return None   # wall-clock stepped; offset is not inferable between samples
        alpha = (monotonic_us - l.monotonic_us)/dt_m
        target = int(round(l.utc_us + alpha*dt_w))
        unc = max(l.uncertainty_us, h.uncertainty_us) + int(abs(dt_w-dt_m))
        both_attested = l.attested and h.attested
        return Interval.point(target, unc, f'CLOCK_MAP:{l.source}|{h.source}',
                              'ESTIMATED' if not both_attested else 'MEASURED')

    def to_dict(self):
        return {'max_jump_us': self.max_jump_us, 'anchors': [asdict(a) for a in self.anchors]}

    @classmethod
    def from_dict(cls, d):
        s = cls(d['max_jump_us'])
        for a in d['anchors']:
            s.add(ClockAnchor(**a))
        return s


@dataclass(frozen=True)
class TimedEvent:
    event_id: str
    when: Interval
    source_root: str
    domain: str
    simulation: bool = False
    uttered_at: Optional[Interval] = None
    narrated_at: Optional[Interval] = None

    def __post_init__(self):
        if not self.event_id or not self.source_root or not self.domain:
            raise ValueError('event ID, evidence lineage and domain are required')


def reference_features(ev: TimedEvent, at: Interval, zone: str) -> dict[str, float]:
    """Language-neutral measurable features; not rules for Russian vocabulary.

    A point-valued event and utterance give precise civil-day delta and
    duration bins.  Uncertain event order returns NO definite temporal claim.
    Clock zone is a *supplied context*, not inferred from language tokens.
    """
    c = (ev.when.lo_us + ev.when.hi_us)//2
    n = (at.lo_us + at.hi_us)//2
    delta = c-n
    rel = order(ev.when, at)
    feats: dict[str, float] = {'bias': 1.0}
    if rel == 'BEFORE':
        feats['order:before'] = 1.0
    elif rel == 'AFTER':
        feats['order:after'] = 1.0
    else:
        feats['order:uncertain'] = 1.0
    # ONLY assert calendar day if the entire interval falls on one civil day
    # and the reference interval also falls on one day in the same zone.
    d0, d1 = local_date(ev.when.lo_us, zone), local_date(ev.when.hi_us, zone)
    n0, n1 = local_date(at.lo_us, zone), local_date(at.hi_us, zone)
    if d0 == d1 and n0 == n1:
        dd = (d0-n0).days
        feats['civil:day:'+str(max(-7, min(7, dd)))] = 1.0
        feats['civil:weekday:'+str(d0.weekday())] = 1.0
    else:
        feats['civil:uncertain'] = 1.0
    # Duration bins describe *relative physical time*, not named weekdays.
    if rel != 'UNKNOWN_OR_OVERLAP':
        elapsed = abs(delta)
        for label, threshold in [('1m', 60*US), ('1h', 3600*US), ('1d', 86400*US), ('1w', 604800*US)]:
            feats['distance:lt:'+label] = float(elapsed < threshold)
            feats['distance:ge:'+label] = float(elapsed >= threshold)
    return feats
