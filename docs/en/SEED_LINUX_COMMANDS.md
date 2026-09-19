# Linux console command handbook

The tag base is built in this order: **processes → files → network → kubectl**. Links like `!proc[1]`, `!file[2]`, `!net[3]`, `!kube[1]` refer to the same command.

**In the app:**
- `?` — list of tags
- `?proc` / `?file` / `?net` / `?kube` — tag commands with tid
- `!proc[1]` — insert the command into the input line
- `!! proc[1]; file[2]` — assemble a chain

**Fill the DB:** `python3 src/seed_linux_commands.py --seed`

---

## proc — processes

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ps aux` | list processes |
| 2 | `top` | interactive process monitor |
| 3 | `htop` | handy monitor (if installed) |
| 4 | `kill` | kill a process by PID |
| 5 | `killall` | kill by name |
| 6 | `pkill` | kill by name pattern |
| 7 | `nohup` | run immune to session disconnect |
| 8 | `jobs` | list shell background jobs |
| 9 | `fg` | bring a job to foreground |
| 10 | `bg` | resume in background |

In the app: `!proc[1]` … `!proc[10]`.

---

## file — files and directories

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ls -la` | list files with details |
| 2 | `cp -r src dest` | recursive copy |
| 3 | `mv src dest` | move or rename |
| 4 | `rm -i` | delete with confirmation |
| 5 | `mkdir -p` | create a directory and parents |
| 6 | `rmdir` | remove an empty directory |
| 7 | `touch` | create an empty file / update time |
| 8 | `cat` | print file contents |
| 9 | `less` | paged view |
| 10 | `head` | first lines of output |
| 11 | `tail -f` | last lines, follow the file |

In the app: `!file[1]` … `!file[11]`.

---

## net — network

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `ss -tulnp` | TCP/UDP sockets (ports) |
| 2 | `ping -c 3` | check host reachability |
| 3 | `curl -sI` | HTTP request, headers only |
| 4 | `wget -qO-` | download to stdout |
| 5 | `ssh` | SSH connection |
| 6 | `rsync -avz` | network sync |
| 7 | `scp` | copy over SSH |
| 8 | `ip addr` | interface addresses |
| 9 | `ip route` | routing table |

In the app: `!net[1]` … `!net[9]`.

---

## kube — Kubernetes (kubectl + tsh)

| tid | Command | Purpose |
|-----|---------|------------|
| 1 | `tsh kube login CLUSTER` | Teleport authorization (`:kctx` remembers NS/POD per cluster) |
| 2 | `kubectl config get-contexts` | list kube contexts |
| 3 | `kubectl config current-context` | current context |
| 4 | `kubectl cluster-info` | cluster info |
| 5 | `kubectl get ns` | list namespaces |
| 6 | `kubectl get all -n $NS` | all resources in namespace `$NS` |
| 7 | `kubectl get pods -n $NS` | pods in namespace `$NS` |
| 8 | `kubectl describe pod $POD -n $NS` | details for pod `$POD` |
| 9 | `kubectl logs $POD -n $NS` | logs of pod `$POD` |
| 10 | `kubectl logs -f $POD -n $NS` | logs of pod `$POD` (follow) |
| 11 | `kubectl exec -it $POD -n $NS -- sh` | exec into pod `$POD` |
| 12 | `kubectl get deploy -n $NS` | deployments in namespace `$NS` |
| 13 | `kubectl describe deploy $DEPLOY -n $NS` | details for deployment `$DEPLOY` |
| 14 | `kubectl rollout status deploy/$DEPLOY -n $NS` | rollout status `$DEPLOY` |
| 15 | `kubectl rollout restart deploy/$DEPLOY -n $NS` | rollout restart `$DEPLOY` |
| 16 | `kubectl get svc -n $NS` | services in namespace `$NS` |
| 17 | `kubectl port-forward svc/$SVC 8080:80 -n $NS` | port-forward to service `$SVC` |
| 18 | `kubectl apply -f FILE.yaml -n $NS` | apply a manifest in namespace `$NS` |
| 19 | `kubectl delete -f FILE.yaml -n $NS` | delete a manifest in namespace `$NS` |

In the app: `!kube[1]` … `!kube[19]`.
