"""G2.7 research: acquire grammatical surface variation from grounded contrasts.

No Russian suffix table, pronouns, case labels, or word meanings are installed.
The teacher supplies a previously attested semantic EVENT and raw utterance.
A tentative alignment based on shared word stems produces *candidate* suffix
transductions. Only rules independently supported by distinct stems may be used
on unknown names. Exact/ambiguous scene references always take precedence.

LIMIT: single-token scene aliases; prefix-preserving suffix edits; structured
entities supplied by simulator. This is not unsupervised Russian parsing.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import hashlib,json
from .text_story_induction import PatternInducer,NarrativeMind,words,SCHEMAS,PERSON_ROLES,stable


def split_edit(base,surface):
    i=0
    while i<min(len(base),len(surface)) and base[i]==surface[i]:i+=1
    deleted,inserted=base[i:],surface[i:]
    if i<2 or len(deleted)>3 or len(inserted)>3:return None
    if deleted==inserted:return None
    return deleted,inserted,i


def similar(base,surface):
    if base==surface:return (100,len(base))
    e=split_edit(base,surface)
    if e is None:return None
    old,new,stem=e
    # The common stem must dominate the edit: prevents treating a function
    # word or a different person's name as an inflected alias.
    if stem<max(2,(len(base)+1)//2):return None
    return (stem*10-3*(len(old)+len(new)),stem)


class MorphStory:
    def __init__(self,min_support=3,min_stems=3):
        self.schematic=PatternInducer(min_support=min_support)
        self.min_stems=min_stems
        self.morph_evidence=[]
        self.rejected=[]

    @staticmethod
    def _scene(persons,objects):
        if not isinstance(persons,dict) or not isinstance(objects,dict):raise ValueError('SCENE_REQUIRED')
        records=[]
        for typ, inventory in [('P',persons),('O',objects)]:
            for alias,referent in inventory.items():
                a=words(alias)
                if len(a)!=1 or not isinstance(referent,str) or not referent:
                    raise ValueError('ONLY_SINGLE_TOKEN_REFERENTS')
                records.append((typ,a[0],referent))
        return records

    def teach(self,utterance,target,persons,objects,source,context=None):
        """Find ONE admissible grounding, then commit all or none of the lesson."""
        roles=PatternInducer._slots_for(target)
        tokens=words(utterance)
        if not tokens or len(tokens)>50:raise ValueError('INVALID_UTTERANCE')
        records=self._scene(persons,objects)
        context=context or {}
        role_choices={}
        defaults={}
        for role in roles:
            typ='P' if role in PERSON_ROLES else 'O'
            matching=[(base,t) for t,base,ref in records if t==typ and ref==target[role]]
            # Alias must exist for the intended event referent; never infer
            # that some *other* entity is the intended recipient.
            if not matching:
                chans=[x for x in ('speaker','addressee') if target[role]==context.get(x)]
                if len(chans)==1 and typ=='P':
                    defaults[role]=chans[0];continue
                raise ValueError('UNATTESTED_REFERENT')
            options=[]
            for base,_ in matching:
                for i,token in enumerate(tokens):
                    sc=similar(base,token)
                    if sc is None:continue
                    # Reject a surface alias that's an exact name for another
                    # scene entity, even if it resembles this role's name.
                    if any(t==typ and word==token and ref!=target[role] for t,word,ref in records):
                        continue
                    options.append((sc[0],i,base,token,role))
            if not options:raise ValueError('NO_GROUNDED_SURFACE')
            role_choices[role]=options
        active=list(role_choices)
        results=[]
        def assign(i,chosen,occupied,score):
            if i==len(active):
                pat=[]
                at={v[1]:v[4] for v in chosen}
                for j,tok in enumerate(tokens):pat.append('@'+at[j] if j in at else tok)
                learned=tuple(pat)
                # Existing independently supported skeleton can break ties
                # between duplicate referents without fixed subject position.
                bonus=100000 if learned in self.schematic.patterns and self.schematic.patterns[learned][0]==target['kind'] else 0
                results.append((score+bonus,learned,chosen[:]))
                return
            for x in role_choices[active[i]]:
                if x[1] not in occupied:
                    assign(i+1,chosen+[x],occupied|{x[1]},score+x[0])
                    if len(results)>3000:raise ValueError('ALIGNMENT_EXPLOSION')
        assign(0,[],set(),0)
        if not results:raise ValueError('NO_UNIQUE_ALIGNMENT')
        top=max(r[0] for r in results)
        contenders=[r for r in results if r[0]==top]
        if len(contenders)!=1:raise ValueError('AMBIGUOUS_ALIGNMENT')
        _,pattern,chosen=contenders[0]
        # Grammar contradictions are retained as evidence by the underlying
        # learner; a pattern with multiple meanings becomes UNKNOWN.
        lesson={'kind':target['kind'],'pattern':list(pattern),'defaults':defaults,
                'source':source,'utterance':utterance}
        ed=[]
        for _,_,base,surface,role in chosen:
            change=split_edit(base,surface)
            if change:
                old,new,_=change
                ed.append({'source':source,'pattern':list(pattern),'role':role,
                           'type':'P' if role in PERSON_ROLES else 'O',
                           'base':base,'surface':surface,'remove':old,'append':new})
        for _,_,base,surface,role in chosen:
            if base==surface:
                ed.append({'source':source,'pattern':list(pattern),'role':role,
                           'type':'P' if role in PERSON_ROLES else 'O',
                           'base':base,'surface':surface,'remove':'','append':''})
        # Fully transactional even for unexpected formatting errors.
        self.schematic.examples.append(lesson)
        self.morph_evidence.extend(ed)
        self.schematic._rebuild()
        return {'status':'ADMITTED','kind':target['kind'],'pattern':list(pattern),
                'candidate_surface_edits':len(ed)}

    def accepted_edits(self):
        """Pattern/role-conditioned affix transformations learned across stems.

        The SAME person can be nominative in one syntactic role and genitive
        in another. Rules therefore belong to a learned construction slot.
        Any irregular alternative must be observed on distinct names.
        """
        support=defaultdict(set)
        for ev in self.morph_evidence:
            key=(tuple(ev['pattern']),ev['role'],ev['type'],ev['remove'],ev['append'])
            support[key].add(ev['base'])
        groups=defaultdict(dict)
        for (pat,role,typ,old,new),bases in support.items():
            if len(bases)>=self.min_stems:
                groups[(pat,role,typ,old)][new]=bases
        learned={}
        for (pat,role,typ,old),variants in groups.items():
            if len(variants)==1:
                new,bases=next(iter(variants.items()))
                learned[(pat,role,typ,old,new,'')]=len(bases)
                continue
            ranked=sorted(variants.items(),key=lambda kv:(-len(kv[1]),kv[0]))
            default,major=ranked[0]
            exceptions={}
            clean=True
            for alternative,bases in ranked[1:]:
                endings={base[:-len(old)][-1:] if old else base[-1:] for base in bases}
                if len(endings)!=1 or not next(iter(endings)):
                    clean=False;break
                ending=next(iter(endings))
                if any((other[:-len(old)][-1:] if old else other[-1:])==ending
                       for other in major):clean=False;break
                if ending in exceptions:clean=False;break
                exceptions[ending]=(alternative,len(bases))
            if not clean:continue
            learned[(pat,role,typ,old,default,'')]=len(major)
            for ending,(alternative,count) in exceptions.items():
                learned[(pat,role,typ,old,alternative,ending)]=count
        return learned

    def _forms(self,pattern,role,typ,base,rules):
        grouped=defaultdict(list)
        for (pat,r,t,old,new,cond),sup in rules.items():
            if pat!=pattern or r!=role or t!=typ:return_candidate=False
            else:return_candidate=True
            if not return_candidate:continue
            if old and not base.endswith(old):continue
            stem=base[:-len(old)] if old else base
            if cond and not stem.endswith(cond):continue
            grouped[old].append((cond,stem+new))
        out=set()
        for variants in grouped.values():
            most=max(len(c) for c,form in variants)
            out.update(form for c,form in variants if len(c)==most)
        return out

    def parse(self,paragraph,persons,objects,context=None,max_events=12):
        records=self._scene(persons,objects)
        tokens=words(paragraph)
        if not tokens or len(tokens)>120:return {'status':'UNKNOWN','reason':'LENGTH'}
        rules=self.accepted_edits();ctx=context or {}
        candidates={0:[[]]}
        for start in range(len(tokens)):
            if start not in candidates:continue
            for pat,(kind,support,defaults) in self.schematic.patterns.items():
                bindings={};pos=start;valid=True
                for elem in pat:
                    if elem.startswith('@'):
                        role=elem[1:];typ='P' if role in PERSON_ROLES else 'O'
                        options=set()
                        for rt,base,value in records:
                            if rt==typ and pos<len(tokens) and tokens[pos] in self._forms(pat,role,typ,base,rules):
                                options.add(value)
                        if len(options)!=1:valid=False;break
                        bindings[role]=next(iter(options));pos+=1
                    elif pos<len(tokens) and tokens[pos]==elem:pos+=1
                    else:valid=False;break
                if not valid or pos<=start:continue
                for role,channel in defaults.items():
                    if not isinstance(ctx.get(channel),str) or not ctx[channel]:valid=False;break
                    bindings[role]=ctx[channel]
                if not valid:continue
                for seq in candidates[start]:
                    if len(seq)>=max_events:continue
                    proposed=seq+[{'kind':kind,**bindings}]
                    bucket=candidates.setdefault(pos,[])
                    if proposed not in bucket:bucket.append(proposed)
                    if len(bucket)>1:bucket[:]=bucket[:2]
        final=candidates.get(len(tokens),[])
        if not final:return {'status':'UNKNOWN','reason':'UNSUPPORTED_SURFACE'}
        if len(final)>1:return {'status':'UNKNOWN','reason':'AMBIGUOUS_COMPOSITION'}
        return {'status':'PARSED','scope':'NARRATED_ONLY','events':final[0],
                'tokens':len(tokens),'boundaries_supplied':False}

    def retract(self,source):
        self.schematic.retract(source)
        self.morph_evidence=[e for e in self.morph_evidence if e['source']!=source]

    def to_dict(self):
        return {'schematic':self.schematic.to_dict(),'min_stems':self.min_stems,
                'morph_evidence':self.morph_evidence}

    @classmethod
    def from_dict(cls,d):
        o=cls(d['schematic']['min_support'],d['min_stems'])
        o.schematic=PatternInducer.from_dict(d['schematic'])
        o.morph_evidence=list(d['morph_evidence']);return o

    def digest(self):return hashlib.sha256(stable(self.to_dict()).encode()).hexdigest()
