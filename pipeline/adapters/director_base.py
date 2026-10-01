"""Swappable page-level semantics; coordinates remain detector-owned."""
from typing import Protocol
from pipeline.adapters.base import PageAdapter


class DirectorAdapter(PageAdapter,Protocol):
    pass


def fallback(record,reason):
    panels=[]
    for panel in record['panels']:
        texts=[t for t in record['texts'] if t['panel_id']==panel['id']]
        panels.append({'id':panel['id'],'beat':'quiet','shot':'wide','energy':.1,'mood':[],
                       'time_skip':False,'focus':[],
                       'texts':[{'id':t['id'],'kind':'unknown','delivery':'speak','intensity':.2} for t in texts],
                       'sfx':[]})
    return {'summary':'Scene understanding unavailable.', 'panels':panels,
            'needs_review':True,'review_reasons':[reason],'provider':'safe-fallback'}
