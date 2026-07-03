from __future__ import annotations
from pathlib import Path
import os, shutil, subprocess, tempfile

def render_docx(docx:Path,out_dir:Path,dpi:int=300)->tuple[int,str,str,Path|None,list[Path]]:
    out_dir.mkdir(parents=True,exist_ok=True)
    home=Path(tempfile.mkdtemp(prefix='wdp_lo_home_')); profile=Path(tempfile.mkdtemp(prefix='wdp_lo_profile_'))
    env=os.environ.copy(); env['HOME']=str(home); env['XDG_CACHE_HOME']=str(home/'cache'); env['XDG_CONFIG_HOME']=str(home/'config')
    lo=shutil.which('libreoffice') or shutil.which('soffice')
    if not lo: return 127,'','LibreOffice not installed',None,[]
    cmd=[lo,'-env:UserInstallation=file://'+str(profile),'--headless','--convert-to','pdf','--outdir',str(out_dir),str(docx)]
    p=subprocess.run(cmd,text=True,capture_output=True,env=env,timeout=180)
    pdf=out_dir/(docx.stem+'.pdf')
    if p.returncode!=0 or not pdf.exists(): return p.returncode,p.stdout,p.stderr,pdf if pdf.exists() else None,[]
    prefix=out_dir/'page'; pdftoppm=shutil.which('pdftoppm')
    if not pdftoppm: return 127,p.stdout,p.stderr+'\npdftoppm not installed',pdf,[]
    q=subprocess.run([pdftoppm,'-png','-r',str(dpi),str(pdf),str(prefix)],text=True,capture_output=True,timeout=300)
    pages=sorted(out_dir.glob('page-*.png'),key=lambda x:int(x.stem.split('-')[-1]))
    return q.returncode,p.stdout+'\n'+q.stdout,p.stderr+'\n'+q.stderr,pdf,pages
