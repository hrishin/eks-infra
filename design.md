# Edge Kubernetes Fleet Management for Inference Models
### System Design Reference · v1.0

---

## Part 0 — Requirements Discovery

> Before committing to any architecture, these questions must be answered. Every answer changes the design materially.

---

### 0.1 Workload & Model Requirements

| # | Question | Why It Matters |
|---|----------|----------------|
| 1 | What model sizes are you targeting? (7B, 13B, 70B, 405B+) | Determines minimum GPU memory per node and whether tensor/pipeline parallelism is needed |
| 2 | What modality? (text, vision, multimodal, audio) | Affects runtime choice — vLLM vs Triton vs custom |
| 3 | What is the expected input/output context length (tokens)? | KV cache sizing, memory per request, max concurrent sessions |
| 4 | Do you need multiple model variants per site, or one model per site? | Affects scheduling model — multi-LoRA, separate deployments, or time-sliced MIG |
| 5 | Is this batch inference, online (real-time), or both? | Latency SLOs, autoscaling strategy, queue depth tolerance |
| 6 | What are your latency SLOs? (TTFT, TPOT, end-to-end p99) | Gateway timeout config, KEDA thresholds, alerting thresholds |
| 7 | Do you need streaming responses (SSE / chunked HTTP)? | Gateway must support streaming; affects load balancer choice |
| 8 | What is the expected requests/sec per site? Peak vs sustained? | Sizing GPU nodes, autoscaler min/max replica counts |

---

### 0.2 Fleet Scale & Topology

| # | Question | Why It Matters |
|---|----------|----------------|
| 9 | How many edge sites total? Now and in 3 years? | Determines fleet management tooling — Rancher Fleet, Anthos, Arc, or homegrown |
| 10 | How are sites geographically distributed? (country, region, datacenter, on-prem, on-device?) | Impacts data sovereignty, latency routing, certificate authority design |
| 11 | Are edge sites homogeneous (same hardware) or heterogeneous? | Heterogeneous fleets need node labelling, tolerations, and hardware-aware scheduling |
| 12 | What is the expected WAN bandwidth and latency per site? | Model distribution strategy, Prometheus remote_write cadence, GitOps sync interval |
| 13 | Do sites need to operate fully offline (air-gapped / intermittent)? | Changes GitOps to pull-only, requires local model cache, offline certificate rotation |
| 14 | Is there a hub/spoke hierarchy, or is every site equal? | Fleet topology pattern — centralised control vs federated vs autonomous |

---

### 0.3 Hardware & Infrastructure

| # | Question | Why It Matters |
|---|----------|----------------|
| 15 | What GPU hardware is available at edge? (NVIDIA A100, H100, L40S, RTX, Jetson, AMD, none?) | Determines runtime (CUDA vs ROCm vs CPU), MIG support, NVLINK topology |
| 16 | Are nodes bare metal, virtualised, or cloud-managed (EKS Anywhere, GKE Edge)? | Affects GPU passthrough method, control plane HA options, node replacement strategy |
| 17 | What is the node count per edge site? Single node or multi-node cluster? | Single-node = no HA; multi-node = etcd quorum, needs 3 control plane nodes |
| 18 | Is there local persistent storage? NVMe, SAN, NAS? | Model weight caching, KV cache persistence, PVC provisioner choice |
| 19 | What CPU/RAM budget per edge node? | K3s overhead is ~500MB RAM; inference server overhead above GPU memory |
| 20 | Is ARM64 (Jetson, Graviton) in scope? | Multi-arch container images required; some operators don't support ARM64 |

---

### 0.4 Operations & Team

| # | Question | Why It Matters |
|---|----------|----------------|
| 21 | Who operates the edge sites? Central SRE team or on-site staff? | Runbook complexity, remote access design, automation vs manual intervention tolerance |
| 22 | What is the on-call model? 24×7, business hours, follow-the-sun? | Alerting routing, escalation policy, MTTR targets |
| 23 | What is your existing K8s maturity? Do teams know Flux/ArgoCD? | Tooling selection; avoid introducing too many new abstractions at once |
| 24 | What is your change velocity? How often are models updated? | GitOps pipeline design, canary strategy, rollback SLA |
| 25 | Do you have a CI/CD platform today? (Jenkins, GitHub Actions, Tekton?) | Pipeline integration points for model packaging and fleet rollout |
| 26 | What observability stack exists? (Datadog, Grafana, ELK, custom?) | Determines whether to integrate or build new; remote_write target, log sink |

---

### 0.5 Security & Compliance

| # | Question | Why It Matters |
|---|----------|----------------|
| 27 | Do workloads process regulated data? (PII, HIPAA, GDPR, financial?) | Data residency constraints, audit logging, namespace isolation |
| 28 | Is there a requirement that model weights never leave a specific jurisdiction? | Affects model registry location, distribution architecture |
| 29 | What is the identity and access model? (OIDC, LDAP, manual kubeconfig?) | K8s RBAC design, service account strategy, human access controls |
| 30 | Are there supply chain security requirements? (SBOM, image signing, Sigstore?) | CI/CD pipeline additions, admission webhook policy |
| 31 | Is SSH access to nodes acceptable, or must it be API-only? | Talos vs standard OS; shapes the break-glass procedure |
| 32 | Any existing secret management system? (Vault, AWS SSM, CyberArk?) | ESO integration vs SOPS vs Vault Agent — influences day-0 bootstrapping |

---

### 0.6 Cost & Commercial

| # | Question | Why It Matters |
|---|----------|----------------|
| 33 | Is there a per-site hardware budget cap? | Determines if full NVIDIA GPU Operator is affordable vs manual DaemonSet |
| 34 | Is this greenfield or migrating from an existing inference platform? | Migration path complexity, dual-run period, cutover risk |
| 35 | Are there commercial tooling constraints? (open-source only? existing enterprise licenses?) | Rancher vs Anthos vs Arc; open-source-only changes several component choices |
| 36 | What is the SLA commitment to downstream consumers of the inference API? | Determines acceptable availability budget, failover architecture |

---

### 0.7 Key Architecture Decision Points (Derived from Answers Above)

Once answers are collected, the following decisions are unlocked:

```
Connectivity model        → Flux pull-only  OR  ArgoCD push  OR  hybrid
K8s distro at edge        → K3s (resource-light)  OR  RKE2 (hardened)  OR  MicroK8s  OR  EKS Anywhere
Model distribution        → OCI artifact  OR  Dragonfly P2P  OR  S3 presigned  OR  pre-baked node image
GPU scheduling            → Whole GPU  OR  MIG partitioning  OR  time-slicing  OR  CPU fallback
Autoscaling trigger       → KEDA on queue depth  OR  HPA on GPU util  OR  no autoscaling (fixed capacity)
Secret management         → SOPS+Age (air-gap)  OR  Vault Agent (online)  OR  Sealed Secrets
Observability collection  → Prometheus Agent remote_write  OR  Grafana Alloy  OR  Datadog Agent
Fleet control plane       → Rancher Fleet  OR  Anthos  OR  Azure Arc  OR  Cluster API DIY
```

---

## Part 1 — System Architecture

---

### 1.1 Architecture Overview

The recommended pattern is a **three-tier hub-and-spoke architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 1 — Central Control Plane (Cloud / Main DC)           │
│  Fleet mgmt · GitOps · Model Registry · Global Observability│
│  Secret Management · Policy Engine · CI/CD Pipelines        │
└──────────────────────────┬──────────────────────────────────┘
                           │  WAN (HTTPS/mTLS)
┌──────────────────────────▼──────────────────────────────────┐
│  TIER 2 — Regional Hub (×R)                                  │
│  Regional K8s · OCI Model Cache · Traffic Gateway           │
│  Regional Prometheus · Edge Bootstrap Service · CA          │
└──────────────────────────┬──────────────────────────────────┘
                           │  WAN (intermittent ok)
┌──────────────────────────▼──────────────────────────────────┐
│  TIER 3 — Edge Site (×N)                                     │
│  K3s/RKE2 · vLLM/TGI · GPU Operator · Prometheus Agent     │
│  Fluent Bit · Envoy Gateway · Model PVC · Watchdog DS       │
└─────────────────────────────────────────────────────────────┘
```

Edge sites pull desired state from git (Flux agent). Model weights are distributed regionally to avoid saturating WAN. Inference is always served locally — regional/central are **fallbacks**, not the primary path.

---

### 1.2 Fleet Topology Patterns

| Pattern | Description | Best For | Trade-off |
|---------|-------------|----------|-----------|
| **Hub-and-Spoke** | Central management plane; edges pull config downstream | Retail, telco, manufacturing | Hub is single source of config authority |
| **Flat Federation** | All clusters peer-managed via KubeFed / Liqo | Research grids, sovereign edge | Harder to enforce global policy uniformly |
| **Autonomous Edge** | Clusters operate offline; sync when connected | Ships, remote sites, air-gapped | Config drift; delayed rollouts; requires local git mirror |

**Recommendation:** Start with Hub-and-Spoke. Autonomous capability is addable via Flux's offline reconciliation mode — design for it from day 0 even if not needed immediately.

---

### 1.3 Inference Request Flow

```
Client → Edge Envoy Gateway → AuthN/Rate Limit → Inference Service (vLLM)
      → GPU Worker Pool → KV Cache Lookup → Streamed Token Response

Fallback chain: edge vLLM → regional hub vLLM → central cluster vLLM
```

- **P99 TTFT target:** <200ms (online) / no SLO (batch)
- **Batching:** continuous batching (vLLM default)
- **AuthN:** mTLS (pod-to-pod) + JWT (external clients)
- **Failover:** weighted routing at Envoy gateway; automatic on health check failure

---

### 1.4 Component Reference

| Component | Primary Choice | Purpose | Edge Consideration |
|-----------|---------------|---------|-------------------|
| Fleet Control Plane | Rancher + Fleet | Cluster lifecycle, config distribution | Lightweight agent on edge; control plane lives in cloud |
| GitOps Engine | FluxCD v2 | Desired state management | Pull model — no inbound firewall rules at edge |
| K8s Distribution | K3s | Edge cluster runtime | ~70MB binary, SQLite or embedded etcd, CNCF certified |
| Inference Engine | vLLM | Serve LLM tokens | PagedAttention, continuous batching, OpenAI-compat API |
| Model Distribution | Dragonfly P2P | Push weights to edge sites | P2P avoids bandwidth bottleneck when pulling same large shard across N sites |
| GPU Operator | NVIDIA GPU Operator | Driver, toolkit, DCGM, device plugin | Pin operator version; match driver to CUDA requirement for model |
| Autoscaling | KEDA | Scale replicas on inference queue depth | ScaledObject on `vllm:num_requests_waiting`; handles scale-to-zero |
| Metrics | Prometheus Agent + Thanos | Metrics collection | Agent mode: remote_write only, no local TSDB storage at edge |
| Logging | Fluent Bit + Loki | Log aggregation | <50MB RAM; structured JSON; filter debug logs before shipping |
| Tracing | OpenTelemetry + Tempo | Distributed traces | OTEL vendor-neutral; Tempo stores on object storage cheaply |
| Secrets | SOPS+Age / Vault Agent | Credentials, certificates | SOPS for air-gapped sites; Vault Agent for online sites |
| Policy | Kyverno | Admission control | Native K8s YAML policies; easier to maintain than OPA Rego |
| Ingress | Envoy Gateway | Edge request routing | Supports SSE streaming for token responses |
| CNI | Cilium | Networking + policy | eBPF; low overhead; built-in network policy and observability |
| Node OS | Talos Linux | Immutable node OS | API-only; no SSH; read-only rootfs; purpose-built for K8s |

---

## Part 2 — Design Considerations

---

### 2.1 Connectivity & Disconnected Operations

- **Design for intermittent WAN.** Edge clusters must serve inference without any central connectivity. This is a hard requirement, not an edge case.
- **Flux pull model** — agent polls git repo on a configurable interval (default: 1 minute). No inbound connections required from central to edge.
- **Sync budget** — define acceptable config drift window (e.g., 5-minute reconcile loop). Alert if an edge cluster has not reconciled in >3× its normal interval.
- **Model pre-caching** — weights must be fully present on the local PVC before the site can be considered healthy. Include a model readiness check in the site bootstrap pipeline.
- **Fallback chains** — implement at the Envoy Gateway level with weighted clusters: local (primary), regional hub (secondary), central (tertiary).
- **Heartbeat protocol** — a lightweight keepalive daemonset (or Rancher Fleet agent) reports site status even during degraded mode when full metrics are unavailable.

---

### 2.2 Model Lifecycle Management

- **Immutable model artifacts** — tag by SHA256 hash, never overwrite a version tag. Treat model weights like container images.
- **OCI artifact standard** — package model shards as OCI layers. Benefit: registry-level deduplication, pull-by-digest, standard tooling.
- **Staged rollout** — canary to one site (5% of fleet), then progressive wave expansion. Automated rollback if SLO breach detected within the observation window.
- **Model size tiers** — maintain fast (7B), balanced (13B), accurate (70B) variants. The tier deployed to a site depends on its GPU class (node label).
- **LoRA adapter management** — vLLM multi-LoRA: one base model loaded, multiple adapters hot-swapped per request. Avoids full model reload on adapter updates.
- **Quantised variants** — AWQ / GPTQ / INT4 for memory-constrained nodes. Define a quantisation policy per node tier in the HelmRelease values.

---

### 2.3 Hardware Heterogeneity

- **Node labels per GPU type** — `nvidia.com/gpu.product`, `nvidia.com/gpu.memory`, `nvidia.com/mig.capable`. Use these in pod `nodeSelector` or `nodeAffinity`.
- **MIG partitioning** — A100 / H100 support Multi-Instance GPU. Partition 80GB A100 into 2× MIG 3g.40gb for two independent 40GB inference contexts.
- **CPU fallback** — llama.cpp or ONNX Runtime for sites without GPU. Maintain a separate HelmRelease values overlay for CPU-only sites.
- **ARM64 support** — Jetson Orin, AWS Graviton. Requires multi-arch container images (`docker buildx`). Not all operators have ARM64 support — audit before committing.
- **Thermal management** — monitor `DCGM_FI_DEV_GPU_TEMP`. Alert at 85°C. Implement load shedding at 90°C. Edge sites may lack datacenter-grade cooling.

---

### 2.4 Security & Zero Trust

- **mTLS everywhere** — Cilium or Istio Ambient for pod-to-pod. No implicit trust inside the cluster.
- **Short-lived certificates** — SPIFFE/SPIRE for workload identity. Maximum 24-hour certificate TTL. Auto-rotate via cert-manager.
- **Policy enforcement** — Kyverno ClusterPolicies: enforce `securityContext`, no privileged containers, no `hostNetwork`, GPU resource limits required.
- **Supply chain** — sign all images with Cosign. Enforce signature verification via Kyverno `verifyImages` rule. No unsigned images schedule.
- **Air-gap readiness** — mirror all images to private OCI registry before deployment. Rancher Fleet bundles should be fully self-contained.
- **Audit logging** — K8s API server audit logs forwarded to central SIEM. GPU driver events from DCGM included.

---

### 2.5 Inference Performance

- **PagedAttention (vLLM)** — eliminates KV cache memory fragmentation. Critical for high-concurrency edge workloads. Do not use inference runtimes without this.
- **Continuous batching** — vLLM default. Never leaves GPU idle waiting for a fixed batch window to close.
- **Tensor parallelism** — split large model across multiple GPUs on the same node (`--tensor-parallel-size N`). Use for models exceeding single-GPU memory.
- **Pipeline parallelism** — distribute model layers across nodes for 70B+ on smaller GPUs. Requires fast interconnect (NVLink or InfiniBand). Poor on commodity edge hardware — prefer quantised single-GPU variants instead.
- **NUMA awareness** — pin GPU inference pods to the NUMA node local to the GPU. Use `topologyManager` policy `single-numa-node`.
- **Huge pages** — 1GB huge pages for model weight loading. Reduces TLB pressure during prefill phase.

---

### 2.6 Autoscaling Strategy

- **KEDA on `vllm:num_requests_waiting`** — scale out when queued requests exceed threshold (e.g., 10 waiting → add replica).
- **Scale-to-zero with warm pool** — keep minimum 1 pod running per site. Cold start for a 70B model is 60–120 seconds. Scale-to-zero is only viable for batch or non-latency-sensitive workloads.
- **GPU ResourceQuota** — prevent a single tenant namespace from consuming all GPU capacity on a shared site.
- **Do not fight HPA and KEDA simultaneously** — use KEDA for primary trigger; VPA for CPU/RAM right-sizing of sidecar containers only.
- **Predictive scaling** — for known traffic patterns (e.g., business hours), use KEDA `cron` scaler to pre-warm replicas before demand arrives.
- **Burst to cloud** — Envoy Gateway weighted routing: when local queue exceeds burst threshold, route overflow to regional hub.

---

### 2.7 Data Sovereignty & Compliance

- **Request locality enforcement** — gateway policy must prevent PII workload requests from crossing jurisdictional boundaries, even in failover.
- **Model residency** — regulated industries may require model weights to physically reside in a specific country. The model registry and edge PVC location must comply.
- **Prompt audit logging** — log prompt SHA256 hashes (not content) for compliance traceability without storing sensitive data.
- **Egress control** — Cilium `CiliumNetworkPolicy` to block unexpected outbound connections. An inference model must not make external network calls.
- **Workload isolation** — separate namespaces with dedicated node pools for GDPR/HIPAA workloads. Enforce via Kyverno node affinity policy.

---

### 2.8 Cluster Bootstrapping (Day 0)

- **Zero-touch provisioning pipeline:** `PXE boot → cloud-init → K3s install → Flux bootstrap → model pull job`
- **Cluster API** — declarative cluster lifecycle management. Each edge site is a `Cluster` CR in the central management cluster. Operator-driven provisioning.
- **Bootstrap token rotation** — single-use join tokens. Rotate immediately after cluster joins the fleet.
- **Day 0 policy enforcement** — Kyverno policies installed before any workload namespace is created. Admission webhook active from first workload.
- **Immutable node OS** — Talos Linux or Flatcar Container Linux. Read-only rootfs, API-only access. No SSH in production.

---

### 2.9 Observability Architecture

- **Prometheus Agent mode** — runs as a scraper + remote_write forwarder only. No local TSDB. Minimal memory footprint at edge (~50–100MB).
- **Thanos Receive** — regional ingestion endpoint. Thanos Query provides a global view across all edge sites from central.
- **GPU metrics via DCGM Exporter** — exposes `DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_GPU_TEMP`, `DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL`.
- **vLLM metrics** — `vllm:e2e_request_latency_seconds`, `vllm:num_requests_running`, `vllm:num_requests_waiting`, `vllm:gpu_cache_usage_perc`.
- **Fluent Bit at edge** — tail container logs, apply structured JSON filter, drop debug-level logs before shipping to Loki to reduce bandwidth.
- **OpenTelemetry traces** — per-request trace spanning gateway → inference pod → GPU kernel. Enables profiling of prefill vs decode phase latency.

---

### 2.10 Cost & Resource Efficiency

| Principle | Implementation |
|-----------|----------------|
| GPU utilisation target | 75–85% sustained. Below 60% = over-provisioned. Above 90% = latency degradation begins. |
| Bin-packing | MIG on A100/H100 to run multiple tenants per GPU. LimitRange to prevent runaway allocations. |
| Model sharing | vLLM multi-LoRA: one base model in memory, multiple LoRA adapters per request. |
| Idle site hibernation | Scale inference to 0 overnight via KEDA cron scaler. Keep K8s control plane alive. |
| Spot / preemptible nodes | Inference is stateless. Safe to run batch inference on spot. Online inference needs on-demand. |
| Memory formula | `GPU_memory_needed = parameters × dtype_bytes × 1.2` (KV cache overhead factor) |

**Example:** Llama-3-70B in FP16 = 70B × 2 bytes × 1.2 ≈ 168GB → minimum 2× A100 80GB.

---

## Part 3 — SRE Operations

---

### 3.1 SLOs & Error Budget

| Signal | SLO | Measurement |
|--------|-----|-------------|
| Availability | 99.5% | Successful inference requests / total requests (30-day rolling) |
| Latency (TTFT) | P99 < 200ms | `vllm:e2e_request_latency_seconds` histogram |
| Error rate | < 0.5% | 5xx responses / total requests |
| Model rollout time | < 30 minutes | Time from git tag to 100% fleet deployed |
| Detection to alert | < 5 minutes | Alert firing delay from SLO breach |
| MTTR | < 2 hours | Incident open to resolved |

**Error budget:** 99.5% = 3.65 hours/month per cluster. Spend it on planned maintenance, not incidents.

---

### 3.2 Golden Signals Dashboard

| Signal | Metric | Alert Condition |
|--------|--------|----------------|
| Latency | `vllm:e2e_request_latency_seconds` p99 | > 500ms for 5 minutes |
| Traffic | `rate(vllm:request_success_total[5m])` | Drop > 30% vs 1-hour baseline |
| Errors | `vllm:request_failure_total / total` | > 1% error rate |
| GPU Saturation | `DCGM_FI_DEV_GPU_UTIL` | > 92% for 10 minutes |
| Queue Depth | `vllm:num_requests_waiting` | > 50 pending requests |
| GPU Memory | `DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL` | > 95% |
| KV Cache Hit | `vllm:gpu_cache_usage_perc` | < 10% (cold cache after restart, expected transiently) |

---

### 3.3 Rollout Strategy — GitOps Progressive Waves

```
Stage 0: staging cluster
  → automated benchmark vs baseline (throughput, TTFT, accuracy regression)
  → gate: no regression > 5% on any signal

Stage 1: canary — 1 site (5% of fleet)
  → observe for 30 minutes
  → gate: error rate < 0.5%, P99 TTFT within SLO

Stage 2: 25% of fleet
  → automated rollback if SLO breach detected within observation window

Stage 3: 100% of fleet
  → Flux HelmRelease wave annotations control deployment ordering

Rollback SLA: < 5 minutes via Flux revert. No human intervention required.
```

Use `fluxcd.io/ignore: "true"` annotation on a HelmRelease to pause a specific site during operations without affecting the rest of the fleet.

---

### 3.4 Incident Response

#### P1 — Inference Fully Down (error rate > 5%)

| Time | Action |
|------|--------|
| T+0m | Envoy Gateway auto-fails over to regional hub |
| T+2m | SRE paged. Check pod status, GPU health via `kubectl describe` |
| T+5m | Restart inference pod if OOMKilled / CrashLoopBackOff |
| T+10m | If GPU XID error: cordon node, drain, reschedule |
| T+15m | If unresolved: invoke model rollback via git revert |
| T+30m | Escalate to platform team if no resolution |

#### P2 — Degraded Performance (P99 > 2× baseline for 5 min)

1. Check queue depth — is KEDA scaling correctly?
2. Check GPU memory fragmentation — rolling restart of vLLM pod if needed
3. Verify no noisy neighbour via MIG / namespace ResourceQuota
4. Check KV cache hit rate — cold cache after restart is expected and transient
5. Consider manual `kubectl scale` to add replicas ahead of KEDA reaction

#### P3 — Site Disconnected (no heartbeat for > 2 min)

1. Verify: is the site still serving inference locally? (autonomous mode is expected)
2. Check WAN link, VPN tunnel status, DNS resolution from site
3. **Do not push config changes to disconnected site** — wait for reconnection
4. On reconnect: force `flux reconcile` and review drift report

---

### 3.5 Change Management

| Change Type | Gate | Rollout Method |
|-------------|------|----------------|
| Model version bump | Automated benchmark CI gate | Progressive GitOps wave |
| K8s config change | PR review + `--dry-run=server` validation | Env → Staging → Prod |
| K8s version upgrade | CAB approval | One cluster at a time, rolling |
| GPU driver update | Hardware lab test | Maintenance window, node-by-node |
| CNI change | Network team sign-off | Blue/green cluster swap |
| Security emergency patch | SRE lead + incident manager only | Direct to prod with post-hoc PR |

---

### 3.6 Capacity Planning

- **GPU utilisation review:** weekly. Trigger provisioning planning at 60% sustained utilisation.
- **Traffic growth baseline:** compare week-on-week. If > 20% growth trend, initiate hardware procurement.
- **Model upgrade impact:** when moving to a larger model (e.g., 7B → 13B), recalculate GPU memory budget before rollout. Never surprise an edge site with a model that doesn't fit.
- **Failure headroom:** always maintain spare GPU capacity for model reload during restarts. Never design for 100% utilisation.

---

### 3.7 Toil Reduction & Automation Targets

| Toil | Automation |
|------|------------|
| OOMKilled pod | Auto-restart + VPA recommendation generated |
| GPU XID error | Auto-cordon node + page SRE |
| High queue depth | KEDA auto-scale-out |
| Certificate expiry | cert-manager auto-renew at 7 days remaining |
| Disconnected site reconnect | Auto-trigger `flux reconcile` on heartbeat restoration |
| Stale model weights | Nightly checksum verification job; alert on mismatch |

---

### 3.8 SRE Anti-Patterns — What Not to Do

- **Do not SSH to edge nodes for debugging.** Use `kubectl exec` only. SSH access disables auditability and breaks immutable OS guarantees.
- **Do not manually copy model weights.** Always use the model distribution pipeline. Manual copying creates undocumented state.
- **Do not run mutable node OS.** Talos or Flatcar only. `apt install` on a production GPU node is a future incident.
- **Do not store secrets in git unencrypted.** SOPS or ESO always. No exceptions.
- **Do not disable alerts during incidents.** Silence the alert for the specific symptom. Never globally disable.
- **Do not skip staging.** A canary deployment to one production site is not a substitute for staging validation.
- **Do not mix HPA and KEDA on the same Deployment.** They will fight each other. KEDA exclusively for inference pods.

---

## Part 4 — Runbooks

---

### RB-001 — GPU OOM / vLLM CrashLoopBackOff

**Symptoms:** Pod in CrashLoopBackOff or OOMKilled. `DCGM_FI_DEV_FB_USED` at 100%. Requests timing out.

**Root causes:** KV cache exhausted by long-context requests; model loaded without quantisation on undersized GPU; memory leak in older vLLM versions.

```bash
# 1. Check pod events
kubectl describe pod -n inference <pod-name>

# 2. Check GPU memory from inside the pod
kubectl exec -n inference <pod-name> -- nvidia-smi

# 3. Reduce max_model_len in HelmRelease values
# vllm.args.max-model-len: "4096"   (reduce from 8192)
# vllm.args.gpu-memory-utilization: "0.85"

# 4. Force rollout restart
kubectl rollout restart deployment/vllm -n inference
```

---

### RB-002 — Flux HelmRelease Stuck / Not Syncing

**Symptoms:** HelmRelease in `Failed` or permanently `Reconciling`. New model version not deployed after git push.

```bash
# Check all Flux resources
flux get all -n flux-system

# Force reconcile
flux reconcile kustomization flux-system --with-source

# Suspend and resume to clear stuck state
flux suspend helmrelease vllm -n inference
flux resume helmrelease vllm -n inference

# Check source controller git connectivity
kubectl exec -n flux-system deployment/source-controller \
  -- curl -I https://github.com/org/fleet-config
```

---

### RB-003 — GPU Node XID Error

**Symptoms:** DCGM alert: XID 63 (row remapping) or XID 74 (NVLink error). GPU shows unavailable in device plugin. Inference pods evicted.

```bash
# Cordon node immediately — prevent new scheduling
kubectl cordon <node-name>

# Check DCGM XID details
kubectl logs -n gpu-operator daemonset/dcgm-exporter -c dcgm

# Drain workloads gracefully
kubectl drain <node-name> \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=60

# Run DCGM diagnostic
kubectl exec -n gpu-operator daemonset/dcgm-exporter -- \
  dcgmi diag -r 1 -i 0

# If persistent hardware fault: label for physical review
kubectl label node <node-name> maintenance=hardware-review
```

---

### RB-004 — Edge Site Config Drift After Reconnect

**Symptoms:** Site has been offline. Reconnected. Running workloads differ from desired state in git.

```bash
# Force full reconciliation
flux reconcile source git fleet-config -n flux-system
flux reconcile kustomization --all -n flux-system

# Review what would change (dry-run)
flux diff kustomization flux-system

# Check HelmRelease desired vs actual
kubectl get helmrelease -n inference -o yaml | grep -A5 "lastApplied"

# If drift is from manual intervention: document in incident report
# then reconcile to restore declared state
```

---

## Part 5 — Configuration Reference

---

### 5.1 KEDA ScaledObject — vLLM Queue Depth

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-autoscaler
  namespace: inference
spec:
  scaleTargetRef:
    name: vllm-deployment
  minReplicaCount: 1          # Never scale to zero for online inference
  maxReplicaCount: 4
  cooldownPeriod: 300         # 5-minute GPU spindown delay
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://kube-prometheus-stack-prometheus.monitoring:9090
        metricName: vllm_requests_waiting
        query: avg(vllm:num_requests_waiting)
        threshold: "10"       # Scale out when 10+ requests waiting
```

---

### 5.2 Flux HelmRelease — Progressive Wave Rollout

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: vllm
  namespace: inference
  annotations:
    fluxcd.io/wave: "2"       # Deploy after wave-1 canary sites validate
spec:
  chart:
    spec:
      chart: vllm
      version: "0.5.3"
      sourceRef:
        kind: HelmRepository
        name: internal-charts
  values:
    model: meta-llama/Llama-3-8B-Instruct
    gpuMemoryUtilization: 0.85
    maxModelLen: 8192
    tensorParallelSize: 1
  rollback:
    force: true
    cleanupOnFail: true
```

---

### 5.3 Kyverno Policy — Enforce GPU Resource Limits

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-gpu-limits
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-gpu-limits
      match:
        resources:
          kinds: [Pod]
          namespaces: [inference]
      validate:
        message: "GPU workloads in the inference namespace must declare nvidia.com/gpu limits"
        pattern:
          spec:
            containers:
              - resources:
                  limits:
                    nvidia.com/gpu: "?*"
```

---

### 5.4 GPU Memory Sizing Reference

| Model | Precision | GPU Memory Required | Minimum Hardware |
|-------|-----------|---------------------|-----------------|
| Llama-3-8B | FP16 | ~19GB | 1× A100 40GB |
| Llama-3-8B | INT4 (AWQ) | ~6GB | 1× L4 24GB |
| Llama-3-70B | FP16 | ~168GB | 2× A100 80GB |
| Llama-3-70B | INT4 (AWQ) | ~42GB | 1× A100 80GB |
| Llama-3-405B | FP16 | ~972GB | 12× A100 80GB |
| Mistral-7B | FP16 | ~16GB | 1× A100 40GB |

Formula: `memory_GB = parameters_B × dtype_bytes × 1.2`

---

*Document version 1.0 — generated as a discovery-first design reference. Answers to Part 0 questions will determine which architectural choices in Parts 1–5 should be adjusted for your specific context.*
