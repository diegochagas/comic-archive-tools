#!/usr/bin/env python3
"""Build + run a Higgsfield generation for one ai-comics page job.
Usage: gen_page.py <project> <issue> <page> <try> [--cost]
Prints the local PNG path (or cost) to stdout. Auth/env come from ~/hf-env/env.sh.
"""
import sys, os, json, subprocess, urllib.request, tempfile

ROOT = '/sessions/adoring-practical-pascal/mnt/ai-comics'
HF = os.path.expanduser('~/hf/node_modules/.bin/higgsfield')

def build_prompt(job):
    letter = job.get('lettering', 'ai')
    lang = {'en': 'English', 'pt-BR': 'Brazilian Portuguese'}.get(job.get('language', 'en'), 'English')
    if letter == 'ai':
        suffix = (f"\n\nRender ALL dialogue and captions in {lang} EXACTLY as written, "
                  "letter by letter, inside the balloons/captions. Comic book page, portrait. "
                  "Character appearance must match the attached reference images for identity, "
                  "but the drawing style must follow the base style described above. "
                  "CRITICAL: the ONLY text anywhere on the page is the exact dialogue and caption "
                  "strings specified above. Do NOT print any character names, role labels, scene "
                  "titles, stage directions, panel notes, or descriptive words as text on the art "
                  "(e.g. never draw the words 'Young Ryo', 'Blink', 'STYLE', 'PAGE', or any label). "
                  "Caption and location boxes contain ONLY the exact caption strings listed above — "
                  "never insert setting, scene, or 'STYLE:' descriptions into a caption box, and "
                  "never prepend/append extra words to a caption. Spell every word correctly. "
                  "No watermarks, no signatures, no page numbers.")
    else:
        suffix = ("\n\nIMPORTANT — DO NOT RENDER ANY TEXT. Draw every balloon/caption in the correct "
                  "position and shape but leave it COMPLETELY EMPTY white. Comic book page, portrait.")
    return job['preamble'] + "\n\n" + job['prompt'] + suffix

def refs(project, job):
    base = os.path.join(ROOT, 'projects', project, 'refs')
    out = []
    for f in job.get('model_sheets', []):
        p = os.path.join(base, 'model-sheets', f)
        if os.path.exists(p): out.append(p)
    for f in job.get('style_refs', []):
        p = os.path.join(base, 'style', f)
        if os.path.exists(p): out.append(p)
    # extra continuity refs passed via env EXTRA_REFS (colon-separated absolute paths)
    for p in filter(None, os.environ.get('EXTRA_REFS', '').split(':')):
        if os.path.exists(p): out.append(p)
    return out[:14]

def main():
    project, issue, page, tryk = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    cost_only = '--cost' in sys.argv[5:]
    override = os.environ.get('PROMPT_OVERRIDE_FILE')  # optional: reroll with edited prompt
    job = json.load(open(os.path.join(ROOT, 'projects', project, 'jobs', issue, f'page_{page:02d}.json')))
    # strip the "=== PAGE N — TITLE ===" header line so it can't leak onto the art
    import re as _re
    job['prompt'] = _re.sub(r'^\s*===\s*PAGE\b.*?===\s*\n?', '', job['prompt'], count=1, flags=_re.I)
    # neutralize the style-label token so the model can't print "RYO STYLE" on the page
    for k in ('prompt', 'preamble'):
        job[k] = _re.sub(r'\bRYO STYLE\b', 'the established art style', job[k])
    prompt = open(override).read() if override else build_prompt(job)
    aspect = job.get('aspect', '2:3')
    reflist = refs(project, job)

    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as tf:
        tf.write(prompt); pf = tf.name
    cmd = [HF, 'generate', ('cost' if cost_only else 'create'), 'nano_banana_pro',
           '--prompt', f'@{pf}' if False else prompt,
           '--aspect_ratio', aspect, '--resolution', '2k', '--json']
    for r in reflist:
        cmd += ['--image-references', r]
    if not cost_only:
        cmd += ['--wait', '--wait-timeout', '10m']

    if cost_only:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        print(res.stdout.strip() or res.stderr.strip()); return
    # retry transient failures (503 service-unavailable, intermittent nsfw filter)
    out = ''
    for attempt in range(4):
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = (res.stdout or '').strip()
        err = (res.stderr or '').strip() + ' ' + out
        if res.returncode == 0 and out:
            break
        if any(t in err.lower() for t in ('503', 'service unavailable', 'nsfw', 'timeout', 'temporarily')):
            import time as _t; _t.sleep(4); continue
        print('ERROR', res.returncode, err[:500]); sys.exit(1)
    else:
        print('ERROR retries-exhausted', err[:300]); sys.exit(1)
    # parse JSON for result url
    url = None
    try:
        data = json.loads(out)
        def find_url(o):
            if isinstance(o, str) and o.startswith('http') and any(o.lower().split('?')[0].endswith(e) for e in ('.png','.jpg','.jpeg','.webp')):
                return o
            if isinstance(o, dict):
                for v in o.values():
                    u = find_url(v)
                    if u: return u
            if isinstance(o, list):
                for v in o:
                    u = find_url(v)
                    if u: return u
            return None
        url = find_url(data)
    except Exception as e:
        print('PARSE_FAIL', str(e), out[:400]); sys.exit(1)
    if not url:
        print('NO_URL', out[:400]); sys.exit(1)
    gendir = os.path.join(ROOT, 'projects', project, 'work', issue, 'gen')
    os.makedirs(gendir, exist_ok=True)
    dst = os.path.join(gendir, f'page_{page:02d}_try{tryk}.png')
    urllib.request.urlretrieve(url, dst)
    print(dst)

if __name__ == '__main__':
    main()
