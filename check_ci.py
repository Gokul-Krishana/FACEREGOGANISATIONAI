import subprocess
import urllib.request
import json
import time

p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
out, _ = p.communicate('protocol=https\nhost=github.com\n\n')
token = ''
for line in out.splitlines():
    if line.startswith('password='):
        token = line.split('=', 1)[1]

def inspect_run(run_id, name):
    print('=== ' + name + ' (Run ID: ' + str(run_id) + ') ===')
    req = urllib.request.Request('https://api.github.com/repos/Gokul-Krishana/FACEREGOGANISATIONAI/actions/runs/' + str(run_id) + '/jobs')
    req.add_header('Authorization', 'Bearer ' + token)
    req.add_header('User-Agent', 'Python-urllib')
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            for job in data.get('jobs', []):
                print('Job:', job.get('name'), '| Status:', job.get('status'), '| Conclusion:', job.get('conclusion'))
                for step in job.get('steps', []):
                    print('  Step:', step.get('name'), '| Status:', step.get('status'), '| Conclusion:', step.get('conclusion'))
    except Exception as e:
        print('Error:', e)

inspect_run('44908110454', 'Linux Build & Compatibility CI')
inspect_run('44908110378', 'Apple iOS Build CI')
