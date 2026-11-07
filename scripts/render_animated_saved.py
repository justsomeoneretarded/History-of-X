"""Re-render accepted animated checkpoints with current graphics, preserving request identity."""
from history_of_x.core import read_json
from history_of_x.animated import main
request=read_json('work/animated/request.json')
args=[]
for name in ['title','brief','voice','minutes','profile','preset']:
 args.extend(['--'+name,str(request[name])])
args.extend(['--stage','render'])
raise SystemExit(main(args))
