"""Calculadora didactica DORA sin dependencias externas.

Una fila por publicacion efectiva y un commit representativo por fila.
El CSV completo permite buscar recuperaciones posteriores a la ventana.
"""
import argparse
import csv
import os
import statistics
from datetime import datetime
from pathlib import Path

FIELDS = ['run_id', 'sha', 'commit_at', 'deployed_at', 'failed', 'recovery_of', 'run_url']

def timestamp(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Cada fecha debe incluir Z o un desplazamiento UTC')
    return value

def calculate(path, start, end):
    start, end = timestamp(start), timestamp(end)
    if end <= start:
        raise ValueError('El fin debe ser posterior al inicio')
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            raise ValueError('Encabezado CSV incorrecto')
        rows = list(reader)
    ids = {}
    for row in rows:
        if None in row or any(row[k] is None for k in FIELDS):
            raise ValueError('Fila con cantidad incorrecta de columnas')
        if not row['run_id'] or row['run_id'] in ids:
            raise ValueError('run_id vacio o duplicado')
        if row['failed'] not in ('0', '1'):
            raise ValueError('failed solo admite 0 o 1')
        if not row['sha'] or not row['run_url'].startswith('https://github.com/'):
            raise ValueError('Falta SHA o enlace verificable de GitHub')
        row['commit'] = timestamp(row['commit_at'])
        row['deployed'] = timestamp(row['deployed_at'])
        if row['deployed'] < row['commit']:
            raise ValueError('Publicacion anterior al commit')
        ids[row['run_id']] = row
    recoveries = {}
    for row in rows:
        ref = row['recovery_of']
        if ref:
            if ref not in ids or ids[ref]['failed'] != '1' or row['failed'] != '0':
                raise ValueError('Recuperacion sin incidente valido')
            if ref in recoveries or row['deployed'] <= ids[ref]['deployed']:
                raise ValueError('Recuperacion duplicada o anterior a la falla')
            recoveries[ref] = row
    cohort = [r for r in rows if start <= r['deployed'] < end]
    failed = [r for r in cohort if r['failed'] == '1']
    leads = [(r['deployed'] - r['commit']).total_seconds()/60 for r in cohort]
    durations = [(recoveries[r['run_id']]['deployed'] - r['deployed']).total_seconds()/60
                 for r in failed if r['run_id'] in recoveries]
    return dict(n=len(cohort), days=(end-start).total_seconds()/86400,
                failed=len(failed), pending=len(failed)-len(durations),
                frequency=len(cohort)/((end-start).total_seconds()/86400),
                lead_mean=statistics.mean(leads) if leads else None,
                lead_median=statistics.median(leads) if leads else None,
                cfr=100*len(failed)/len(cohort) if cohort else None,
                recovery=statistics.mean(durations) if durations else None,
                rework=100*sum(bool(r['recovery_of']) for r in cohort)/len(cohort) if cohort else None)

def format_report(r, start, end, title='Informe DORA del laboratorio'):
    fmt = lambda v: 'No calculable' if v is None else f'{v:.2f}'
    return '\n'.join([
        '# ' + title, '', f'Ventana [{start}, {end})', '',
        '| Indicador | Resultado |', '|---|---:|',
        f'| Publicaciones efectivas | {r["n"]} |',
        f'| Duracion de ventana en dias | {r["days"]:.4f} |',
        f'| Frecuencia en publicaciones por dia | {r["frequency"]:.2f} |',
        f'| Lead time promedio en minutos | {fmt(r["lead_mean"])} |',
        f'| Lead time mediano en minutos | {fmt(r["lead_median"])} |',
        f'| Publicaciones con falla | {r["failed"]} |',
        f'| Change failure rate en porcentaje | {fmt(r["cfr"])} |',
        f'| Recuperacion promedio en minutos | {fmt(r["recovery"])} |',
        f'| Incidentes pendientes de recuperacion | {r["pending"]} |',
        '',
        'Recuperacion calculada sobre fallas publicadas en la ventana y ya recuperadas. '
        'Las pendientes se informan por separado. Tiempos aproximados de publicacion; '
        'confirmar salud con la evidencia del sitio.'])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archivo', default='datos/despliegues.csv')
    parser.add_argument('--inicio', required=True)
    parser.add_argument('--fin', required=True)
    parser.add_argument('--titulo', default='Informe DORA del laboratorio')
    args = parser.parse_args()
    try:
        report = format_report(calculate(args.archivo, args.inicio, args.fin), args.inicio, args.fin, args.titulo)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Datos invalidos: {exc}\n')
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text(report, encoding='utf-8')

if __name__ == '__main__':
    main()
