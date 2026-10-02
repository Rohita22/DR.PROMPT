# ADR: Application Platform v2 executable isolation

Status: accepted for implementation; local execution unavailable until runtime provisioning.
Date: 2026-10-02.

## Environment evidence

Development is native Windows NT 10.0.26200 using PowerShell, Python 3.12 and Node.
Docker, Podman, runsc and Firecracker are absent from PATH and standard Windows install paths.
An elevated read-only WSL inspection reports WSL2 and one stopped docker-desktop distribution.
This is evidence of a residual WSL distribution, not a working Docker installation.
There is no host /dev/kvm. KVM inside the stopped distribution is unverified; we will not
start or repurpose Docker's managed distribution. No repository CI configuration was found.
No usable isolation provider is currently available. Executable challenges fail closed.

## Candidates

| Candidate | Isolation and resources | Portability / operations | Decision |
|---|---|---|---|
| Rootless Docker Engine | Linux namespaces, unprivileged daemon/user namespaces, seccomp, no-network namespace; cgroup v2 required for CPU/memory/PID enforcement | Free Engine on Linux; Windows requires a deliberately provisioned Linux VM/WSL distro; prepared images | Selected adapter, strict capability checks; unavailable locally |
| Rootless Podman | Similar kernel boundary, daemonless; cgroup delegation still essential | Free; Windows requires Podman machine/VM; different inspection contracts | Viable future adapter, not silently treated as Docker |
| gVisor/runsc | User-space kernel adds syscall isolation beyond ordinary containers | Linux installation/runtime administration and compatibility testing required | Preferred production hardening; not installed or claimed active |
| Firecracker | Separate guest kernel using KVM, strong VM boundary | Linux + accessible /dev/kvm, kernel/rootfs/jailer/network orchestration required | Not practical on this native Windows environment; deferred |
| Host subprocess/temp directory | No meaningful hostile-code boundary | Easy but unsafe | Explicitly prohibited |

## Decision and boundary

Keep STATIC on the existing constrained HTML/CSS path. SANDBOXED_EXECUTABLE uses a
provider-neutral ApplicationSandbox port and a hardened rootless Linux Docker adapter.
Default backend is disabled. Enabling requires Linux rootless Engine, cgroup v2 and a
locally prepared immutable image ID; no per-attempt pulling or dependency installation.
The adapter must reject unsupported engines rather than ignore missing enforcement.

Every run gets a fresh non-root container, network none, no published ports, read-only
root filesystem, all capabilities dropped, no-new-privileges, bounded tmpfs workspace,
CPU/memory/swap/PID limits and a wall-clock watchdog that forcibly removes the container.
No host mounts (including Docker socket), devices, environment files, application secrets
or repository roots enter the container. Workspace files are transferred as bounded data.
Commands are repository-owned presets. The runtime contains pinned React/TypeScript,
bundler, Playwright and Chromium dependencies. The agent edits only declared source files.

Trusted controller, build/typecheck and browser all run inside the container. Application
JS executes only inside that container's browser. The trusted browser controller serves
only built assets over container-local loopback; no ports are exposed on the host.
Browser contexts are fresh per check, block non-application requests and cannot navigate
local files. Hidden scenarios stay server-side and outside the page; raw runner output,
console logs, hidden state screenshots and expected values are not gameplay diagnostics.
Only bounded validated result data and screenshots of fresh initial public state return.

## Limits and operational obligations

Ordinary rootless containers share the Linux kernel: this is not a proof against kernel
or browser exploits. Do not enable public adversarial multi-tenant production use without
security review, dedicated disposable workers, patching, an independently verified image,
gVisor or VM isolation, and daemon-crash orphan cleanup. Runtime flags alone are not proof
of enforcement: opt-in integration probes must pass on the deployment host. Container
cleanup failures are infrastructure failures, not successful attempts. No host fallback.

Current Windows installation cannot run integration probes; package functionality tested
with fakes is not equivalent to validated executable behavior. Documentation and reports
must distinguish these statuses. Host filesystem storage remains bounded by transfer
limits; writable container tmpfs has a hard size cap. No container reuse across users.

## References

- [Docker rootless mode](https://docs.docker.com/engine/security/rootless/)
- [Rootless cgroup requirements](https://docs.docker.com/engine/security/rootless/tips/)
- [Podman run controls](https://docs.podman.io/en/stable/markdown/podman-run.1.html)
- [gVisor Docker setup](https://gvisor.dev/docs/user_guide/quick_start/docker/)
- [Firecracker prerequisites](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md)
