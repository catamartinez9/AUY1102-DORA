"""Registra una publicacion completada; la salud se comprueba en el navegador."""
import csv
import io
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ['run_id', 'sha', 'commit_at', 'deployed_at', 'failed', 'recovery_of', 'run_url']

def record():
    commit_at = subprocess.check_output(
        ['git', 'show', '-s', '--format=%cI', 'HEAD'], text=True).strip()
    base = os.environ['GITHUB_SERVER_URL']
    repo = os.environ['GITHUB_REPOSITORY']
    run_id = os.environ['GITHUB_RUN_ID']
    row = [run_id, os.environ['GITHUB_SHA'], commit_at,
           datetime.now(timezone.utc).isoformat(timespec='seconds'),
           '0', '', f'{base}/{repo}/actions/runs/{run_id}']
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    writer.writerow(FIELDS)
    writer.writerow(row)
    result = ('## Registro de publicacion\n\n'
              'Confirma la funcion Reservar en el sitio publicado. '
              'failed=0 es provisional; usa 1 si requiere recuperacion.\n\n'
              '```csv\n' + buf.getvalue() + '```\n\n'
              'deployed_at se toma inmediatamente despues de deploy-pages; '
              'es una aproximacion del momento de publicacion.\n')
    Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(result, encoding='utf-8')
    print(result)

if __name__ == '__main__':
    record()
