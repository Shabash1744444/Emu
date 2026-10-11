"""Host / environment adapter (EVALUATOR side).  It owns the worlds and the script of other participants, delivers
events to the kernel with CHANNEL IDENTITY and BOUNDARY VERIFICATION (the only things MEDIATE trusts), applies the
kernel's actions to the worlds and keeps the log of what the human actually received.

Channel roles: SENSOR (world percepts, verified SENSOR), ACTUATOR (receipts, verified ACTUATOR), USER and TEACHER
(verified TRANSPORT: we know the message came from that channel, nothing more), NPC (verified TRANSPORT), SIM_FEED
(a simulator replay feed: verified TRANSPORT, but its 'percepts' are not observations of this world)."""
from __future__ import annotations

import copy
import json
import pickle
from typing import Dict, List, Optional


class Host:
    def __init__(self, worlds: Dict[str, object], intros: Dict[str, int], script: List[dict], *,
                 entity_streams: Optional[Dict[str, List[dict]]] = None, delivery_log: Optional[str] = None,
                 ends: Optional[Dict[str, int]] = None):
        self.worlds = worlds                    # world_id -> MechWorld | EntityWorld
        self.intros = intros                    # world_id -> tick of introduction
        self.ends = ends or {}                  # world_id -> first tick at which the room is left (no more percepts)
        self.script = sorted(script, key=lambda e: (e['t'], json.dumps(e, ensure_ascii=False, sort_keys=True)))
        self.entity_streams = entity_streams or {}
        self.pending: Dict[str, Dict[str, int]] = {}      # world -> interventions for the next step
        self.receipts: Dict[str, List[dict]] = {}         # world -> receipts to deliver next tick
        self.delivered: List[dict] = []                   # what the human/teacher actually received (no replays)
        self.actions_applied: List[dict] = []
        self.history: Dict[str, Dict[int, dict]] = {w: {} for w in worlds}
        self.delivery_log = delivery_log                  # append-only file: survives crashes of everything
        self.golds: Dict[str, dict] = {}
        self.gold_fn = None

    # ------------------------------------------------------------------ events
    def events_for_tick(self, t: int) -> List[dict]:
        evs = []
        for w, t0 in sorted(self.intros.items()):
            wd = self.worlds[w]
            if t0 == t:
                if hasattr(wd, 'observable'):
                    names = wd.observable
                    evs.append({'type': 'WORLD_INTRO', 'channel': 'host', 'role': 'SENSOR', 'verified_by': 'SENSOR',
                                'content': {'world': w, 'names': names, 'domains': [wd.spec[n].domain for n in names],
                                            'switches': wd.switches, 'static': False,
                                            'targets': [n for n in names if n not in wd.switches]}})
                else:
                    names = wd.features + [wd.relation]
                    evs.append({'type': 'WORLD_INTRO', 'channel': 'host', 'role': 'SENSOR', 'verified_by': 'SENSOR',
                                'content': {'world': w, 'names': names, 'domains': [2] * len(names), 'switches': [],
                                            'static': True, 'targets': [wd.relation]}})
            if t0 <= t and hasattr(wd, 'observable') and t < self.ends.get(w, 10 ** 9):
                for r in self.receipts.pop(w, []):
                    evs.append(r)
                self.history[w][t] = dict(wd.state)
                evs.append({'type': 'PERCEPT', 'channel': f'sensor:{w}', 'role': 'SENSOR', 'verified_by': 'SENSOR',
                            'content': {'world': w, 'percept': wd.percept()}})
        for w, stream in self.entity_streams.items():
            for item in stream:
                if item['t'] == t:
                    wd = self.worlds[w]
                    e = item['entity']
                    evs.append({'type': 'ENTITY_OBS', 'channel': f'sensor:{w}', 'role': 'SENSOR', 'verified_by': 'SENSOR',
                                'content': {'world': w, 'entity': e, 'features': dict(wd.entities[e]),
                                            'labels': {wd.relation: wd.label(e)}}})
        for e in self.script:
            if e['t'] == t:
                ev = {k: v for k, v in e.items() if k not in ('t', 'gold', 'check', 'id')}
                evs.append(ev)
                if e.get('type') in ('QUESTION', 'GOAL') and self.gold_fn is not None:
                    self.golds[e['content'].get('qid') or e['content'].get('gid')] = self.gold_fn(self, t, e)
        return evs

    def _delivered_hashes(self):
        import os
        hs = set()
        if self.delivery_log and os.path.exists(self.delivery_log):
            with open(self.delivery_log, encoding='utf8') as f:
                for line in f:
                    try:
                        hs.add(json.loads(line)['hash'])
                    except (ValueError, KeyError):
                        pass
        return hs

    # ------------------------------------------------------------------ actions and messages
    def apply(self, t: int, outbox: List[dict]):
        for o in outbox:
            if o['kind'] == 'ACTION':
                c = o['content']
                w = c['world']
                self.pending.setdefault(w, {}).update({k: int(v) for k, v in c['action'].items()})
                self.receipts.setdefault(w, []).append({'type': 'RECEIPT', 'channel': f'actuator:{w}', 'role': 'ACTUATOR',
                                                        'verified_by': 'ACTUATOR',
                                                        'content': {'world': w, 'action': c['action'], 'status': 'EXECUTED',
                                                                    'effective_t': t + 1, 'for_seq': o['seq']}})
                self.actions_applied.append({'t': t, 'world': w, 'action': c['action'], 'replayed': o['replayed']})
            else:
                if not hasattr(self, '_dh'):
                    self._dh = self._delivered_hashes()
                if o['hash'] in self._dh:
                    continue                                   # exactly once: already in the human's hands
                row = {'t': t, 'seq': o['seq'], 'hash': o['hash'], 'channel': o['channel'], 'kind': o['kind'],
                       'content': o['content']}
                self.delivered.append(row)
                self._dh.add(o['hash'])
                if self.delivery_log:
                    with open(self.delivery_log, 'a', encoding='utf8') as f:
                        f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')
        for w, wd in sorted(self.worlds.items()):
            if hasattr(wd, 'step') and self.intros[w] <= t < self.ends.get(w, 10 ** 9):
                wd.step(self.pending.pop(w, {}))

    # ------------------------------------------------------------------ persistence (host side, not the mind)
    def dump(self, path: str):
        d = {k: v for k, v in self.__dict__.items() if k not in ('_dh', 'gold_fn')}
        with open(path + '.tmp', 'wb') as f:
            pickle.dump(d, f)
        import os
        os.replace(path + '.tmp', path)

    @classmethod
    def load(cls, path: str) -> 'Host':
        h = cls.__new__(cls)
        with open(path, 'rb') as f:
            h.__dict__.update(pickle.load(f))
        h.__dict__.setdefault('ends', {})
        return h
