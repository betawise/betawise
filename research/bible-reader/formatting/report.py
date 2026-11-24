"""Produce a compact, provenance-backed summary of passed formatting trials."""
import hashlib
import json
from pathlib import Path
from measure import APP


def collect(paths):
    def read(name):
        result=json.loads((paths[name]/'results.json').read_text())
        assert result['status']=='passed',name
        return result
    source=read('sidecars')
    compact=read('compact')['variants']
    small=read('small')
    word=read('word')
    checks=read('inline_check')
    inline={name:read(name)for name in ['inline_type','inline_all','inline_pred_type','inline_pred_all']}
    head=small['heading_file']['bytes']
    styles=small['variants']['typography/runs']['style_bytes']
    all_styles=small['variants']['all_styles/runs']['style_bytes']
    gamma=compact['kjv-typography-atoms-gamma.bin']['bytes']
    cases={
        'gamma_style_sidecar':gamma+head,
        'inline_style_flags':inline['inline_type']['combined_delta']+head,
        'inline_flags_with_book_defaults':inline['inline_pred_type']['combined_delta']+head,
        'separate_sidecars_with_book_defaults':styles+head,
        'separate_sidecars_with_book_defaults_and_redletter':all_styles+head,
    }
    expected=json.loads((APP/'build/data/kjv/results.json').read_text())['resource_sha256']
    hashes={name:hashlib.sha256((APP/'build/data/kjv'/name).read_bytes()).hexdigest()for name in ['container.bin','search.bin','pruning.bin','verses.bin']}
    assert all(value==expected[name]for name,value in hashes.items())
    return dict(status='passed',scope='Incremental resource data only; formatting renderer is not implemented or priced.',
        kjv_source_audit=source['versions']['kjv']['audit'],comparison_bytes=cases,
        recommended=dict(style_bytes=styles,heading_bytes=head,total_bytes=styles+head,
            including_redletter_bytes=all_styles+head,word_default_table_bytes=45,
            default_word_keys=word['words'],smallcaps_exceptions=762,
            heading_huffman=small['heading_huffman'],source_text_and_index_unchanged=True),
        validation=dict(inline_search_cases=sum(v['production_search_cases']for v in inline.values()),
            inline_atom_checks=sum(v['atoms_checked']for v in checks['trials'].values()),
            production_resource_hashes=hashes,versions_audited=list(source['versions'])),
        artifacts={name:str(path)for name,path in paths.items()})
