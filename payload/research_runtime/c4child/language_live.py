"""Read-only language laboratory G3.0C, isolated from canonical G2.9 knowledge.

This adapter never treats unconstrained chat as a VERIFIED learning lesson,
never silently grants world observation, and never turns diagnostic text into
native C4 free-language generation.
"""
import json
from .g30b import digest
from .g30c import (SenseLedger, BoundaryInducer, ReferenceInducer,
                   ContextOperatorInducer, import_host_evidence, export_host_evidence,
                   restore_state, frozen_state, interpret_with_operators)

class LanguageLab:
    def __init__(self,index,observations,state):
        self.index=index
        self.host=import_host_evidence(observations)
        self.lex=SenseLedger(self.host,index['lexicon'])
        self.ortho=BoundaryInducer(self.host)
        self.refs=ReferenceInducer(self.host)
        self.ops=ContextOperatorInducer(self.host)
        restore_state(state,self.lex,self.ortho,self.refs,digest(index),operators=self.ops)
        self.start_count=len(self.lex.lessons)

    def interpret(self,text):
        try:
            r=interpret_with_operators(text,self.lex,self.ortho,self.ops)
        except (ValueError,TypeError) as exc:
            return {'epistemic':'UNVERIFIED_INTERPRETATION','error':str(exc), 'raw':text}
        return r

    def memory_state(self):
        return (self.index, export_host_evidence(self.host),
                frozen_state(self.lex,self.ortho,self.refs,digest(self.index),operators=self.ops))

    def diagnostic(self,text):
        r=self.interpret(text)
        lexical=r.get('lexical_candidates',[])
        if not lexical:
            return ('Ни одного знакомого смыслового слова не выделено. '
                    'Предложение в целом не понято.'),r
        parts=[]
        for lex in lexical[:7]:
            result=lex['result']; st=result.get('status','UNKNOWN')
            chosen=result.get('chosen')
            parts.append(str(lex['raw'])+' → '+(str(chosen) if chosen is not None else st))
        msg='; '.join(parts)
        msg+=' | Это гипотезы о словах, НЕ понимание всего предложения.'
        return msg,r
