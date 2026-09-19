# Linux 常用控制台命令手册

标签库按此顺序构建：**进程 → 文件 → 网络 → kubectl**。`!proc[1]`、`!file[2]`、`!net[3]`、`!kube[1]` 这类链接对应的是同一条命令。

**在应用中：**
- `?` —— 标签列表
- `?proc` / `?file` / `?net` / `?kube` —— 带 tid 的标签命令
- `!proc[1]` —— 把命令插入输入行
- `!! proc[1]; file[2]` —— 组装命令链

**填充数据库：** `python3 src/seed_linux_commands.py --seed`

---

## proc — 进程

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ps aux` | 进程列表 |
| 2 | `top` | 交互式进程监视器 |
| 3 | `htop` | 更易用的监视器（若已安装） |
| 4 | `kill` | 按 PID 结束进程 |
| 5 | `killall` | 按名称结束 |
| 6 | `pkill` | 按名称模式结束 |
| 7 | `nohup` | 启动后不受会话断开影响 |
| 8 | `jobs` | shell 后台任务列表 |
| 9 | `fg` | 把任务调回前台 |
| 10 | `bg` | 在后台继续 |

在应用中：`!proc[1]` … `!proc[10]`。

---

## file — 文件与目录

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ls -la` | 带详情的文件列表 |
| 2 | `cp -r src dest` | 递归复制 |
| 3 | `mv src dest` | 移动或重命名 |
| 4 | `rm -i` | 确认后删除 |
| 5 | `mkdir -p` | 创建目录及父目录 |
| 6 | `rmdir` | 删除空目录 |
| 7 | `touch` | 创建空文件 / 更新时间 |
| 8 | `cat` | 输出文件内容 |
| 9 | `less` | 分页查看 |
| 10 | `head` | 输出的前几行 |
| 11 | `tail -f` | 最后几行，跟踪文件 |

在应用中：`!file[1]` … `!file[11]`。

---

## net — 网络

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `ss -tulnp` | TCP/UDP 套接字（端口） |
| 2 | `ping -c 3` | 检查主机可达性 |
| 3 | `curl -sI` | HTTP 请求，仅头部 |
| 4 | `wget -qO-` | 下载到 stdout |
| 5 | `ssh` | SSH 连接 |
| 6 | `rsync -avz` | 网络同步 |
| 7 | `scp` | 通过 SSH 复制 |
| 8 | `ip addr` | 接口地址 |
| 9 | `ip route` | 路由表 |

在应用中：`!net[1]` … `!net[9]`。

---

## kube — Kubernetes (kubectl + tsh)

| tid | 命令 | 用途 |
|-----|---------|------------|
| 1 | `tsh kube login CLUSTER` | Teleport 授权（`:kctx` 按集群记住 NS/POD） |
| 2 | `kubectl config get-contexts` | kube context 列表 |
| 3 | `kubectl config current-context` | 当前 context |
| 4 | `kubectl cluster-info` | 集群信息 |
| 5 | `kubectl get ns` | namespace 列表 |
| 6 | `kubectl get all -n $NS` | namespace `$NS` 中的所有资源 |
| 7 | `kubectl get pods -n $NS` | namespace `$NS` 中的 Pod |
| 8 | `kubectl describe pod $POD -n $NS` | pod `$POD` 的详情 |
| 9 | `kubectl logs $POD -n $NS` | pod `$POD` 的日志 |
| 10 | `kubectl logs -f $POD -n $NS` | pod `$POD` 的日志（follow） |
| 11 | `kubectl exec -it $POD -n $NS -- sh` | Exec 进入 pod `$POD` |
| 12 | `kubectl get deploy -n $NS` | namespace `$NS` 中的 Deployments |
| 13 | `kubectl describe deploy $DEPLOY -n $NS` | deployment `$DEPLOY` 的详情 |
| 14 | `kubectl rollout status deploy/$DEPLOY -n $NS` | rollout `$DEPLOY` 的状态 |
| 15 | `kubectl rollout restart deploy/$DEPLOY -n $NS` | 重启 rollout `$DEPLOY` |
| 16 | `kubectl get svc -n $NS` | namespace `$NS` 中的 Services |
| 17 | `kubectl port-forward svc/$SVC 8080:80 -n $NS` | 到 service `$SVC` 的 port-forward |
| 18 | `kubectl apply -f FILE.yaml -n $NS` | 在 namespace `$NS` 中应用清单 |
| 19 | `kubectl delete -f FILE.yaml -n $NS` | 在 namespace `$NS` 中删除清单 |

在应用中：`!kube[1]` … `!kube[19]`。
