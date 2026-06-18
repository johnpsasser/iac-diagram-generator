---
name: iac-diagram-generator
description: Analyzes Infrastructure as Code files (Terraform, CloudFormation, Kubernetes, Docker Compose) and generates visual architecture diagrams. Use when analyzing infrastructure code, designing cloud architectures, or when the user requests architecture diagrams from IaC.
allowed-tools: Read, Bash, Glob, Grep
---

# IaC Architecture Diagram Generator

Analyzes Infrastructure as Code and generates professional architecture diagrams
using Nano Banana Pro (Gemini 3 Pro Image). Parses IaC into a resource/dependency
graph, then renders a polished diagram from a structured prompt.

**Parsing is supported for:** Terraform, CloudFormation, Kubernetes, Docker Compose.

## Workflow

### Step 1: Discover IaC files

Use Glob to find IaC files in the target directory:

- **Terraform**: `*.tf`, `*.tfvars`
- **CloudFormation**: `*.yaml`, `*.yml`, `*.json`, `*.template`
- **Kubernetes**: `*.yaml`, `*.yml` (often under `manifests/`, `k8s/`, `kube/`)
- **Docker Compose**: `compose.yaml`, `compose.yml`, `docker-compose.yaml`, `docker-compose.yml`

If no file is mentioned, search the current directory recursively. Pick the format
that matches what you find before parsing.

### Step 2: Parse the files

Run the parser. It accepts **local paths or GitHub repository URLs** and prints a
JSON resource graph. The format argument is one of `terraform`,
`cloudformation`, `kubernetes`, `docker-compose`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" <format> <path-or-github-url>
```

Examples:

```bash
# Local
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" terraform ./infrastructure
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" cloudformation template.yaml
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" kubernetes k8s/
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" docker-compose compose.yaml

# GitHub (cloned to a temp dir automatically, then cleaned up)
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" terraform https://github.com/user/repo
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/parse_iac.py" terraform https://github.com/user/repo/tree/main/infrastructure
```

Supported GitHub URL forms: `https://github.com/user/repo`,
`.../tree/branch/path/to/dir`, `github.com/user/repo`, `git@github.com:user/repo`.

The JSON contains resources, dependencies/relationships, hierarchical structure
(VPCs, subnets, namespaces), and connection types.

### Step 3: Analyze the resource graph

From the JSON, understand:

- **Hierarchy**: VPC > Availability Zones > Subnets > Resources (or cluster > namespaces > workloads)
- **Resource types**: compute, networking, storage, database, security, analytics
- **Dependencies**: explicit (`depends_on`, `DependsOn`) and implicit (references)
- **Connections**: how resources communicate (HTTP, DB, queues)
- **Security boundaries**: VPCs, subnets, security groups, network policies

### Step 4: Build the Nano Banana Pro prompt

Write a detailed, structured, natural-language prompt describing the architecture.
**Follow the visual design system** so output is consistent and professional:

- Read `references/visual-style.md` for the full template (canvas, frame, header,
  zones, icon style, color palette, connection styling, labels, layout, and the
  DO/DON'T list).
- Read `references/example-prompts.md` for two complete worked examples
  (three-tier web app, Kubernetes microservices), a fill-in-the-blanks template,
  and per-provider header colors.

Key rules: 16:9 landscape, framed border with margins, gradient header with title +
subtitle, isometric 3D icons (never flat official icons), tinted zone backgrounds,
curved bezier arrows with pill-shaped protocol/port labels, left-to-right flow.
If there are more than ~15 resources, split into multiple focused diagrams.

### Step 5: Generate the diagram

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/iac-diagram-generator/scripts/generate_diagram.py" "ENHANCED_PROMPT_HERE"
```

This requires the `GEMINI_API_KEY` environment variable (see Setup). It saves a
timestamped PNG (`iac_diagram_*.png`) in the current directory.

### Step 6: Report back

Give the user: the diagram filename/location, a summary of the architecture
components, notable patterns or best practices observed, and any improvement
suggestions.

For editable vector output (SVG/PDF), see `references/vectorization.md`.

## Supported IaC formats

### Terraform (`.tf`, `.tfvars`)

Tiered parser, auto-selected best-first:

| Parser | Accuracy | Requirements | What it does |
|--------|----------|--------------|--------------|
| **tfparse** | Best | `terraform init` run, Python 3.10+ | Full expression evaluation, accurate dependencies |
| **python-hcl2** | Good | none | Proper HCL2 parsing, reference extraction |
| **regex** | Basic | none | Pattern matching, inferred dependencies |

For best results: `cd` into the Terraform dir and run `terraform init` first so
`tfparse` can resolve modules and expressions.

### AWS CloudFormation (`.yaml`, `.yml`, `.json`, `.template`)

Tiered parser: **cfn-lint** (best — resolves intrinsic functions) → **PyYAML**
(basic). Extracts dependencies from `!Ref`/`Fn::Ref`, `!GetAtt`/`Fn::GetAtt`,
`!Sub`/`Fn::Sub`, `DependsOn`, and `Fn::If` branches.

### Kubernetes (`.yaml`, `.yml` — manifests, Helm output)

Relationship detection (inspired by
[KubeDiagrams](https://github.com/philippemerle/KubeDiagrams)):

| Relationship | Example | Detection |
|--------------|---------|-----------|
| **SELECTOR** | Service → Deployment | Label-selector matching |
| **OWNER** | Deployment → Pod | Ownership hierarchy |
| **REFERENCE** | Ingress → Service | Backend references |
| **MOUNT** | Deployment → ConfigMap/Secret/PVC | Volume mounts |
| **COMMUNICATION** | NetworkPolicy | Ingress/egress selectors |

Handles 20+ kinds across Workloads, Networking, Config, Storage, and RBAC.

### Docker Compose (`compose.yaml`, `docker-compose.yaml`, …)

Extracts services, networks, volumes, and dependencies (`depends_on`, network
membership, volume sharing).

## Not yet supported

The parser does **not** currently handle these formats — do not claim diagrams
for them without first parsing the resources by hand:

- **Pulumi** (`.ts`/`.py`/`.go`) — requires language-specific AST analysis
- **Azure ARM / Bicep**
- **GCP Deployment Manager**

If a user asks for one of these, say it isn't supported yet and offer to read the
files directly and build the graph manually, or to diagram a supported format.

## Common architecture patterns

- **Three-tier web app**: public subnet (LBs, NAT) → private subnet (app servers,
  workers) → database subnet (RDS, ElastiCache, no direct internet).
- **Microservices**: API gateway / ingress at the edge, service mesh for
  inter-service calls, namespaces/VPCs per domain, shared data stores and queues.
- **Serverless**: API Gateway → Lambda → DynamoDB/S3, EventBridge/SQS for async,
  CloudFront for delivery.

## Setup

**Required:** Python 3.7+ and PyYAML (`pip install pyyaml`).

**Optional (better parsing):**

```bash
pip install python-hcl2   # better Terraform parsing, no terraform init needed
pip install tfparse       # best Terraform parsing, needs terraform init + Python 3.10+
pip install cfn-lint      # accurate CloudFormation intrinsic-function parsing
```

**Diagram generation:** set a Gemini API key (the generator auto-installs
`google-genai` on first run):

```bash
export GEMINI_API_KEY="your-api-key-here"   # https://aistudio.google.com/apikey
```

Nano Banana Pro renders at roughly $0.134/image (a few seconds each) and embeds a
SynthID watermark marking the image as AI-generated.

## Error handling

The parser reports clear messages for: missing/invalid files, unsupported formats,
IaC syntax errors, failed GitHub clones (and times out after 120s), and read
permission issues. The generator reports missing `GEMINI_API_KEY`, auth/quota/rate
errors, and network failures. On a parse error the script exits non-zero — surface
the message to the user rather than fabricating a diagram.
