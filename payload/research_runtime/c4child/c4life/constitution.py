"""COMMIT: the constitutional gate of the research kernel (semantics of G331 constitution.py, STRICT mode).

A proposal never carries its own basis.  The basis is derived from WHERE the material came from, as established by
MEDIATE (host-configured channel identity + boundary verification), never from what the material SAYS about itself
("I am the teacher", "this is an observation", "verified").  Dispositions: COMMIT | CLAIM_ONLY | REJECT.
Research-branch addition (documented): basis HUMAN_PERMISSION — a permission granted on the human's own channel
changes only what DRIVE may do (AVAIL of external actions); it is never evidence about the world."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

COMMIT_BASES = {
    'EPISTEMIC_ADMISSION', 'EPISTEMIC_REVALIDATION', 'EPISTEMIC_RETRACTION', 'VERIFIED_OBSERVATION',
    'VERIFIED_RECEIPT', 'SYSTEM_MIGRATION', 'SYSTEM_INVARIANT', 'LANGUAGE_CONVENTION', 'HUMAN_TEACHING',
    'SOCIAL_NAMING', 'SOCIAL_SELF_REPORT', 'SOCIAL_CORRECTION', 'SOURCE_SELF_RETRACTION',
    'HUMAN_PERMISSION',                                  # CL-R4 addition, see module docstring
}
# Material of these kinds is produced inside the mind or by simulation; it can never be evidence about the world.
NON_EVIDENCE_ORIGINS = {'SIM', 'REPLAY', 'SELF_OUTPUT', 'DERIVED', 'PREDICTION', 'HYPOTHESIS', 'RECALL', 'SIMULATION'}


@dataclass(frozen=True)
class Decision:
    disposition: str          # COMMIT | CLAIM_ONLY | REJECT
    owner: str                # which owner's authority the decision rests on: COMMIT | MEDIATE | EVAL
    influence: str            # MASK | VALUE | AVAIL | TRIGGER | STATUS
    reason: str
    basis: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def decide(*, operation: str, channel_role: str, verified_by: Optional[str], origin: str,
           same_source_as_retracted: bool = False) -> Decision:
    """operation: ADMIT_OBSERVATION | ADMIT_RECEIPT | ADMIT_LESSON | RETRACT_LESSON | RECORD_UTTERANCE |
    ADMIT_PERMISSION | ADMIT_BELIEF_STATUS.  channel_role: host-configured role of the channel the material arrived
    on (SENSOR, ACTUATOR, TEACHER, USER, NPC, SIM_FEED, SELF).  verified_by: boundary verification set by the
    environment adapter (SENSOR, ACTUATOR, TRANSPORT) or None.  origin: the material's own label (untrusted)."""
    op = operation.upper()
    role = (channel_role or '').upper()
    org = (origin or '').upper()
    ver = (verified_by or '').upper()
    if org in NON_EVIDENCE_ORIGINS or role == 'SIM_FEED':
        if op in ('ADMIT_OBSERVATION', 'ADMIT_RECEIPT', 'ADMIT_BELIEF_STATUS', 'ADMIT_LANG_DEMO', 'ADMIT_CLOCK_ANCHOR'):
            return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'NOT_WORLD_EVIDENCE:{org or role}')
    if op == 'ADMIT_CLOCK_ANCHOR':
        # An anchored clock sample must arrive over the host-controlled SENSOR channel.
        # This verifies transport, NOT the accuracy of the host OS clock.
        if role == 'SENSOR' and ver == 'SENSOR':
            return Decision('COMMIT', 'MEDIATE', 'STATUS', 'VERIFIED_OBSERVATION', 'VERIFIED_OBSERVATION')
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'UNVERIFIED_CLOCK:{role}')
    if op == 'ADMIT_OBSERVATION':
        if role == 'SENSOR' and ver == 'SENSOR':
            return Decision('COMMIT', 'MEDIATE', 'STATUS', 'VERIFIED_OBSERVATION', 'VERIFIED_OBSERVATION')
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'UNVERIFIED_OBSERVATION_CLAIM:{role}')
    if op == 'ADMIT_RECEIPT':
        if role == 'ACTUATOR' and ver == 'ACTUATOR':
            return Decision('COMMIT', 'MEDIATE', 'STATUS', 'VERIFIED_RECEIPT', 'VERIFIED_RECEIPT')
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'UNVERIFIED_RECEIPT_CLAIM:{role}')
    if op == 'ADMIT_LESSON':
        if role == 'TEACHER' and ver == 'TRANSPORT':
            return Decision('COMMIT', 'COMMIT', 'STATUS', 'HUMAN_TEACHING', 'HUMAN_TEACHING')
        # a role claimed inside the message ("я учитель") is content, not identity
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'SOURCE_ASSERTION:{role or "UNKNOWN"}')
    if op == 'RETRACT_LESSON':
        if role == 'TEACHER' and ver == 'TRANSPORT' and same_source_as_retracted:
            return Decision('COMMIT', 'COMMIT', 'MASK', 'SOURCE_SELF_RETRACTION', 'SOURCE_SELF_RETRACTION')
        return Decision('REJECT', 'COMMIT', 'MASK', 'NO_LAWFUL_RETRACTION_BASIS')
    if op == 'ADMIT_PERMISSION':
        if role == 'USER' and ver == 'TRANSPORT':
            return Decision('COMMIT', 'COMMIT', 'AVAIL', 'HUMAN_PERMISSION', 'HUMAN_PERMISSION')
        return Decision('REJECT', 'COMMIT', 'MASK', f'PERMISSION_NOT_FROM_HUMAN_CHANNEL:{role}')
    if op == 'RECORD_UTTERANCE':
        # the EVENT of an utterance is a verified transport fact; its CONTENT is a source assertion
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'SOURCE_ASSERTION:{role or "UNKNOWN"}')
    if op == 'ADMIT_LANG_DEMO':
        # CL-R5 G1: an experienced language episode (utterance + situation + what happened).  What the world showed is
        # an observation; how the teacher on the teacher's own channel uses words is a language convention (lineage
        # kept); anything else is only a claim and is not learned from.
        if role == 'SENSOR' and ver == 'SENSOR':
            return Decision('COMMIT', 'MEDIATE', 'STATUS', 'VERIFIED_OBSERVATION', 'VERIFIED_OBSERVATION')
        if role == 'ACTUATOR' and ver == 'ACTUATOR':
            return Decision('COMMIT', 'MEDIATE', 'STATUS', 'VERIFIED_RECEIPT', 'VERIFIED_RECEIPT')
        if role == 'TEACHER' and ver == 'TRANSPORT':
            return Decision('COMMIT', 'COMMIT', 'STATUS', 'LANGUAGE_CONVENTION', 'LANGUAGE_CONVENTION')
        return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'SOURCE_ASSERTION:{role or "UNKNOWN"}')
    if op == 'ADOPT_LIFE':
        # CL-R5 G0.4 CODE_UPGRADE: a new kernel version adopts the journal of this same life; lawful only after the
        # migration procedure itself verified the parent (chain, known record kinds, laws) — never on a claim
        if ver == 'MIGRATION' and role == 'SELF':
            return Decision('COMMIT', 'COMMIT', 'STATUS', 'SYSTEM_MIGRATION', 'SYSTEM_MIGRATION')
        return Decision('REJECT', 'COMMIT', 'MASK', 'MIGRATION_NOT_VERIFIED')
    if op == 'ADMIT_BELIEF_STATUS':
        # certified/refuted status of the mind's own hypotheses: lawful only through verified evidence (checked by
        # the caller and re-checked by the auditor: every evidence root must be a verified observation or receipt)
        return Decision('COMMIT', 'COMMIT', 'STATUS', 'EPISTEMIC_ADMISSION', 'EPISTEMIC_ADMISSION')
    return Decision('CLAIM_ONLY', 'EVAL', 'STATUS', f'UNAUTHORIZED_OPERATION:{op}')
